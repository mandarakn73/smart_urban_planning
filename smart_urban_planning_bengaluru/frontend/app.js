const $ = id => document.getElementById(id);

const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#039;'
}[c]));

const prettyName = name => String(name ?? '')
  .replace(/_/g, ' ')
  .replace(/\b\w/g, c => c.toUpperCase());

const map = L.map('map').setView([12.9716, 77.5946], 15);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const siteMarker = L.marker([12.9716, 77.5946]).addTo(map);
const radiusCircle = L.circle([12.9716, 77.5946], { radius: 500 }).addTo(map);
const featureLayer = L.layerGroup().addTo(map);
const roadLayer = L.layerGroup().addTo(map);
const designLayer = L.layerGroup().addTo(map);
const constraintLayer = L.layerGroup().addTo(map);
const parcelLayer = L.layerGroup().addTo(map);

let latestContext = null;
let latestSpatial = null;
let latestScenario = null;
let latestParcel = null;
let latestAlternatives = null;
let selectedStrategy = 'balanced';
let latestDesign = null;

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || `HTTP ${r.status}`);
  }
  return r.json();
}

function setStatus(text, kind = 'idle') {
  $('status').textContent = text;
  $('status').className = `status-pill ${kind}`;
}

function clearMapFeatures() {
  featureLayer.clearLayers();
  roadLayer.clearLayers();
}

function clearDesign() {
  designLayer.clearLayers();
}

function markerStyle(kind) {
  const colors = {
    school: '#7c3aed',
    schools: '#7c3aed',
    hospital: '#dc2626',
    hospitals: '#dc2626',
    bus_stop: '#ea580c',
    bus_stops: '#ea580c',
    park: '#16a34a',
    parks: '#16a34a',
    police: '#2563eb',
    fire_stations: '#991b1b',
    buildings: '#64748b',
    pois: '#475467',
    landuse: '#0891b2',
    water_bodies: '#0284c7'
  };
  const color = colors[kind] || '#334155';
  return {
    radius: 6,
    color,
    fillColor: color,
    fillOpacity: 0.85,
    weight: 2
  };
}

function makeGeoJSONFeature(item) {
  if (!item || !item.geometry) return null;
  const geometry = item.geometry;
  if (!geometry.type || !Array.isArray(geometry.coordinates)) return null;
  return {
    type: 'Feature',
    geometry,
    properties: {
      id: item.id ?? '',
      name: item.name ?? '',
      highway: item.highway ?? '',
      distance_m: item.distance_m ?? null
    }
  };
}

function drawContextOnMap(ctx) {
  clearMapFeatures();

  for (const item of (ctx?.roads?.features || [])) {
    const feature = makeGeoJSONFeature(item);
    if (!feature) continue;
    try {
      L.geoJSON(feature, {
        style: {
          color: '#64748b',
          weight: 2,
          opacity: 0.65
        }
      }).addTo(roadLayer);
    } catch (err) {
      console.warn('Skipping invalid road feature:', item, err);
    }
  }

  const categories = [
    'schools',
    'hospitals',
    'bus_stops',
    'parks',
    'police',
    'fire_stations',
    'buildings',
    'pois',
    'landuse',
    'water_bodies'
  ];

  for (const kind of categories) {
    const layer = ctx?.[kind];
    if (!layer || layer.status !== 'ready' || !Array.isArray(layer.features)) continue;

    for (const item of layer.features) {
      const geometry = item?.geometry;
      if (!geometry || geometry.type !== 'Point') continue;

      const coords = geometry.coordinates;
      if (
        !Array.isArray(coords) ||
        coords.length < 2 ||
        typeof coords[0] !== 'number' ||
        typeof coords[1] !== 'number'
      ) continue;

      const marker = L.circleMarker(
        [coords[1], coords[0]],
        markerStyle(kind)
      );

      const name = item.name || prettyName(kind);
      const distance = item.distance_m != null
        ? `${Number(item.distance_m).toFixed(1)} m`
        : '';

      marker.bindPopup(
        `<b>${esc(name)}</b><br>${esc(prettyName(kind))}${distance ? `<br>${distance} from site` : ''}`
      ).addTo(featureLayer);
    }
  }
}


function clearDesign() {
  designLayer.clearLayers();
  constraintLayer.clearLayers();
}

function clearParcel() {
  parcelLayer.clearLayers();
}

function markerStyle(kind) {
  const colors = {
    school: '#7c3aed', schools: '#7c3aed',
    hospital: '#dc2626', hospitals: '#dc2626',
    bus_stop: '#ea580c', bus_stops: '#ea580c',
    park: '#16a34a', parks: '#16a34a',
    police: '#2563eb', fire_stations: '#991b1b',
    buildings: '#64748b', pois: '#475467',
    landuse: '#0891b2', water_bodies: '#0284c7'
  };
  const color = colors[kind] || '#334155';
  return { radius: 6, color, fillColor: color, fillOpacity: 0.85, weight: 2 };
}

function makeGeoJSONFeature(item) {
  if (!item || !item.geometry) return null;
  const geometry = item.geometry;
  if (!geometry.type || !Array.isArray(geometry.coordinates)) return null;
  return {
    type: 'Feature',
    geometry,
    properties: {
      id: item.id ?? '',
      name: item.name ?? '',
      highway: item.highway ?? '',
      distance_m: item.distance_m ?? null
    }
  };
}

function drawContextOnMap(ctx) {
  featureLayer.clearLayers();
  roadLayer.clearLayers();
  for (const item of (ctx?.roads?.features || [])) {
    const feature = makeGeoJSONFeature(item);
    if (!feature) continue;
    try {
      L.geoJSON(feature, { style: { color: '#64748b', weight: 2, opacity: 0.65 } }).addTo(roadLayer);
    } catch (err) {
      console.warn('Skipping invalid road feature:', item, err);
    }
  }
  const categories = ['schools','hospitals','bus_stops','parks','police','fire_stations','buildings','pois','landuse','water_bodies'];
  for (const kind of categories) {
    const layer = ctx?.[kind];
    if (!layer || layer.status !== 'ready' || !Array.isArray(layer.features)) continue;
    for (const item of layer.features) {
      const geometry = item?.geometry;
      if (!geometry || geometry.type !== 'Point') continue;
      const coords = geometry.coordinates;
      if (!Array.isArray(coords) || coords.length < 2 || typeof coords[0] !== 'number' || typeof coords[1] !== 'number') continue;
      const marker = L.circleMarker([coords[1], coords[0]], markerStyle(kind));
      const name = item.name || prettyName(kind);
      const distance = item.distance_m != null ? `${Number(item.distance_m).toFixed(1)} m` : '';
      marker.bindPopup(`<b>${esc(name)}</b><br>${esc(prettyName(kind))}${distance ? `<br>${distance} from site` : ''}`).addTo(featureLayer);
    }
  }
}

function updateSite(lat, lon, radius) {
  siteMarker.setLatLng([lat, lon]);
  radiusCircle.setLatLng([lat, lon]).setRadius(radius);
  map.setView([lat, lon], 15);
  $('siteLabel').textContent = `${lat.toFixed(5)}, ${lon.toFixed(5)} • ${radius} m radius`;
}

function designStyle(feature) {
  const type = feature?.properties?.feature_type;
  const styles = {
    site_boundary: { color:'#0f172a', fillColor:'#cbd5e1', fillOpacity:0.06, weight:3, dashArray:'7 5' },
    building_block: { color:'#1d4ed8', fillColor:'#60a5fa', fillOpacity:0.64, weight:2 },
    open_green_space: { color:'#15803d', fillColor:'#86efac', fillOpacity:0.52, weight:2 },
    service_parking_zone: { color:'#a16207', fillColor:'#fde68a', fillOpacity:0.58, weight:2 },
    internal_access: { color:'#7c3aed', fillColor:'#c4b5fd', fillOpacity:0.40, weight:2 },
    entry_zone: { color:'#ea580c', fillColor:'#fdba74', fillOpacity:0.75, weight:2 },
    water_context_zone: { color:'#0369a1', fillColor:'#38bdf8', fillOpacity:0.50, weight:3, dashArray:'4 4' },
    green_context_zone: { color:'#166534', fillColor:'#4ade80', fillOpacity:0.40, weight:3, dashArray:'4 4' },
  };
  return styles[type] || { color:'#334155', fillColor:'#94a3b8', fillOpacity:0.4, weight:2 };
}

function renderGeoJSONCollection(collection, targetLayer) {
  if (!collection || collection.type !== 'FeatureCollection' || !Array.isArray(collection.features)) return;
  try {
    L.geoJSON(collection, {
      style: designStyle,
      pointToLayer: (_, latlng) => L.circleMarker(latlng, {
        radius: 7, color:'#ea580c', fillColor:'#fb923c', fillOpacity:0.9, weight:2
      }),
      onEachFeature: (feature, layer) => {
        const p = feature?.properties || {};
        const title = prettyName(p.feature_type || 'planning feature');
        const reason = p.reason ? `<br>${esc(p.reason)}` : '';
        const units = p.units_allocated != null ? `<br>Indicative units: ${esc(p.units_allocated)}` : '';
        const source = p.source_layer ? `<br>Source layer: ${esc(p.source_layer)}` : '';
        layer.bindPopup(`<b>${esc(title)}</b>${units}${source}${reason}`);
      }
    }).addTo(targetLayer);
  } catch (err) {
    console.error('Could not render GeoJSON:', err);
    throw err;
  }
}

function renderSelectedPlan() {
  clearDesign();
  if (!latestAlternatives?.alternatives?.[selectedStrategy]) return;
  const option = latestAlternatives.alternatives[selectedStrategy];
  renderGeoJSONCollection(option.design, designLayer);
}

function renderParcelOnMap(parcelGeoJSON) {
  clearParcel();
  if (!parcelGeoJSON) return;
  try {
    const layer = L.geoJSON(parcelGeoJSON, {
      style: { color:'#0f172a', weight:4, dashArray:'5 4', fillColor:'#93c5fd', fillOpacity:0.08 }
    }).addTo(parcelLayer);
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.12));
  } catch (e) {
    console.warn('Could not draw parcel:', e);
  }
}

function contextCards(ctx) {
  const order = ['roads','buildings','schools','hospitals','police','fire_stations','bus_stops','parks','water_bodies','landuse','pois','traffic_events'];
  $('contextCards').innerHTML = order.map(k => {
    const d = ctx?.[k] || { status: 'not_loaded' };
    const status = d.status || 'not_loaded';
    if (status === 'not_loaded') return `<div class="metric-card not-loaded"><div class="label">${esc(prettyName(k))}</div><div class="value">—</div><div class="sub">Layer unavailable</div></div>`;
    const value = d.count ?? 0;
    const sub = value === 0 ? 'Loaded • none found in radius' : (d.truncated ? `${d.displayed_count} displayed • ${value} found in radius` : 'Loaded • within radius');
    return `<div class="metric-card ${value === 0 ? 'zero' : 'ready'}"><div class="label">${esc(prettyName(k))}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`;
  }).join('');
}

function analysisCards(sp) {
  const findings = sp?.findings || {};
  const order = ['schools','hospitals','police','fire_stations','bus_stops','roads','parks','water_bodies','buildings','landuse','traffic_events'];
  $('analysisCards').innerHTML = order.map(k => {
    const d = findings[k] || { status:'not_loaded' };
    const status = d.status || 'not_loaded';
    const count = status === 'not_loaded' ? '—' : (d.count_within_radius ?? 0);
    const nearest = d.nearest_m == null ? 'No feature found' : `${Number(d.nearest_m).toFixed(1)} m nearest`;
    return `<div class="metric-card ${status === 'not_loaded' ? 'not-loaded' : (count === 0 ? 'zero' : 'ready')}"><div class="label">${esc(prettyName(k))}</div><div class="value">${esc(count)}</div><div class="sub">${esc(status === 'not_loaded' ? 'Layer unavailable' : nearest)}</div></div>`;
  }).join('');
  $('analysisNotes').innerHTML = (sp?.notes || []).map(n => `<div class="note">${esc(n)}</div>`).join('');
}

function renderRag(rag) {
  if (!rag) { $('ragContent').innerHTML = '<div class="empty-state">No planning-knowledge response returned.</div>'; return; }
  if (rag.status === 'knowledge_base_empty') { $('ragContent').innerHTML = `<div class="empty-state"><strong>Knowledge base is empty.</strong><br>Add verified Bengaluru planning documents or configure the OpenAI vector store.</div>`; return; }
  if (rag.status === 'not_configured') { $('ragContent').innerHTML = `<div class="empty-state"><strong>OpenAI RAG is not configured.</strong><br>${esc(rag.reason || 'Add OPENAI_API_KEY and OPENAI_VECTOR_STORE_ID to .env.')}</div>`; return; }
  if (rag.status === 'error' && !(rag.results || []).length) { $('ragContent').innerHTML = `<div class="empty-state"><strong>RAG error.</strong><br>${esc(rag.reason || 'Unable to retrieve planning evidence.')}</div>`; return; }
  const provider = rag.provider || 'unknown';
  const answer = rag.answer ? `<div class="rag-answer"><strong>Retrieved planning interpretation</strong><p>${esc(rag.answer)}</p></div>` : '';
  const fallback = rag.fallback_reason ? `<div class="note warn">OpenAI RAG was unavailable, so the local RAG fallback was used.</div>` : '';
  $('ragContent').innerHTML = `<div class="rag-meta">Provider: <b>${esc(provider)}</b> • ${esc(rag.document_count || 0)} document(s) referenced</div>${fallback}${answer}<div class="result-list">${(rag.results || []).map((x,i) => `<div class="result-item"><h3>${i+1}. ${esc(x.document || 'Planning source')} ${x.page ? `• p.${esc(x.page)}` : ''}</h3><p>${esc(x.text || '')}</p>${x.relevance_score != null ? `<small>Relevance ${esc(x.relevance_score)}</small>` : ''}</div>`).join('')}</div>`;
}

function renderScenario(sc) {
  const dev = sc?.development || {}, loc = sc?.location || {}, lim = sc?.limitations || [];
  $('scenarioContent').innerHTML = `<div class="scenario-row"><span>Status</span><span>${esc(sc?.status || 'unknown')}</span></div><div class="scenario-row"><span>Scenario</span><span>${esc(sc?.scenario_type || 'new_development')}</span></div><div class="scenario-row"><span>Development</span><span>${esc(dev.type || '—')}</span></div><div class="scenario-row"><span>Units</span><span>${esc(dev.units ?? '—')}</span></div><div class="scenario-row"><span>Radius</span><span>${esc(sc?.radius_m ?? $('radius').value)} m</span></div><div class="scenario-row"><span>Latitude</span><span>${esc(loc.latitude ?? $('lat').value)}</span></div><div class="scenario-row"><span>Longitude</span><span>${esc(loc.longitude ?? $('lon').value)}</span></div>${lim.map(x => `<div class="note warn">${esc(x)}</div>`).join('')}`;
}

function impactCard(title, body, status) {
  return `<div class="impact-card"><div class="impact-title"><strong>${esc(title)}</strong><span class="tag ${status === 'not_available' || status === 'not_evaluated' ? 'tag-warn' : 'tag-ok'}">${esc(status)}</span></div><div class="impact-body">${body}</div></div>`;
}

function renderImpact(impact) {
  if (!impact) { $('impactContent').innerHTML = '<div class="empty-state">Run an analysis to generate impact findings.</div>'; return; }
  const m=impact.mobility||{}, s=impact.social_infrastructure||{}, e=impact.environment||{}, u=impact.utilities||{}, r=impact.regulatory||{}, b=impact.built_context||{};
  $('impactContent').innerHTML = impactCard('Mobility', `Roads: <b>${esc(m.roads_within_radius ?? '—')}</b> • Bus stops: <b>${esc(m.bus_stops_within_radius ?? '—')}</b> • Traffic-event records: <b>${esc(m.traffic_event_records_within_radius ?? '—')}</b><br><span>${esc(m.interpretation || '')}</span>`, m.status)
    + impactCard('Social infrastructure', `Schools: <b>${esc(s.schools_within_radius ?? '—')}</b> • Hospitals: <b>${esc(s.hospitals_within_radius ?? '—')}</b> • Police: <b>${esc(s.police_within_radius ?? '—')}</b> • Fire: <b>${esc(s.fire_stations_within_radius ?? '—')}</b><br><span>${esc(s.interpretation || '')}</span>`, s.schools_within_radius != null ? 'observed' : 'not_available')
    + impactCard('Environment', `Parks: <b>${esc(e.parks_within_radius ?? '—')}</b> • Water bodies: <b>${esc(e.water_bodies_within_radius ?? '—')}</b><br><span>${esc(e.interpretation || '')}</span>`, 'observed')
    + impactCard('Built context', `Buildings: <b>${esc(b.buildings_within_radius ?? '—')}</b> • Land use features: <b>${esc(b.landuse_within_radius ?? '—')}</b>`, 'observed')
    + impactCard('Utilities', `<span>${esc(u.interpretation || 'Utility datasets not loaded.')}</span>`, 'not_available')
    + impactCard('Regulatory feasibility', `Knowledge base: <b>${esc(r.knowledge_base_status || 'unknown')}</b><br><span>${esc(r.interpretation || '')}</span>`, r.status);
}

function optionTitle(strategy) {
  return { balanced:'Balanced development', open_space:'Open-space priority', efficient:'Development efficiency' }[strategy] || strategy;
}

function renderAlternatives(result) {
  if (!result?.alternatives) return;
  latestAlternatives = result;
  const labels = { balanced:'Balanced development', open_space:'Open-space priority', efficient:'Development efficiency' };
  $('alternativeContent').innerHTML = `<div class="alternatives-grid">${Object.entries(result.alternatives).map(([key, opt]) => {
    const s=opt.summary||{};
    return `<button class="alternative-card ${key===selectedStrategy?'selected':''}" data-strategy="${esc(key)}"><div class="alt-head"><strong>${esc(labels[key]||key)}</strong><span>${key===selectedStrategy?'Selected':'View'}</span></div><div class="alt-stats"><div><b>${esc(s.building_blocks??'—')}</b><small>Blocks</small></div><div><b>${esc(s.indicative_units_per_block??'—')}</b><small>Units/block</small></div><div><b>${Math.round(Number(s.target_green_share||0)*100)}%</b><small>Green target</small></div><div><b>${s.actual_parcel?'Yes':'No'}</b><small>Actual parcel</small></div></div><p>${esc((opt.notes||[])[0]||'Conceptual planning option.')}</p></button>`;
  }).join('')}</div>`;

  document.querySelectorAll('.alternative-card').forEach(btn => {
    btn.onclick = () => {
      selectedStrategy = btn.dataset.strategy;
      renderAlternatives(latestAlternatives);
      renderSelectedPlan();
      renderDecisionLog();
      $('designStatus').textContent = `${optionTitle(selectedStrategy)} selected`;
    };
  });

  renderDecisionLog();
  renderSelectedPlan();
}

function renderDecisionLog() {
  const option = latestAlternatives?.alternatives?.[selectedStrategy];
  if (!option) return;
  const s = option.summary || {};
  $('designContent').innerHTML = `<div class="design-summary-grid"><div class="design-stat"><span>Site area</span><strong>${esc(s.site_area_m2??'—')} m²</strong></div><div class="design-stat"><span>Actual parcel</span><strong>${s.actual_parcel?'Yes':'No'}</strong></div><div class="design-stat"><span>Units</span><strong>${esc(s.units??'—')}</strong></div><div class="design-stat"><span>Building blocks</span><strong>${esc(s.building_blocks??'—')}</strong></div><div class="design-stat"><span>Indicative units / block</span><strong>${esc(s.indicative_units_per_block??'—')}</strong></div><div class="design-stat"><span>RAG evidence items</span><strong>${esc(s.rag_evidence_items??'—')}</strong></div></div><div class="design-note"><b>${esc(option.strategy_label||selectedStrategy)}</b><br>${s.nearest_mapped_road ? `Nearest mapped road context: <b>${esc(s.nearest_mapped_road.name)}</b> • ${esc(Number(s.nearest_mapped_road.distance_m).toFixed(1))} m.` : 'No mapped road was available for data-informed access.'}</div><div class="design-legend"><span><i class="plan-swatch boundary"></i>Site boundary</span><span><i class="plan-swatch building"></i>Building blocks</span><span><i class="plan-swatch green"></i>Open / green</span><span><i class="plan-swatch parking"></i>Service / parking</span><span><i class="plan-swatch access"></i>Internal access</span><span><i class="plan-swatch constraint"></i>Mapped constraint</span></div><div class="notes">${(option.notes||[]).map(n=>`<div class="note warn">${esc(n)}</div>`).join('')}</div>`;

  const decisions = option.decision_log || [];
  $('decisionContent').innerHTML = `<h3 class="decision-title">Why this option was generated</h3><div class="decision-list">${decisions.map(d=>`<div class="decision-item"><strong>${esc(prettyName(d.decision||'decision'))}</strong><span>${esc(d.reason||'')}</span><small>Evidence: ${esc(d.evidence||'')}</small></div>`).join('')}</div>`;
}

function buildSitePayload() {
  const lat = Number($('lat').value), lon = Number($('lon').value), area = Number($('siteArea').value);
  if (latestParcel) {
    return { parcel_geojson: latestParcel };
  }
  return { center: { latitude: lat, longitude: lon }, area_m2: area };
}

function makeReportPayload() {
  return {
    scenario: latestScenario || {},
    spatial: latestSpatial || {},
    impact_analysis: latestScenario?.impact_analysis || {},
    planning_knowledge: latestScenario?.planning_knowledge || {},
    alternatives: latestAlternatives?.alternatives || {}
  };
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadText(text, filename, type) {
  downloadBlob(new Blob([text], {type}), filename);
}

async function uploadParcel() {
  const file = $('parcelFile').files?.[0];
  if (!file) { $('parcelStatus').textContent = 'Choose a GeoJSON file first'; return; }
  $('parcelBtn').disabled = true;
  $('parcelStatus').textContent = 'Uploading…';
  try {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/parcel/upload', { method:'POST', body:fd });
    if (!r.ok) throw new Error(await r.text());
    const out = await r.json();
    latestParcel = out.parcel_geojson;
    $('siteArea').value = Math.max(1000, Math.round(Number(out.area_m2)));
    $('lat').value = Number(out.centroid.latitude).toFixed(7);
    $('lon').value = Number(out.centroid.longitude).toFixed(7);
    $('parcelStatus').textContent = `Loaded • ${Math.round(out.area_m2).toLocaleString()} m²`;
    renderParcelOnMap(latestParcel);
    clearDesign();
    $('designBtn').disabled = true;
    $('geojsonBtn').disabled = true;
    $('planJsonBtn').disabled = true;
    $('reportPdfBtn').disabled = true;
    $('reportHtmlBtn').disabled = true;
    $('designStatus').textContent = 'Parcel loaded — re-run analysis';
  } catch (e) {
    latestParcel = null;
    $('parcelStatus').textContent = 'Upload failed';
    alert(`Parcel upload failed: ${e.message}`);
  } finally {
    $('parcelBtn').disabled = false;
  }
}

async function generateAlternatives() {
  if (!latestContext || !latestScenario) {
    $('designContent').innerHTML = '<div class="empty-state">Run Analyze Site first.</div>';
    return;
  }
  const area = Number($('siteArea').value);
  if (!latestParcel && (!Number.isFinite(area) || area <= 0)) {
    $('designContent').innerHTML = '<div class="empty-state"><strong>Enter a valid conceptual site area or upload a parcel.</strong></div>';
    return;
  }
  $('designBtn').disabled = true;
  $('designBtn').textContent = 'Generating…';
  $('designStatus').textContent = 'Generating alternatives…';
  try {
    const result = await post('/design/alternatives', {
      site: buildSitePayload(),
      development: latestScenario.development || { type:$('dev').value, units:Number($('units').value) },
      existing_context: latestContext,
      planning_rules: latestScenario.planning_knowledge || {},
      impact_analysis: latestScenario.impact_analysis || {}
    });
    latestAlternatives = result;
    selectedStrategy = 'balanced';
    renderAlternatives(result);
    $('designStatus').textContent = '3 options generated';
    $('geojsonBtn').disabled = false;
    $('planJsonBtn').disabled = false;
    $('reportPdfBtn').disabled = false;
    $('reportHtmlBtn').disabled = false;
  } catch (e) {
    $('designContent').innerHTML = `<div class="empty-state"><strong>Design generation failed.</strong><br>${esc(e.message)}</div>`;
    $('designStatus').textContent = 'Error';
  } finally {
    $('designBtn').disabled = false;
    $('designBtn').textContent = 'Generate 3 Planning Options';
  }
}

async function downloadSelectedGeoJSON() {
  const option = latestAlternatives?.alternatives?.[selectedStrategy];
  if (!option) return;
  const payload = JSON.stringify(option.design, null, 2);
  downloadText(payload, `bengaluru_${selectedStrategy}_concept_plan.geojson`, 'application/geo+json');
}

async function downloadPlanJSON() {
  if (!latestAlternatives) return;
  const payload = { selected_strategy:selectedStrategy, alternatives:latestAlternatives, scenario:latestScenario, spatial:latestSpatial };
  downloadText(JSON.stringify(payload, null, 2), 'bengaluru_planning_options.json', 'application/json');
}

async function downloadReportPDF() {
  if (!latestAlternatives) return;
  const r = await fetch('/report/pdf', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(makeReportPayload()) });
  if (!r.ok) throw new Error(await r.text());
  downloadBlob(await r.blob(), 'smart_urban_planning_bengaluru_report.pdf');
}

async function openReportHTML() {
  if (!latestAlternatives) return;
  const reportWindow = window.open('', '_blank');
  if (!reportWindow) { alert('Allow pop-ups for the planning report.'); return; }
  reportWindow.document.write('<p style="font-family:Arial;padding:30px">Building report…</p>');
  const r = await fetch('/report/html', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(makeReportPayload()) });
  if (!r.ok) { reportWindow.close(); throw new Error(await r.text()); }
  reportWindow.document.open();
  reportWindow.document.write(await r.text());
  reportWindow.document.close();
}

$('parcelBtn').onclick = uploadParcel;
$('designBtn').onclick = generateAlternatives;
$('geojsonBtn').onclick = downloadSelectedGeoJSON;
$('planJsonBtn').onclick = downloadPlanJSON;
$('reportPdfBtn').onclick = () => downloadReportPDF().catch(e => alert(`Report download failed: ${e.message}`));
$('reportHtmlBtn').onclick = () => openReportHTML().catch(e => alert(`Report failed: ${e.message}`));

$('run').onclick = async () => {
  const lat = Number($('lat').value), lon = Number($('lon').value), radius = Number($('radius').value), dev = $('dev').value, units = Number($('units').value);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(radius) || !Number.isFinite(units) || lat < -90 || lat > 90 || lon < -180 || lon > 180 || radius <= 0 || units <= 0) {
    setStatus('Enter valid site values.', 'error'); return;
  }
  $('run').disabled = true;
  $('designBtn').disabled = true;
  $('geojsonBtn').disabled = true;
  $('planJsonBtn').disabled = true;
  $('reportPdfBtn').disabled = true;
  $('reportHtmlBtn').disabled = true;
  setStatus('Analyzing…', 'running');
  updateSite(lat, lon, radius);
  clearDesign();
  latestAlternatives = null;
  $('designStatus').textContent = 'Waiting for analysis';
  $('designContent').innerHTML = '<div class="empty-state">Run analysis, then generate planning alternatives.</div>';
  try {
    const [ctx, sp, sc] = await Promise.all([
      post('/digital-twin/context', { latitude:lat, longitude:lon, radius_m:radius }),
      post('/spatial/analyze', { latitude:lat, longitude:lon, radius_m:radius, development_type:dev }),
      post('/scenario/analyze', { latitude:lat, longitude:lon, radius_m:radius, location:{latitude:lat,longitude:lon}, development:{type:dev,units} })
    ]);
    latestContext = ctx; latestSpatial = sp; latestScenario = sc;
    contextCards(ctx); analysisCards(sp); renderRag(sc.planning_knowledge); renderScenario(sc); renderImpact(sc.impact_analysis); drawContextOnMap(ctx);
    if (latestParcel) renderParcelOnMap(latestParcel);
    $('designBtn').disabled = false;
    $('designStatus').textContent = 'Ready to generate';
    setStatus('Analysis complete', 'success');
  } catch (e) {
    setStatus(`Error: ${e.message}`, 'error');
    $('designStatus').textContent = 'Unavailable';
  } finally {
    $('run').disabled = false;
  }
};
