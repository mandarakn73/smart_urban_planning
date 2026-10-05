from __future__ import annotations

from math import ceil, sqrt
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, MultiPolygon, box, mapping, shape
from shapely.ops import nearest_points, unary_union

from ..data_store import nearby_layer


UTM_CRS = "EPSG:32643"
WGS84_CRS = "EPSG:4326"


def _feature(geom, feature_type: str, reason: str, **props) -> Optional[dict]:
    if geom is None or geom.is_empty:
        return None
    properties = {
        "feature_type": feature_type,
        "reason": reason,
        "conceptual": True,
    }
    properties.update(props)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": mapping(geom),
    }


def _fc(features: List[Optional[dict]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [f for f in features if f],
    }


def _to_wgs84(geom):
    return gpd.GeoSeries([geom], crs=UTM_CRS).to_crs(WGS84_CRS).iloc[0]


def _to_utm(geom):
    return gpd.GeoSeries([geom], crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]


def _site_envelope(lat: float, lon: float, side_m: float):
    center = gpd.GeoSeries([Point(lon, lat)], crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]
    half = side_m / 2.0
    return center, box(center.x - half, center.y - half, center.x + half, center.y + half)


def parse_parcel_geojson(parcel_geojson: Any):
    """Accept a GeoJSON Feature, FeatureCollection or bare Polygon/MultiPolygon in WGS84."""
    if not parcel_geojson:
        return None

    if isinstance(parcel_geojson, str):
        import json
        parcel_geojson = json.loads(parcel_geojson)

    obj = parcel_geojson
    if obj.get("type") == "FeatureCollection":
        geoms = []
        for feat in obj.get("features", []):
            geom = feat.get("geometry") if isinstance(feat, dict) else None
            if geom and geom.get("type") in {"Polygon", "MultiPolygon"}:
                geoms.append(shape(geom))
        if not geoms:
            raise ValueError("GeoJSON FeatureCollection contains no Polygon/MultiPolygon parcel geometry.")
        geom = unary_union(geoms)
    elif obj.get("type") == "Feature":
        geom = shape(obj.get("geometry"))
    else:
        geom = shape(obj)

    if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Parcel geometry must be a non-empty Polygon or MultiPolygon in EPSG:4326.")
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError("Parcel geometry became empty after geometry repair.")
    return geom


def _resolve_site(site: Dict[str, Any]) -> Tuple[Point, Any, bool, float]:
    parcel = parse_parcel_geojson(site.get("parcel_geojson"))
    if parcel is None:
        center = site.get("center") or {}
        lat = center.get("latitude")
        lon = center.get("longitude")
        if lat is None or lon is None:
            raise ValueError("Provide site.center.latitude and site.center.longitude.")
        area_m2 = site.get("area_m2")
        side_m = site.get("side_m")
        if side_m is None and area_m2 is None:
            raise ValueError("Provide conceptual site area in m², side length, or an actual parcel GeoJSON.")
        if side_m is None:
            area_m2 = float(area_m2)
            if area_m2 <= 0:
                raise ValueError("Conceptual site area must be positive.")
            side_m = sqrt(area_m2)
        else:
            side_m = float(side_m)
            if side_m <= 0:
                raise ValueError("Conceptual site side must be positive.")
            area_m2 = side_m * side_m
        center_m, site_geom = _site_envelope(float(lat), float(lon), float(side_m))
        return center_m, site_geom, False, float(area_m2)

    parcel_m = _to_utm(parcel)
    if parcel_m.is_empty:
        raise ValueError("Uploaded parcel could not be projected into the Bengaluru metric CRS.")
    center_m = parcel_m.centroid
    area_m2 = float(parcel_m.area)
    return center_m, parcel_m, True, area_m2


def _nearby_geoms(kind: str, center_wgs: Point, radius_m: float, limit: int = 200):
    g = nearby_layer(kind, center_wgs.x, center_wgs.y, radius_m, limit)
    return g.to_crs(UTM_CRS) if not g.empty else g


def _nearest_road_access(site_geom, center_wgs: Point, radius_m: float):
    roads = _nearby_geoms("roads", center_wgs, max(radius_m, 250.0), 300)
    if roads.empty:
        return None, None

    nearest_geom = None
    nearest_distance = float("inf")
    nearest_road_row = None

    for _, row in roads.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        distance = geom.distance(site_geom.boundary)
        if distance < nearest_distance:
            nearest_distance = float(distance)
            nearest_geom = geom
            nearest_road_row = row

    if nearest_geom is None:
        return None, None

    _, access_point = nearest_points(nearest_geom, site_geom.boundary)
    return access_point, {
        "name": str(nearest_road_row.get("name") or nearest_road_row.get("highway") or "mapped road"),
        "distance_m": nearest_distance,
    }


def _context_constraints(site_geom, center_wgs: Point, radius_m: float):
    constraints: List[dict] = []
    preserved_geoms = []
    counts = {"water_bodies": 0, "parks": 0, "schools": 0, "hospitals": 0}

    for kind, ft, reason in [
        ("water_bodies", "water_context_zone", "Mapped water-body geometry intersecting the parcel; kept out of conceptual building placement."),
        ("parks", "green_context_zone", "Mapped park geometry intersecting the parcel; preserved as existing green context in the conceptual design."),
    ]:
        g = _nearby_geoms(kind, center_wgs, radius_m, 300)
        if g is None or g.empty:
            continue
        for _, row in g.iterrows():
            geom = row.geometry
            inter = geom.intersection(site_geom)
            if inter.is_empty:
                continue
            counts[kind] += 1
            preserved_geoms.append(inter)
            constraints.append(_feature(
                inter,
                ft,
                reason,
                source_layer=kind,
            ))

    for kind in ["schools", "hospitals"]:
        g = _nearby_geoms(kind, center_wgs, radius_m, 100)
        if g is not None and not g.empty:
            counts[kind] = int(len(g))

    preserved = unary_union(preserved_geoms) if preserved_geoms else GeometryCollection()
    return constraints, preserved, counts


def _make_blocks(inner, restricted, units: int, strategy: str) -> Tuple[List, int, float]:
    profiles = {
        "balanced": {"blocks": max(4, min(8, ceil(max(units, 1) / 100))), "green": 0.25},
        "open_space": {"blocks": max(3, min(6, ceil(max(units, 1) / 140))), "green": 0.38},
        "efficient": {"blocks": max(5, min(10, ceil(max(units, 1) / 80))), "green": 0.18},
    }
    p = profiles.get(strategy, profiles["balanced"])
    block_count = p["blocks"]
    block_capacity = units / block_count if block_count else units

    minx, miny, maxx, maxy = inner.bounds
    width = maxx - minx
    height = maxy - miny
    cols = 4 if block_count >= 7 else 3
    rows = max(2, ceil(block_count / cols))
    bw = width * (0.18 if cols == 4 else 0.22)
    bh = height * (0.20 if rows >= 3 else 0.28)
    blocks = []

    for row in range(rows):
        for col in range(cols):
            if len(blocks) >= block_count:
                break
            cx = minx + width * ((col + 0.5) / cols)
            cy = miny + height * ((row + 0.5) / rows)
            candidate = box(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
            candidate = candidate.intersection(inner).difference(restricted)
            if candidate.is_empty or candidate.area < inner.area * 0.015:
                continue
            blocks.append(candidate)
        if len(blocks) >= block_count:
            break

    # If constraints block too many grid cells, add one fallback block from the largest free rectangle area.
    if not blocks and not inner.difference(restricted).is_empty:
        fallback = inner.difference(restricted)
        if fallback.geom_type in {"Polygon", "MultiPolygon"}:
            blocks = [max(list(fallback.geoms) if isinstance(fallback, MultiPolygon) else [fallback], key=lambda g: g.area)]
            block_count = 1
            block_capacity = units

    return blocks, len(blocks), block_capacity


def _strategy_profile(strategy: str):
    return {
        "balanced": {"green_share": 0.25, "parking_share": 0.10, "label": "Balanced development"},
        "open_space": {"green_share": 0.38, "parking_share": 0.08, "label": "Open-space priority"},
        "efficient": {"green_share": 0.18, "parking_share": 0.12, "label": "Development efficiency"},
    }.get(strategy, {"green_share": 0.25, "parking_share": 0.10, "label": strategy.title()})


def _build_plan(
    site_geom,
    actual_parcel: bool,
    area_m2: float,
    center_m: Point,
    development: Dict[str, Any],
    existing_context: Dict[str, Any],
    planning_rules: Dict[str, Any],
    strategy: str,
):
    units = int(float(development.get("units") or development.get("number_of_units") or 0))
    center_wgs = _to_wgs84(center_m)
    search_radius = max(sqrt(area_m2) * 2.0, 250.0)

    constraint_features, preserved, counts = _context_constraints(site_geom, center_wgs, search_radius)
    access_point, road_info = _nearest_road_access(site_geom, center_wgs, search_radius)

    inner = site_geom.buffer(-max(5.0, min(20.0, sqrt(area_m2) * 0.04)))
    if inner.is_empty:
        inner = site_geom

    # Never place conceptual blocks over explicitly intersecting water/green context.
    restricted = preserved if not preserved.is_empty else GeometryCollection()
    free_inner = inner.difference(restricted)

    if access_point is not None:
        access_line = LineString([access_point, free_inner.centroid])
        access_zone = access_line.buffer(max(4.0, min(8.0, sqrt(area_m2) * 0.02)), cap_style=2).intersection(free_inner)
    else:
        access_line = LineString([(free_inner.centroid.x, free_inner.bounds[1]), free_inner.centroid])
        access_zone = access_line.buffer(max(4.0, min(8.0, sqrt(area_m2) * 0.02)), cap_style=2).intersection(free_inner)

    profile = _strategy_profile(strategy)
    minx, miny, maxx, maxy = site_geom.bounds
    service = box(
        minx + (maxx - minx) * 0.07,
        miny + (maxy - miny) * 0.04,
        maxx - (maxx - minx) * 0.07,
        miny + (maxy - miny) * 0.04 + (maxy - miny) * 0.10,
    ).intersection(free_inner)

    blocks, block_count, block_capacity = _make_blocks(free_inner.difference(service), restricted.union(access_zone), units, strategy)
    building_union = unary_union(blocks) if blocks else GeometryCollection()

    # Green area is placed in the largest clean central zone; exact percentages are design targets only.
    target_green_area = min(free_inner.area * profile["green_share"], free_inner.area * 0.45)
    green_seed = box(
        center_m.x - sqrt(target_green_area) * 0.55,
        center_m.y - sqrt(target_green_area) * 0.55,
        center_m.x + sqrt(target_green_area) * 0.55,
        center_m.y + sqrt(target_green_area) * 0.55,
    )
    green_zone = green_seed.intersection(free_inner).difference(building_union).difference(service).difference(access_zone)
    if not green_zone.is_empty and green_zone.area > target_green_area * 1.25:
        green_zone = green_zone.buffer(0).intersection(free_inner)

    circulation = access_zone

    features: List[dict] = []
    features.append(_feature(
        site_geom,
        "site_boundary",
        "Actual parcel boundary supplied by the user." if actual_parcel else "Conceptual site envelope derived from the supplied site area; not a cadastral boundary.",
        area_m2=round(area_m2, 1),
        boundary_source="uploaded_geojson" if actual_parcel else "conceptual_square",
    ))

    features.extend(constraint_features)

    for i, geom in enumerate(blocks, start=1):
        features.append(_feature(
            geom,
            "building_block",
            f"{profile['label']} option: conceptual building block placed on the clean portion of the site after mapped context constraints.",
            block_id=i,
            units_allocated=round(block_capacity, 1),
            development_type=development.get("type", "residential"),
            strategy=strategy,
        ))

    if not green_zone.is_empty:
        features.append(_feature(
            green_zone,
            "open_green_space",
            "Conceptual open/green area reserved to support internal amenity and spatial separation; this is not a regulatory open-space calculation.",
            target_share=profile["green_share"],
            strategy=strategy,
        ))

    if not service.is_empty:
        features.append(_feature(
            service,
            "service_parking_zone",
            "Conceptual service and parking reservation near one edge of the site; parking supply and fire-access standards still require parcel-specific validation.",
            target_share=profile["parking_share"],
            strategy=strategy,
        ))

    if not circulation.is_empty:
        features.append(_feature(
            circulation,
            "internal_access",
            "Conceptual internal access spine tied to the nearest mapped road context.",
            strategy=strategy,
        ))

    if access_point is not None:
        features.append(_feature(
            access_point.buffer(5.0).intersection(site_geom),
            "entry_zone",
            "Conceptual entry/exit location at the parcel edge nearest the mapped road; not a road-access approval.",
            road_name=road_info["name"] if road_info else "mapped road",
            strategy=strategy,
        ))

    # Explainability / provenance log.
    decisions = []
    decisions.append({
        "decision": "site_boundary",
        "reason": "Use uploaded parcel geometry." if actual_parcel else "Use a square derived from conceptual site area because no parcel geometry was supplied.",
        "evidence": "User input",
    })
    if road_info:
        decisions.append({
            "decision": "access_location",
            "reason": f"Nearest mapped road is {road_info['name']} at {road_info['distance_m']:.1f} m from the parcel boundary.",
            "evidence": "Bengaluru road layer",
        })
    else:
        decisions.append({
            "decision": "access_location",
            "reason": "No nearby road feature was available; access fallback is schematic.",
            "evidence": "Local GIS layer availability",
        })

    if counts["water_bodies"] or counts["parks"]:
        decisions.append({
            "decision": "context_preservation",
            "reason": f"The generator preserved mapped intersecting context: {counts['water_bodies']} water feature(s) and {counts['parks']} park feature(s).",
            "evidence": "Bengaluru GIS layers",
        })
    else:
        decisions.append({
            "decision": "context_preservation",
            "reason": "No mapped water-body or park geometry intersected the parcel in the available local dataset.",
            "evidence": "Bengaluru GIS layers",
        })

    decisions.append({
        "decision": "layout_strategy",
        "reason": f"Applied the {profile['label'].lower()} heuristic for block count and open-space target.",
        "evidence": "Conceptual design heuristic",
    })
    evidence_items = len((planning_rules or {}).get("results", []))
    decisions.append({
        "decision": "planning_evidence",
        "reason": "Planning documents were retrieved for the scenario; numeric rules are not auto-inferred unless directly validated for the site/jurisdiction.",
        "evidence": f"RAG: {evidence_items} evidence item(s)",
    })

    notes = [
        "Conceptual only; not construction-ready and not a regulatory approval.",
        "The generator preserves mapped context features that intersect the parcel but does not invent statutory buffers.",
        "Building placement, block count, green-share targets and parking reservation are visualization heuristics, not building-code calculations.",
        "FAR, setbacks, parking, fire access, coverage, density, zoning and permitted use still require parcel-specific regulatory validation.",
    ]
    if not actual_parcel:
        notes.insert(1, "No actual parcel boundary was supplied; the site envelope is conceptual.")
    if road_info:
        notes.append(f"Conceptual access uses the nearest mapped road context: {road_info['name']} at approximately {road_info['distance_m']:.1f} m from the parcel boundary.")
    if counts["schools"] or counts["hospitals"]:
        notes.append(f"The surrounding context includes {counts['schools']} school feature(s) and {counts['hospitals']} hospital feature(s); these are contextual observations, not service-capacity assessments.")

    return {
        "status": "ok",
        "strategy": strategy,
        "strategy_label": profile["label"],
        "summary": {
            "site_area_m2": round(area_m2, 1),
            "site_side_m": round(sqrt(area_m2), 1),
            "actual_parcel": actual_parcel,
            "units": units,
            "building_blocks": block_count,
            "indicative_units_per_block": round(block_capacity, 1) if block_count else 0,
            "rag_evidence_items": evidence_items,
            "nearest_mapped_road": road_info,
            "context_counts": counts,
            "target_green_share": profile["green_share"],
            "target_parking_share": profile["parking_share"],
        },
        "design": _fc(features),
        "decision_log": decisions,
        "notes": notes,
    }


def generate(
    site: Dict[str, Any],
    development: Dict[str, Any],
    existing_context: Dict[str, Any],
    planning_rules,
    impact_analysis,
    strategy: str = "balanced",
):
    try:
        center_m, site_geom, actual_parcel, area_m2 = _resolve_site(site)
        return _build_plan(
            site_geom,
            actual_parcel,
            area_m2,
            center_m,
            development,
            existing_context,
            planning_rules or {},
            strategy,
        )
    except (ValueError, TypeError) as e:
        return {
            "status": "needs_input",
            "message": str(e),
            "design": None,
        }


def generate_alternatives(
    site: Dict[str, Any],
    development: Dict[str, Any],
    existing_context: Dict[str, Any],
    planning_rules,
    impact_analysis,
):
    center_m, site_geom, actual_parcel, area_m2 = _resolve_site(site)
    strategies = ["balanced", "open_space", "efficient"]
    options = {
        s: _build_plan(
            site_geom,
            actual_parcel,
            area_m2,
            center_m,
            development,
            existing_context,
            planning_rules or {},
            s,
        )
        for s in strategies
    }

    return {
        "status": "ok",
        "site": {
            "actual_parcel": actual_parcel,
            "area_m2": round(area_m2, 1),
            "center": {
                "latitude": round(_to_wgs84(center_m).y, 7),
                "longitude": round(_to_wgs84(center_m).x, 7),
            },
        },
        "constraints": {
            "type": "FeatureCollection",
            "features": [
                f for f in options["balanced"]["design"]["features"]
                if f.get("properties", {}).get("feature_type") in {"water_context_zone", "green_context_zone", "site_boundary"}
            ],
        },
        "alternatives": options,
    }
