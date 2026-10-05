from typing import Any, Dict


def _status(item: Dict[str, Any]) -> str:
    if item.get("status") == "not_loaded":
        return "not_available"
    count = item.get("count_within_radius")
    return "observed" if count is not None else "not_available"


def analyze(development: Dict[str, Any], spatial: Dict[str, Any], rag_result: Dict[str, Any]) -> Dict[str, Any]:
    f = spatial.get("findings", {})
    units = development.get("units") or development.get("number_of_units")

    out = {
        "status": "ok",
        "evidence_policy": "Observations are derived from processed datasets; no risk score is fabricated without validated thresholds or simulation inputs.",
        "mobility": {
            "status": _status(f.get("roads", {})),
            "roads_within_radius": f.get("roads", {}).get("count_within_radius"),
            "bus_stops_within_radius": f.get("bus_stops", {}).get("count_within_radius"),
            "traffic_event_records_within_radius": f.get("traffic_events", {}).get("count_within_radius"),
            "interpretation": "Road and transit proximity are observed. Traffic-event records are not a congestion measurement."
        },
        "social_infrastructure": {
            "schools_within_radius": f.get("schools", {}).get("count_within_radius"),
            "hospitals_within_radius": f.get("hospitals", {}).get("count_within_radius"),
            "police_within_radius": f.get("police", {}).get("count_within_radius"),
            "fire_stations_within_radius": f.get("fire_stations", {}).get("count_within_radius"),
            "interpretation": "Facility proximity is reported as observed context; adequacy cannot be judged without validated service-area standards and demand data."
        },
        "environment": {
            "parks_within_radius": f.get("parks", {}).get("count_within_radius"),
            "water_bodies_within_radius": f.get("water_bodies", {}).get("count_within_radius"),
            "interpretation": "Mapped green/water features are reported. Environmental impact requires additional terrain, flood, air-quality or ecological data for quantitative assessment."
        },
        "built_context": {
            "buildings_within_radius": f.get("buildings", {}).get("count_within_radius"),
            "landuse_within_radius": f.get("landuse", {}).get("count_within_radius"),
        },
        "utilities": {
            "status": "not_available",
            "interpretation": "Water and electricity demand impacts are not calculated because validated Bengaluru utility datasets and local demand assumptions are not currently loaded."
        },
        "regulatory": {
            "status": "supported_by_rag" if rag_result.get("results") else "not_evaluated",
            "knowledge_base_status": rag_result.get("status"),
            "interpretation": "Regulatory feasibility should only be stated after retrieving applicable official planning documents."
        },
        "scenario_scale": {
            "units": units,
            "population_estimate": None,
            "water_demand_estimate": None,
            "energy_demand_estimate": None,
            "reason": "No local assumption or validated dataset supplied."
        },
    }
    return out
