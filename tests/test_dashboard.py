import json
import tempfile
import unittest
from pathlib import Path
from dashboard import ReviewStore

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.report = root / 'report.json'
        self.report.write_text(json.dumps({'contracts': [{'contract_id': 'C1', 'sources': {'contract': 'hash1'}, 'lines': [{'line_id': 'L1', 'discrepancy_pence': 500}]}]}))
        self.store = ReviewStore(root / 'test.sqlite3', self.report)
        self.data = dict(evidence_key=self.store.report()['contracts'][0]['lines'][0]['evidence_key'], status='confirmed_error', reviewer='Demo reviewer', note='Rate checked against contract.', expected_version=0)

    def test_persistence_and_append_only_history(self):
        self.store.save(self.data)
        reopened = ReviewStore(self.store.db_path, self.report)
        event = reopened.events()[0]
        self.assertEqual(event['note'], self.data['note'])
        reopened.save(dict(self.data, expected_version=event['id'], status='awaiting_evidence'))
        self.assertEqual(len(reopened.events()), 2)
        self.assertEqual(reopened.events()[1]['status'], 'confirmed_error')

    def test_concurrent_edit_rejected(self):
        self.store.save(self.data)
        with self.assertRaisesRegex(ValueError, 'Another review'):
            self.store.save(dict(self.data, note='A different conclusion.'))
        self.assertEqual(len(self.store.events()), 1)

    def test_changed_evidence_rejected(self):
        report = json.loads(self.report.read_text())
        report['contracts'][0]['sources']['contract'] = 'changed'
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Evidence changed'):
            self.store.save(self.data)

    def test_reason_and_reviewer_required(self):
        for field in ['note', 'reviewer']:
            with self.assertRaises(ValueError):
                self.store.save(dict(self.data, **{field: ''}))

    def test_identical_report_keeps_evidence_key(self):
        self.assertEqual(self.data['evidence_key'], self.store.report()['contracts'][0]['lines'][0]['evidence_key'])

    def test_identical_save_is_noop_even_when_retried(self):
        self.store.save(self.data)
        self.assertTrue(self.store.save(self.data)['unchanged'])
        event = self.store.events()[0]
        self.assertTrue(self.store.save(dict(self.data, expected_version=event['id'], note='  '+self.data['note']+'  '))['unchanged'])
        self.assertEqual(len(self.store.events()), 1)
