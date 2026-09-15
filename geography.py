"""Join explicitly synthetic geography to real demo evidence keys without rewriting evidence."""
import json
import math
import sqlite3
from contextlib import closing
from collections import Counter
from pathlib import Path


def coverage(store, path=None):
    path=Path(path) if path else Path(__file__).parent/'Data'/'geography.json'
    metadata=json.loads(path.read_text())
    if metadata.get('synthetic') is not True:
        raise ValueError('Geography must be labelled synthetic.')
    report=store.report(); latest={}
    for event in store.events():latest.setdefault(event['evidence_key'],event['status'])
    matched={c['contract_id']:c for c in report['contracts']}
    result=[];seen_contracts=set();seen_sites=set()
    with closing(sqlite3.connect(store.db_path)) as db:
        for geo in metadata['contracts']:
            cid=geo['contract_id']
            if cid in seen_contracts or cid not in matched:raise ValueError('Invalid geography contract link.')
            seen_contracts.add(cid);contract=matched[cid]
            if geo['contractor']!=contract['contractor']:raise ValueError('Contractor does not match contract.')
            visits={r[0]:r[1] for r in db.execute('SELECT job_id,status FROM visits WHERE run_id=? AND contract_id=?',(report['run_id'],cid))}
            seen_jobs=set();locations=[]
            for site in geo['locations']:
                if site['site_id'] in seen_sites:raise ValueError('Duplicate geography location.')
                seen_sites.add(site['site_id'])
                lat,lon=site['latitude'],site['longitude']
                if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in (lat,lon)) or not (-90<=lat<=90 and -180<=lon<=180):raise ValueError('Invalid coordinates.')
                for job in site['job_ids']:
                    if job not in visits or job in seen_jobs:raise ValueError('Invalid or repeated geographic visit assignment.')
                    seen_jobs.add(job)
                lines=[r for r in contract['lines'] if r['job_id'] in site['job_ids']]
                flagged=[r for r in lines if r['requires_review']]
                done=sum(latest.get(r['evidence_key']) in {'confirmed_error','valid_charge'} for r in flagged)
                locations.append(dict(site,visit_count=len(site['job_ids']),visit_statuses=dict(Counter(visits[j] for j in site['job_ids'])),
                    invoice_line_count=len(lines),flagged=len(flagged),remaining=len(flagged)-done,
                    known_difference_pence=sum(r['discrepancy_pence'] for r in lines if r['discrepancy_pence'] is not None),
                    unknown_amount_count=sum(r['discrepancy_pence'] is None for r in lines)))
            result.append(dict(geo,locations=locations,unmapped_visits=len(set(visits)-seen_jobs)))
        if seen_contracts!=set(matched):raise ValueError('Geography is missing a contract.')
    return dict(synthetic=True,description=metadata['description'],contracts=result,created_at=report['created_at'])
