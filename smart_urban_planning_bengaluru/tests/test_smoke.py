from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    r=client.get('/health')
    assert r.status_code==200

def test_domains():
    r=client.get('/domains')
    assert r.status_code==200
    assert 'domains' in r.json()

def test_context_count_not_display_cap():
    r=client.post('/digital-twin/context',json={'latitude':12.9716,'longitude':77.5946,'radius_m':500})
    assert r.status_code==200
    roads=r.json()['roads']
    assert roads['status']=='ready'
    assert roads['count'] >= roads['displayed_count']
    assert roads['displayed_count'] <= 50

def test_building_layer_excludes_poi_points():
    r=client.post('/digital-twin/context',json={'latitude':12.9716,'longitude':77.5946,'radius_m':500})
    assert r.status_code==200
    for f in r.json()['buildings']['features']:
        assert f['geometry']['type'] in {'Polygon','MultiPolygon'}

def test_scenario_uses_requested_radius():
    r=client.post('/scenario/analyze',json={'latitude':12.9716,'longitude':77.5946,'radius_m':750,'location':{'latitude':12.9716,'longitude':77.5946},'development':{'type':'residential','units':500}})
    assert r.status_code==200
    assert r.json()['radius_m']==750

def test_scenario_parser_normalizes_industry():
    r=client.post('/scenario/parse',json={'query':'Build 500 units industry at 12.9716, 77.5946'})
    assert r.status_code==200
    assert r.json()['development_type']=='industrial'
    assert r.json()['location']['longitude']==77.5946
