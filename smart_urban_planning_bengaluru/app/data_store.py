from functools import lru_cache
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from .settings import DATA_GPKG, TRAFFIC_FILE

RAW_OSM = Path(__file__).resolve().parents[1] / "data" / "raw" / "export.geojson"
SUPPLEMENTAL_OSM = Path(__file__).resolve().parents[1] / "data" / "raw" / "export_poi.geojson"

LAYER_NAMES = [
    "roads", "buildings", "schools", "hospitals", "police", "fire_stations",
    "bus_stops", "landuse", "parks", "water_bodies", "pois", "transit", "green_water",
    "traffic_events"
]


def _gpkg_layers() -> set[str]:
    if not DATA_GPKG.exists():
        return set()
    try:
        return set(gpd.list_layers(DATA_GPKG)["name"].tolist())
    except Exception:
        return set()


@lru_cache(maxsize=None)
def read_layer(kind: str) -> Optional[gpd.GeoDataFrame]:
    if kind not in LAYER_NAMES or not DATA_GPKG.exists():
        return None
    if kind not in _gpkg_layers():
        return None
    g = gpd.read_file(DATA_GPKG, layer=kind, engine="pyogrio")
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    else:
        g = g.to_crs("EPSG:4326")
    return g


@lru_cache(maxsize=1)
def read_traffic() -> Optional[gpd.GeoDataFrame]:
    layer = read_layer("traffic_events")
    if layer is not None:
        return layer
    if not TRAFFIC_FILE.exists():
        return None
    df = pd.read_csv(TRAFFIC_FILE)
    if not {"longitude", "latitude"}.issubset(df.columns):
        return None
    geom = gpd.points_from_xy(df["longitude"], df["latitude"])
    return gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")


def layer_loaded(kind: str) -> bool:
    return read_layer(kind) is not None


def layer_feature_count(kind: str) -> Optional[int]:
    g = read_layer(kind)
    return None if g is None else int(len(g))


def _tag_filter(gdf: gpd.GeoDataFrame, kind: str) -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf if gdf is not None else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    s = pd.Series(False, index=gdf.index)
    def norm(col: str) -> pd.Series:
        if col not in gdf.columns:
            return pd.Series("", index=gdf.index, dtype="string")
        return gdf[col].astype("string").str.lower().str.strip()

    if kind == "roads" and "highway" in gdf.columns:
        s = gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])
        s &= norm("highway").isin({
            "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
            "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
            "residential", "living_street", "service", "track", "road", "construction", "proposed"
        })
    elif kind == "buildings" and "building" in gdf.columns:
        # A building layer must represent building footprints, not POI points carrying a building tag.
        s = gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"]) & gdf["building"].notna()
    elif kind == "schools" and "amenity" in gdf.columns:
        s = norm("amenity").isin({"school", "college", "university", "kindergarten"})
    elif kind == "hospitals":
        s = norm("amenity").eq("hospital") | norm("healthcare").eq("hospital") | norm("building").eq("hospital")
    elif kind == "police":
        s = norm("amenity").eq("police") | norm("emergency").eq("police")
    elif kind == "fire_stations":
        s = norm("amenity").eq("fire_station") | norm("emergency").eq("fire_station")
    elif kind == "bus_stops":
        s = (
            norm("highway").eq("bus_stop")
            | norm("amenity").eq("bus_station")
            | ((norm("bus").eq("yes")) & norm("public_transport").isin({"platform", "stop_position", "station"}))
        )
    elif kind == "landuse" and "landuse" in gdf.columns:
        s = gdf["landuse"].notna()
    elif kind == "parks" and "leisure" in gdf.columns:
        s = norm("leisure").eq("park")
    elif kind == "water_bodies":
        water = norm("water")
        natural = norm("natural")
        waterway = norm("waterway")
        s = water.ne("") | natural.isin({"water", "wetland"}) | waterway.ne("")
    elif kind == "transit":
        s = norm("public_transport").isin({"platform", "stop_position", "station"}) | norm("highway").isin({"bus_stop", "platform"})
    elif kind == "green_water":
        s = norm("leisure").isin({"park", "playground", "sports_centre", "pitch"}) | norm("water").ne("") | norm("natural").isin({"water", "wetland"}) | norm("waterway").ne("")
    elif kind == "pois":
        for c in ["amenity", "public_transport", "emergency", "shop", "tourism", "office", "healthcare", "education"]:
            if c in gdf.columns:
                s |= gdf[c].notna() & norm(c).ne("")
    else:
        s = pd.Series(True, index=gdf.index)
    return gdf[s].copy()


def nearby_layer(kind: str, lon: float, lat: float, radius_m: float, limit: Optional[int] = 50) -> gpd.GeoDataFrame:
    base = read_layer(kind)
    if base is None:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    g = _tag_filter(base, kind)
    if g.empty:
        return g
    p = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32643").iloc[0]
    gm = g.to_crs("EPSG:32643")
    dist = gm.geometry.distance(p)
    out = gm.loc[dist <= radius_m].copy()
    if out.empty:
        return out.to_crs("EPSG:4326")
    out["distance_m"] = dist.loc[out.index]
    out = out.sort_values("distance_m")
    if limit is not None:
        out = out.head(limit)
    return out.to_crs("EPSG:4326")


def nearby_traffic(lon: float, lat: float, radius_m: float, limit: Optional[int] = 100) -> gpd.GeoDataFrame:
    g = read_traffic()
    if g is None or g.empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326") if g is None else g
    p = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:32643").iloc[0]
    gm = g.to_crs("EPSG:32643")
    dist = gm.geometry.distance(p)
    out = gm.loc[dist <= radius_m].copy()
    if out.empty:
        return out.to_crs("EPSG:4326")
    out["distance_m"] = dist.loc[out.index]
    out = out.sort_values("distance_m")
    if limit is not None:
        out = out.head(limit)
    return out.to_crs("EPSG:4326")


def serialize_features(gdf: gpd.GeoDataFrame, max_features: int = 50):
    if gdf is None or gdf.empty:
        return []
    result = []
    keys = {
        "osm_id", "id", "name", "name:en", "name:kn", "highway", "building", "amenity",
        "public_transport", "emergency", "landuse", "leisure", "natural", "water", "waterway",
        "railway", "bus", "healthcare", "education", "distance_m", "maxspeed", "lanes", "oneway",
        "surface", "access", "lit", "operator", "network", "shelter", "alertType", "vehicleType",
        "observationDateTime", "cameraUsage", "junctionName"
    }
    for _, row in gdf.head(max_features).iterrows():
        d = {}
        for k, v in row.items():
            if k not in keys or pd.isna(v):
                continue
            if hasattr(v, "item"):
                v = v.item()
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            d[k] = v
        d["geometry"] = row.geometry.__geo_interface__
        result.append(d)
    return result


def layer_result(kind: str, lon: float, lat: float, radius_m: float, limit: int = 50) -> dict:
    """Return an API-safe layer object that distinguishes not_loaded from zero.

    `count` is the total number found within the radius. `displayed_count` is the
    number actually serialized for the response/map. This avoids the old ambiguity
    where a 50-feature display cap looked like a 50-feature spatial count.
    """
    loaded = layer_loaded(kind)
    if not loaded:
        return {"status": "not_loaded", "count": None, "displayed_count": 0, "truncated": False, "features": [], "message": f"Layer '{kind}' is not loaded."}
    all_g = nearby_layer(kind, lon, lat, radius_m, limit=None)
    total = int(len(all_g))
    displayed = min(total, limit)
    g = all_g.head(limit)
    return {
        "status": "ready",
        "count": total,
        "displayed_count": displayed,
        "truncated": total > limit,
        "features": serialize_features(g, limit),
    }
