# Smart Urban Planning Assistant – Bengaluru

A location-aware urban planning research prototype combining Bengaluru GIS/OSM context, spatial analysis, planning-document RAG, cross-domain impact interpretation, constraint-aware conceptual design, alternative generation, explainable planning decisions, report export and n8n orchestration.

## End-to-end workflow

```text
User location + proposed development
        ↓
Digital Twin / GIS context
        ↓
Spatial proximity analysis
        ↓
Planning Knowledge RAG
        ↓
Scenario + cross-domain impact analysis
        ↓
Actual parcel (optional but preferred)
        ↓
Mapped context constraints
        ↓
Constraint-aware design generation
        ↓
3 conceptual alternatives
        ↓
Explainable design decisions
        ↓
GeoJSON / JSON / PDF report export
        ↓
n8n orchestration
```

## Important scope

This is a **research visualization prototype**, not a cadastral survey system, construction drawing generator or statutory approval engine. The design generator intentionally distinguishes observed GIS evidence, retrieved planning evidence, design heuristics and unavailable data.

Numeric FAR, setbacks, parking, fire-access, coverage, density and zoning values are not treated as automatically applicable legal answers for a parcel. They require site-specific verification against authoritative and current planning instruments.

## New capabilities in this final version

### 1. Actual parcel boundary
Upload a **WGS84 GeoJSON Polygon/MultiPolygon** from the Planning Design Studio. The parcel replaces the old assumed square envelope.

### 2. Constraint-aware planning
The generator checks mapped park and water geometries that intersect the parcel and preserves those geometries in the conceptual plan. It does **not** invent statutory buffers. Nearby schools and hospitals are retained as contextual observations rather than legal exclusion zones.

### 3. Multiple planning alternatives
The system creates:

- **Balanced development** – medium open-space target and block density.
- **Open-space priority** – fewer blocks and a larger conceptual open-space target.
- **Development efficiency** – more blocks and a smaller conceptual open-space target.

These are planning heuristics for comparison, not code calculations.

### 4. Explainable design decisions
Each alternative records why it selected:

- the parcel or conceptual envelope;
- the access location;
- preservation of mapped context;
- the chosen layout strategy;
- the use of retrieved planning evidence.

### 5. Planning report
The UI can open a report in the browser or download a PDF containing site information, spatial findings, impact interpretation, planning evidence, alternatives and limitations.

### 6. Exportable plan
The selected conceptual plan can be downloaded as GeoJSON and the complete alternatives package as JSON. GeoJSON can be opened in QGIS, ArcGIS or processed with GeoPandas.

### 7. n8n orchestration
`n8n/workflow_smart_urban_planning_bengaluru.json` orchestrates:

`Planner Webhook → Planner Orchestrator → Scenario Parse → Digital Twin → Spatial Analysis → Planning RAG → Scenario + Impact → Constraint-Aware Design Alternatives → Planning Report → Planner Response`

Set `BACKEND_URL` in n8n to the reachable FastAPI instance.

## Windows CMD setup

```cmd
cd C:\Users\manda\Desktop\smart_urban_planning_bengaluru
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts\prepare_data.py --osm data\raw\export.geojson data\raw\export_poi.geojson --traffic data\raw\bengaluru_traffic_events.csv
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

`http://127.0.0.1:8000`

## Typical use

1. Enter the Bengaluru location, radius, development type and units.
2. Click **Analyze Site**.
3. Optionally upload the actual parcel GeoJSON.
4. Re-run **Analyze Site** after changing the parcel/location.
5. Click **Generate 3 Planning Options**.
6. Select Balanced, Open-space priority or Development efficiency.
7. Review the map, constraint zones and explainable design decisions.
8. Download the selected GeoJSON / full plan JSON / PDF planning report.

## API additions

- `POST /parcel/upload` — upload and validate a parcel GeoJSON.
- `GET /parcel/current` — retrieve the persisted parcel when present.
- `POST /design/generate` — generate one conceptual design.
- `POST /design/alternatives` — generate the three planning alternatives.
- `POST /report/pdf` — generate a PDF planning report.
- `POST /report/html` — generate a browser-readable planning report.

## Data notes

The prototype uses the processed Bengaluru GeoPackage generated from the supplied OSM extracts and traffic-event CSV. The traffic-event dataset should not be interpreted as a continuous traffic-flow or congestion dataset.

The local planning RAG indexes the planning documents under `data/documents/`. The RMP 2031 Volume 1 file is a draft/background source. Government notifications and zonal-regulation sources should be checked for jurisdiction and effective date before using them for a real planning decision.

## Research-quality limitations

- OSM completeness and currency may vary by feature class.
- Utility demand/capacity calculations require validated local utility data and explicit demand assumptions.
- Existing park/water geometries are treated as contextual constraints only when they intersect the parcel; no unsupported statutory distance buffer is invented.
- Conceptual block dimensions and green/parking shares are heuristics.
- Professional survey, cadastral boundary, current zoning, detailed engineering and statutory approval checks remain outside the prototype.
