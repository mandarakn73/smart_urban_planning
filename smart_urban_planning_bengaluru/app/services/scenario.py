from typing import Dict, Any


def analyze(location: Dict[str,float], development: Dict[str,Any], radius_m: float, context: Dict[str,Any], spatial: Dict[str,Any], rag_result: Dict[str,Any], impact: Dict[str,Any]):
    units=development.get('units') or development.get('number_of_units')
    result={
        'status':'ok',
        'scenario_type':'new_development',
        'location':location,
        'radius_m':radius_m,
        'development':development,
        'observed_context_summary':{
            k:{'status':v.get('status'),'count':v.get('count'),'displayed_count':v.get('displayed_count')}
            for k,v in context.items() if isinstance(v,dict)
        },
        'derived_spatial_findings':spatial,
        'planning_knowledge':rag_result,
        'impact_analysis':impact,
        'estimates':{},
        'limitations':[]
    }
    if units is not None:
        try:
            units=float(units)
            result['estimates']['estimated_units']=units
            result['limitations'].append('Population, water and energy demand are not estimated without a documented local assumption or validated dataset.')
        except Exception:
            result['limitations'].append('Development scale could not be parsed as a numeric value.')
    else:
        result['limitations'].append('Development scale not provided; demand-impact estimation is limited.')
    if not rag_result.get('results'):
        result['limitations'].append('Regulatory feasibility is not evaluated because no applicable planning-rule evidence was retrieved.')
    return result


def compare(scenarios):
    return {'status':'ok','scenarios':scenarios,'comparison_method':'Structured side-by-side comparison. Quantitative differences are only produced when supported by supplied values; no unsupported traffic, utility or regulatory scores are fabricated.'}
