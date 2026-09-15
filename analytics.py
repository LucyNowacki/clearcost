"""Read-only planning metrics from the current reconciliation run and latest reviews."""
import json
import sqlite3
from collections import Counter
from contextlib import closing


def analyse(store):
    report = store.report()
    latest = {}
    for event in store.events():
        latest.setdefault(event['evidence_key'], event)
    result = []
    with closing(sqlite3.connect(store.db_path)) as db:
        for c in report['contracts']:
            key = (report['run_id'], c['contract_id'])
            raw = db.execute('SELECT terms_json FROM contracts WHERE run_id=? AND contract_id=?', key).fetchone()
            if raw is None:
                raise ValueError('Current report has no matching stored contract.')
            terms = json.loads(raw[0])
            records = [json.loads(r[0]) for r in db.execute('SELECT record_json FROM visits WHERE run_id=? AND contract_id=?', key)]
            visits = Counter(r['status'] for r in records)
            daily = Counter(r['service_date'] for r in records)
            completed_daily = Counter(r['service_date'] for r in records if r['status'] == 'completed')
            flagged = [r for r in c['lines'] if r['requires_review']]
            statuses = Counter(latest.get(r['evidence_key'], {}).get('status', 'needs_review') for r in flagged)
            done = statuses['confirmed_error'] + statuses['valid_charge']
            open_rows = [r for r in flagged if latest.get(r['evidence_key'], {}).get('status', 'needs_review') not in {'confirmed_error', 'valid_charge'}]
            result.append(dict(contract_id=c['contract_id'], contractor=c['contractor'], summary=c['summary'],
                daily_visits=dict(sorted(daily.items())), daily_completed=dict(sorted(completed_daily.items())),
                visits=dict(visits), visit_count=sum(visits.values()), statuses=dict(statuses), completed=done,
                remaining=len(flagged)-done, progress=100*done/len(flagged) if flagged else None,
                outstanding_known_difference_pence=sum(r['discrepancy_pence'] for r in open_rows if r['discrepancy_pence'] is not None),
                issues=dict(Counter(issue for r in flagged for issue in r['issues'])),
                terms={k:terms[k] for k in ('standard_rate_pence','cancelled_rate_pence','period_start','period_end','service_type')},
                approved_supplement_count=len(terms['approvals'])))
    return dict(created_at=report['created_at'], contracts=result)
