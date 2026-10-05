"""Build the Bengaluru urban Digital Twin layers from one or more OSM extracts.

The script is tag-driven. It can combine a road-heavy OSM extract with a
point/POI extract without treating bus-stop points as roads.

Example (PowerShell):
    python scripts/prepare_data.py --osm data/raw/export.geojson data/raw/export_poi.geojson \
        --traffic data/raw/bengaluru_traffic_events.csv
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict

import geopandas as gpd
import pandas as pd

OUTPUT_FIELDS = [
    "osm_id", "id", "name", "highway", "building", "building_levels",
    "amenity", "public_transport", "emergency", "landuse", "leisure",
    "natural", "water", "waterway", "railway", "bus", "healthcare",
    "education", "shop", "tourism", "office", "parking", "maxspeed",
    "lanes", "oneway", "surface", "access", "lit", "operator", "network",
    "shelter", "geometry"
]

SOURCE_TAGS = [
    "@id", "id", "name", "highway", "building", "building:levels", "amenity",
    "public_transport", "emergency", "landuse", "leisure", "natural", "water",
    "waterway", "railway", "bus", "healthcare", "education", "shop", "tourism",
    "office", "parking", "maxspeed", "lanes", "oneway", "surface", "access", "lit",
    "operator", "network", "shelter"
]

LAYER_NAMES = [
    "roads", "buildings", "schools", "hospitals", "police", "fire_stations",
    "bus_stops", "landuse", "parks", "water_bodies", "pois", "transit", "green_water"
]

ROAD_HIGHWAYS = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street", "service", "track", "road", "construction", "proposed"
}


def norm(g: gpd.GeoDataFrame, col: str) -> pd.Series:
    if col not in g.columns:
        return pd.Series("", index=g.index, dtype="string")
    return g[col].astype("string").str.strip().str.lower()


def nonempty(g: gpd.GeoDataFrame, col: str) -> pd.Series:
    if col not in g.columns:
        return pd.Series(False, index=g.index)
    return g[col].notna() & norm(g, col).ne("")


def load_source(path: Path) -> gpd.GeoDataFrame:
    schema = gpd.read_file(path, rows=1, engine="pyogrio")
    available = [c for c in SOURCE_TAGS if c in schema.columns]
    g = gpd.read_file(path, columns=available, engine="pyogrio")
    g = g[g.geometry.notna()].copy()
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    else:
        g = g.to_crs("EPSG:4326")

    if "@id" in g.columns and "osm_id" not in g.columns:
        g["osm_id"] = g["@id"]
    if "building:levels" in g.columns and "building_levels" not in g.columns:
        g["building_levels"] = g["building:levels"]
    return g


def layer_masks(g: gpd.GeoDataFrame) -> Dict[str, pd.Series]:
    amenity = norm(g, "amenity")
    building = norm(g, "building")
    public_transport = norm(g, "public_transport")
    emergency = norm(g, "emergency")
    highway = norm(g, "highway")
    landuse = norm(g, "landuse")
    leisure = norm(g, "leisure")
    natural = norm(g, "natural")
    water = norm(g, "water")
    waterway = norm(g, "waterway")
    bus = norm(g, "bus")
    healthcare = norm(g, "healthcare")
    education = norm(g, "education")

    road_geometry = g.geometry.geom_type.isin(["LineString", "MultiLineString"])
    roads = road_geometry & highway.isin(ROAD_HIGHWAYS)

    schools = (
        amenity.isin({"school", "college", "university", "kindergarten"})
        | education.isin({"school", "college", "university", "kindergarten"})
        | building.isin({"school", "college", "university", "kindergarten"})
    )

    hospitals = (
        amenity.eq("hospital")
        | healthcare.eq("hospital")
        | building.eq("hospital")
        | landuse.eq("hospital")
    )

    police = amenity.eq("police") | emergency.eq("police") | building.eq("police")
    fire_stations = amenity.eq("fire_station") | emergency.eq("fire_station") | building.eq("fire_station")

    bus_stops = (
        highway.eq("bus_stop")
        | amenity.eq("bus_station")
        | (bus.eq("yes") & public_transport.isin({"platform", "stop_position", "station"}))
    )

    landuse_layer = nonempty(g, "landuse")
    parks = leisure.eq("park")
    water_bodies = (
        nonempty(g, "water")
        | natural.isin({"water", "wetland"})
        | nonempty(g, "waterway")
        | landuse.isin({"reservoir", "basin"})
    )

    transit = (
        public_transport.isin({"platform", "stop_position", "station"})
        | amenity.eq("bus_station")
        | highway.isin({"bus_stop", "platform"})
        | bus.eq("yes")
    )

    pois = pd.Series(False, index=g.index)
    for c in ["amenity", "public_transport", "emergency", "shop", "tourism", "office", "healthcare", "education"]:
        pois |= nonempty(g, c)

    green_water = parks | water_bodies | leisure.isin({"playground", "sports_centre", "pitch"})

    building_geometry = g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])

    return {
        "roads": roads,
        "buildings": building_geometry & nonempty(g, "building"),
        "schools": schools,
        "hospitals": hospitals,
        "police": police,
        "fire_stations": fire_stations,
        "bus_stops": bus_stops,
        "landuse": landuse_layer,
        "parks": parks,
        "water_bodies": water_bodies,
        "pois": pois,
        "transit": transit,
        "green_water": green_water,
    }


def standardize_output(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = g.copy()
    if "building:levels" in out.columns and "building_levels" not in out.columns:
        out["building_levels"] = out["building:levels"]
    if "@id" in out.columns and "osm_id" not in out.columns:
        out["osm_id"] = out["@id"]

    final = gpd.GeoDataFrame(index=out.index, geometry=out.geometry, crs="EPSG:4326")
    for field in OUTPUT_FIELDS:
        if field == "geometry":
            continue
        if field in out.columns:
            final[field] = out[field].astype("string")
        else:
            final[field] = pd.Series(pd.NA, index=out.index, dtype="string")
    return final[OUTPUT_FIELDS]


def append_layer(layer: gpd.GeoDataFrame, out_path: Path, layer_name: str, written: set[str]) -> None:
    if layer.empty:
        return
    layer = standardize_output(layer)
    if layer_name in written:
        layer.to_file(out_path, layer=layer_name, driver="GPKG", engine="pyogrio", append=True)
    else:
        layer.to_file(out_path, layer=layer_name, driver="GPKG", engine="pyogrio", geometry_type="Unknown")
        written.add(layer_name)


def write_empty_layer(out_path: Path, layer_name: str) -> None:
    empty = gpd.GeoDataFrame({f: pd.Series(dtype="string") for f in OUTPUT_FIELDS if f != "geometry"}, geometry=gpd.GeoSeries([], crs="EPSG:4326"), crs="EPSG:4326")
    empty.to_file(out_path, layer=layer_name, driver="GPKG", engine="pyogrio", geometry_type="Unknown")


def count_tags(g: gpd.GeoDataFrame, diagnostics: dict) -> None:
    for tag in SOURCE_TAGS:
        if tag not in g.columns or tag == "@id":
            continue
        counter = diagnostics.setdefault("tags", {}).setdefault(tag, Counter())
        vals = g[tag].dropna().astype(str).str.strip()
        vals = vals[vals.ne("")]
        counter.update(vals.tolist())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", nargs="+", required=True, help="One or more OSM GeoJSON extracts")
    ap.add_argument("--traffic", default="data/raw/bengaluru_traffic_events.csv")
    ap.add_argument("--out", default="data/processed/bengaluru_urban.gpkg")
    ap.add_argument("--diagnostics", default="reports/osm_diagnostics.json")
    ap.add_argument("--manifest", default="reports/layer_manifest.json")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    journal = Path(str(out) + "-journal")
    if journal.exists():
        journal.unlink()

    written = set()
    seen_osm_ids = set()
    layer_counts = Counter()
    diagnostics = {
        "status": "ready",
        "source_files": [str(Path(p)) for p in args.osm],
        "total_features_read": 0,
        "total_features_after_dedup": 0,
        "geometry_types": Counter(),
        "tags": {},
    }

    for source in args.osm:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"OSM source missing: {path}")
        print(f"Reading {path} ...", flush=True)
        g = load_source(path)
        diagnostics["total_features_read"] += len(g)
        diagnostics["geometry_types"].update(g.geometry.geom_type.astype(str).tolist())
        count_tags(g, diagnostics)

        if "osm_id" in g.columns:
            ids = g["osm_id"].astype("string")
            keep = ~ids.isin(seen_osm_ids)
            # Preserve rows without an OSM id; only deduplicate known ids.
            keep |= ids.isna() | ids.eq("")
            g = g.loc[keep].copy()
            known_ids = set(ids.loc[keep & ids.notna() & ids.ne("")].tolist())
            seen_osm_ids.update(known_ids)

        diagnostics["total_features_after_dedup"] += len(g)
        masks = layer_masks(g)
        for name, mask in masks.items():
            layer = g.loc[mask].copy()
            layer_counts[name] += len(layer)
            append_layer(layer, out, name, written)
        del g

    # Create all expected OSM layers even when a source genuinely contains none.
    for name in LAYER_NAMES:
        if name not in written:
            write_empty_layer(out, name)
            written.add(name)

    # Traffic events are a separate non-OSM source.
    traffic_path = Path(args.traffic)
    traffic_loaded = False
    traffic_count = 0
    if traffic_path.exists():
        df = pd.read_csv(traffic_path)
        if {"longitude", "latitude"}.issubset(df.columns):
            tg = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326")
            tg.to_file(out, layer="traffic_events", driver="GPKG", engine="pyogrio")
            traffic_loaded = True
            traffic_count = len(tg)

    diagnostics["geometry_types"] = dict(diagnostics["geometry_types"])
    diagnostics["tags"] = {tag: dict(counter.most_common(100)) for tag, counter in diagnostics["tags"].items()}

    manifest = {
        "status": "ready",
        "source_files": [str(Path(p)) for p in args.osm],
        "total_features_read": diagnostics["total_features_read"],
        "total_features_after_dedup": diagnostics["total_features_after_dedup"],
        "building_layer_policy": "only Polygon/MultiPolygon geometries with a building tag; POI points carrying a building tag are excluded",
        "layers": {
            **{name: {"loaded": True, "feature_count": int(layer_counts[name])} for name in LAYER_NAMES},
            "traffic_events": {"loaded": traffic_loaded, "feature_count": traffic_count if traffic_loaded else None},
        },
    }

    diag_path = Path(args.diagnostics)
    diag_path.parent.mkdir(parents=True, exist_ok=True)
    diag_path.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nLayer counts:")
    for name in LAYER_NAMES:
        print(f"  {name:15s} {layer_counts[name]:>8,d}")
    print(f"  {'traffic_events':15s} {traffic_count:>8,d}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
