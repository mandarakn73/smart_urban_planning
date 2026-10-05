from ..data_store import layer_result, layer_loaded, nearby_layer, nearby_traffic, serialize_features, read_layer


def context(lat, lon, radius_m):
    result = {}
    for key in [
        "roads", "buildings", "schools", "hospitals", "police", "fire_stations", "bus_stops",
        "landuse", "parks", "water_bodies", "pois"
    ]:
        result[key] = layer_result(key, lon, lat, radius_m, 50)

    if read_layer("traffic_events") is None:
        result["traffic_events"] = {"status": "not_loaded", "count": None, "displayed_count": 0, "truncated": False, "features": [], "message": "Traffic-event layer is not loaded."}
    else:
        tg_all = nearby_traffic(lon, lat, radius_m, None)
        tg = tg_all.head(50)
        result["traffic_events"] = {
            "status": "ready",
            "count": int(len(tg_all)),
            "displayed_count": int(len(tg)),
            "truncated": len(tg_all) > 50,
            "features": serialize_features(tg, 50),
        }
    return result


def _finding(kind: str, lon: float, lat: float, radius_m: float):
    if not layer_loaded(kind):
        return {"status": "not_loaded", "count_within_radius": None, "nearest_m": None}
    g = nearby_layer(kind, lon, lat, radius_m, None)
    return {
        "status": "ready",
        "count_within_radius": int(len(g)),
        "nearest_m": round(float(g["distance_m"].min()), 2) if len(g) and "distance_m" in g.columns else None,
    }


def analyze(lat, lon, radius_m, development_type=None):
    result = {
        "development_type": development_type,
        "radius_m": radius_m,
        "findings": {},
    }

    for label, kind in [
        ("schools", "schools"),
        ("hospitals", "hospitals"),
        ("police", "police"),
        ("fire_stations", "fire_stations"),
        ("bus_stops", "bus_stops"),
        ("roads", "roads"),
        ("parks", "parks"),
        ("water_bodies", "water_bodies"),
        ("buildings", "buildings"),
        ("landuse", "landuse"),
    ]:
        result["findings"][label] = _finding(kind, lon, lat, radius_m)

    if read_layer("traffic_events") is None:
        result["findings"]["traffic_events"] = {
            "status": "not_loaded", "count_within_radius": None, "nearest_m": None
        }
    else:
        tg = nearby_traffic(lon, lat, radius_m, None)
        result["findings"]["traffic_events"] = {
            "status": "ready",
            "count_within_radius": int(len(tg)),
        }

    result["notes"] = [
        "A count of 0 means the relevant processed layer is loaded and no matching feature was found within the requested radius.",
        "status='not_loaded' means the layer is unavailable in the current processed dataset; it must not be interpreted as city-wide absence.",
        "Context feature lists are capped for display; spatial counts are computed from the full processed layer within the requested radius."
    ]
    return result
