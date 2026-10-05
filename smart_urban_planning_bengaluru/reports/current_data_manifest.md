# Current data manifest (verified from uploaded workspace)

## Bengaluru OSM: `export.geojson`
- Size: ~99.6 MB
- Features: 153,230
- CRS: EPSG:4326
- Geometry: 153,026 LineString + 204 Polygon
- Highway tags: populated for 153,230 features; dominant class is `residential`
- Building-tagged features: 7
- Amenity-tagged features: 9
- Landuse-tagged features: 1
- This file is therefore best treated as a road/highway-heavy OSM extract, not a complete Bengaluru POI/building dataset.

## Bengaluru traffic events: `bengaluru_traffic_events.csv`
- 50 records
- 9 columns
- Includes latitude/longitude, alertType, junctionName, vehicleType, cameraUsage, observationDateTime
- Suitable for traffic-event/junction-context analysis.
- Not sufficient by itself for speed/flow prediction.

## PEMS-BAY metadata: `PEMS-BAY-META(1).csv`
- 325 sensor metadata records
- Coordinates are in California/Bay Area (e.g. ~37N, -121W)
- Excluded from Bengaluru analysis.

## Current PDFs in workspace
The visible PDFs are research papers, not official Bengaluru planning regulations. They are kept out of the planning-rule RAG by design.
