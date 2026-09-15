import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from reconcile import run
from dashboard import ReviewStore
from geography import coverage

ROOT=Path(__file__).resolve().parents[1]
class GeographyTests(unittest.TestCase):
    def test_coverage_and_bad_links(self):
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'db';report=Path(tmp)/'report.json'
            run(ROOT/'Data'/'Contracts',db,report);store=ReviewStore(db,report)
            cs=coverage(store)['contracts'];sites=[s for c in cs for s in c['locations']]
            self.assertEqual(len(sites),15)
            self.assertEqual(sum(s['visit_count'] for s in sites),75)
            self.assertEqual(sum(s['invoice_line_count'] for s in sites),80)
            self.assertEqual(sum(s['remaining'] for s in sites),20)
            self.assertEqual(sum(s['known_difference_pence'] for s in sites),98700)
            self.assertEqual(sum(c['unmapped_visits'] for c in cs),0)
            meta=json.loads((ROOT/'Data/geography.json').read_text())
            meta['contracts'][0]['locations'][1]['job_ids'].append(meta['contracts'][0]['locations'][0]['job_ids'][0])
            bad=Path(tmp)/'bad.json';bad.write_text(json.dumps(meta))
            with self.assertRaises(ValueError):coverage(store,bad)
