from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .settings import DATA_GPKG, TRAFFIC_FILE, RAG_DIR
from .schemas import ContextRequest, SpatialRequest, DomainRequest, ScenarioRequest, ScenarioAnalyzeRequest, ScenarioCompareRequest, DesignRequest, AlternativesRequest, ReportRequest
from .data_store import (
    LAYER_NAMES, RAW_OSM, SUPPLEMENTAL_OSM, layer_feature_count, layer_loaded,
    read_traffic, serialize_features, layer_result
)
from .services.spatial import context, analyze
from .services.scenario import analyze as scenario_analyze, compare
from .services.impact import analyze as impact_analyze
from .services.design import generate, generate_alternatives, parse_parcel_geojson
from .rag import rag

app = FastAPI(title="Smart Urban Planning Assistant – Bengaluru", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

from fastapi.staticfiles import StaticFiles
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PARCEL_PATH = ROOT / "data" / "processed" / "site_parcel.geojson"
app.mount("/static", StaticFiles(directory=str(ROOT / "frontend")), name="static")


@app.get("/")
def root():
    from fastapi.responses import FileResponse
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/health")
def health():
    try:
        loaded = [name for name in LAYER_NAMES if name != "traffic_events" and layer_loaded(name)]
        missing = [name for name in LAYER_NAMES if name != "traffic_events" and not layer_loaded(name)]
        return {
            "status": "ok",
            "data_store": "ready" if DATA_GPKG.exists() else "missing",
            "traffic_data": "ready" if read_traffic() is not None else "missing",
            "rag": rag.status(),
            "backend_mode": "local_gpkg_layers",
            "osm_sources": {
                "primary_present": RAW_OSM.exists(),
                "supplemental_present": SUPPLEMENTAL_OSM.exists(),
            },
            "processed_layers_loaded": loaded,
            "processed_layers_not_loaded": missing,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/domains")
def domains():
    domains = ["transportation", "public_social_infrastructure", "land_use", "environment", "urban_context"]
    if read_traffic() is not None:
        domains.append("traffic_events")
    return {"domains": domains}


@app.get("/layers")
def layers():
    source_map = {
        "roads": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "buildings": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "schools": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "hospitals": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "police": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "fire_stations": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "bus_stops": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "landuse": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "parks": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "water_bodies": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "pois": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "transit": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "green_water": [RAW_OSM.name, SUPPLEMENTAL_OSM.name],
        "traffic_events": [TRAFFIC_FILE.name],
    }
    out = []
    for layer in LAYER_NAMES:
        loaded = (read_traffic() is not None) if layer == "traffic_events" else layer_loaded(layer)
        out.append({
            "layer": layer,
            "source": source_map.get(layer, []),
            "status": "ready" if loaded else "not_loaded",
            "feature_count_total": layer_feature_count(layer) if layer != "traffic_events" else (None if read_traffic() is None else int(len(read_traffic()))),
        })
    return {"layers": out}


@app.get("/osm/diagnostics")
def osm_diagnostics():
    from pathlib import Path
    path = ROOT / "reports" / "osm_diagnostics.json"
    if not path.exists():
        raise HTTPException(404, "OSM diagnostics have not been generated yet. Run scripts/prepare_data.py first.")
    import json
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/scenario/parse")
def parse_scenario(req: ScenarioRequest):
    import re
    q = req.query.strip()
    low = q.lower()
    coords = re.search(r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)", q)
    units = re.search(r"(\d[\d,]*)\s*(?:units?|apartments?|flats?|homes?|houses?)", q, re.I)
    aliases = {
        "residential":"residential", "commercial":"commercial", "industrial":"industrial", "industry":"industrial",
        "mixed-use":"mixed-use", "mixed use":"mixed-use", "hospital":"hospital", "school":"school",
        "office":"office", "retail":"retail", "hospitality":"hospitality"
    }
    dtype = next((canon for key,canon in aliases.items() if key in low), None)
    out = {"query": q, "location": None, "development_type": dtype, "units": None, "missing": []}
    if coords:
        lat, lon = float(coords.group(1)), float(coords.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            out["location"] = {"latitude": lat, "longitude": lon}
        else:
            out["missing"].append("valid_location")
    else:
        out["missing"].append("location")
    if units:
        out["units"] = int(units.group(1).replace(",", ""))
    else:
        out["missing"].append("units")
    if dtype is None:
        out["missing"].append("development_type")
    return out


@app.post("/digital-twin/context")
def digital_twin(req: ContextRequest):
    try:
        return context(req.latitude, req.longitude, req.radius_m)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))


@app.post("/spatial/analyze")
def spatial(req: SpatialRequest):
    try:
        return analyze(req.latitude, req.longitude, req.radius_m, req.development_type)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))


@app.get("/rag/status")
def rag_status():
    return rag.status()


@app.post("/rag/reload")
def rag_reload():
    return rag.reload()


@app.post("/rag/search")
def rag_search(payload: dict):
    return rag.search(payload.get("query", ""), int(payload.get("top_k", 5)), payload.get("scenario") or {})


@app.post("/domain/query")
def domain_query(req: DomainRequest):
    mapping = {
        "transportation": ["roads", "bus_stops"],
        "public_infrastructure": ["schools", "hospitals", "police", "fire_stations", "pois"],
        "public_social_infrastructure": ["schools", "hospitals", "police", "fire_stations", "pois"],
        "land_use": ["landuse"],
        "environment": ["parks", "water_bodies"],
        "traffic": ["traffic_events"],
        "urban_context": ["buildings", "pois"],
    }
    requested_layers = mapping.get(req.domain)
    if not requested_layers:
        return {"status": "domain_unavailable", "domain": req.domain, "message": "No processed local dataset is currently mapped to this domain."}

    result = {}
    for layer in requested_layers:
        if layer == "traffic_events":
            if read_traffic() is None:
                result[layer] = {"status": "not_loaded", "count": None, "features": []}
            else:
                g = __import__("app.data_store", fromlist=["nearby_traffic"]).nearby_traffic(req.longitude, req.latitude, req.radius_m)
                result[layer] = {"status": "ready", "count": int(len(g)), "features": serialize_features(g, 25)}
        else:
            result[layer] = layer_result(layer, req.longitude, req.latitude, req.radius_m, 25)
    return {"status": "ok", "domain": req.domain, "data": result}


@app.post("/scenario/analyze")
def scenario(req: ScenarioAnalyzeRequest):
    ctx = context(req.location.latitude, req.location.longitude, req.radius_m)
    sp = analyze(req.location.latitude, req.location.longitude, req.radius_m, req.development.get("type"))
    query = (
        f"Bengaluru planning regulations for {req.development.get('type', 'development')} "
        f"with {req.development.get('units', req.development.get('number_of_units', 'unknown'))} units; "
        "zoning FAR setbacks parking fire access environmental requirements"
    )
    rag_result = rag.search(query, 8, {"location": req.location.model_dump(), "development": req.development, "spatial_findings": sp.get("findings", {})})
    impact = impact_analyze(req.development, sp, rag_result)
    return scenario_analyze(req.location.model_dump(), req.development, req.radius_m, ctx, sp, rag_result, impact)


@app.post("/scenario/compare")
def scenario_compare(req: ScenarioCompareRequest):
    return compare(req.scenarios)


@app.post("/parcel/upload")
async def parcel_upload(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    if not filename.endswith((".geojson", ".json")):
        raise HTTPException(400, "Upload a .geojson or .json parcel file.")
    try:
        raw = await file.read()
        import json
        obj = json.loads(raw.decode("utf-8"))
        geom = parse_parcel_geojson(obj)
        if geom is None:
            raise ValueError("No parcel geometry found.")
        PARCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        PARCEL_PATH.write_text(json.dumps({"type": "Feature", "properties": {"source_file": file.filename}, "geometry": geom.__geo_interface__}, indent=2), encoding="utf-8")
        area_m2 = float(__import__("geopandas").GeoSeries([geom], crs="EPSG:4326").to_crs("EPSG:32643").area.iloc[0])
        centroid = geom.centroid
        return {
            "status": "ok",
            "filename": file.filename,
            "area_m2": round(area_m2, 2),
            "centroid": {"latitude": centroid.y, "longitude": centroid.x},
            "parcel_geojson": {"type": "Feature", "properties": {"source_file": file.filename}, "geometry": geom.__geo_interface__},
        }
    except Exception as e:
        raise HTTPException(400, f"Invalid parcel GeoJSON: {e}")


@app.get("/parcel/current")
def parcel_current():
    if not PARCEL_PATH.exists():
        return {"status": "not_loaded", "parcel_geojson": None}
    import json
    return {"status": "ready", "parcel_geojson": json.loads(PARCEL_PATH.read_text(encoding="utf-8"))}


@app.post("/design/generate")
def design(req: DesignRequest):
    return generate(req.site, req.development, req.existing_context, req.planning_rules, req.impact_analysis, req.strategy)


@app.post("/design/alternatives")
def design_alternatives(req: AlternativesRequest):
    try:
        return generate_alternatives(req.site, req.development, req.existing_context, req.planning_rules, req.impact_analysis)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.post("/report/pdf")
def report_pdf(req: ReportRequest):
    from .services.report import build_report_pdf
    from fastapi.responses import Response
    pdf = build_report_pdf(req.model_dump())
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=smart_urban_planning_bengaluru_report.pdf"},
    )


@app.post("/report/html")
def report_html(req: ReportRequest):
    from .services.report import build_report_html
    from fastapi.responses import HTMLResponse
    return HTMLResponse(build_report_html(req.model_dump()))
