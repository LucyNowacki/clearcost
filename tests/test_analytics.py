import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from reconcile import run
from dashboard import ReviewStore
from analytics import analyse

class AnalyticsTests(unittest.TestCase):
    def test_current_run_counts_and_latest_review(self):
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite'; report=Path(tmp)/'report.json'
            run(Path(__file__).resolve().parents[1]/'Data'/'Contracts',db,report)
            store=ReviewStore(db,report)
            data=analyse(store)['contracts']
            self.assertEqual(sum(c['visit_count'] for c in data),75)
            self.assertEqual(sum(sum(c['daily_visits'].values()) for c in data),75)
            self.assertEqual(sum(sum(c['daily_completed'].values()) for c in data),60)
            self.assertEqual(sum(c['summary']['invoice_line_count'] for c in data),80)
            self.assertEqual(sum(c['summary']['known_discrepancy_total_pence'] for c in data),98700)
            self.assertEqual(sum(c['remaining'] for c in data),20)
            line=store.report()['contracts'][0]['lines'][0]
            request=dict(evidence_key=line['evidence_key'],status='confirmed_error',reviewer='Test',note='Checked',expected_version=0)
            store.save(request)
            self.assertEqual(analyse(store)['contracts'][0]['completed'],1)
            request.update(status='needs_review',expected_version=store.events()[0]['id'])
            store.save(request)
            self.assertEqual(analyse(store)['contracts'][0]['completed'],0)
            self.assertEqual(analyse(store)['contracts'][0]['remaining'],4)
