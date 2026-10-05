$ErrorActionPreference='Stop'
if (!(Test-Path '.venv')) { py -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (!(Test-Path 'data/raw/export.geojson')) { Write-Host 'Copy the road-heavy Bengaluru export.geojson into data/raw/export.geojson first.'; exit 1 }
if (Test-Path 'data/raw/export_poi.geojson') {
  python scripts/prepare_data.py --osm data/raw/export.geojson data/raw/export_poi.geojson --traffic data/raw/bengaluru_traffic_events.csv
} else {
  python scripts/prepare_data.py --osm data/raw/export.geojson --traffic data/raw/bengaluru_traffic_events.csv
}
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
