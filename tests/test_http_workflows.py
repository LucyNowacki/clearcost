from contextlib import closing
"""Full HTTP workflows using disposable databases and source copies."""
import http.client
import json
import shutil
import sqlite3
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import dashboard
from reconcile import run

ROOT=Path(__file__).resolve().parents[1]
class HttpWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'Data',self.root/'Data');shutil.copytree(ROOT/'web',self.root/'web')
        self.db=self.root/'output/db.sqlite';self.report=self.root/'output/report.json'
        run(self.root/'Data/Contracts',self.db,self.report)
        self.root_patch=patch.object(dashboard,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.store=dashboard.ReviewStore(self.db,self.report)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),dashboard.handler(self.store))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            h={'Content-Type':'application/json'};h.update(headers or {})
            c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),h)
            r=c.getresponse();payload=r.read();return r.status,payload
        finally:c.close()
    def read(self,path):
        status,body=self.request(path);self.assertEqual(status,200,body);return json.loads(body)
    def draft(self):
        contract=self.read('/api/report')['contracts'][0]
        folder=self.root/'Data/Contracts'/contract['scenario_folder'];llm=self.root/'output/llm';llm.mkdir(exist_ok=True)
        import hashlib
        draft=dict(status='draft_needs_human_review',source=str(folder/'contract.pdf'),source_sha256=hashlib.sha256((folder/'contract.pdf').read_bytes()).hexdigest(),model='test',created_at='2026-09-15',extraction={'terms':[],'warnings':[]})
        (llm/'test.json').write_text(json.dumps(draft));return folder,llm
    def test_pages_and_all_contractor_totals(self):
        for path in ['/','/analysis','/geography','/extractions','/guidance','/readme']:
            self.assertEqual(self.request(path)[0],200,path)
        report=self.read('/api/report');analysis=self.read('/api/analysis');geo=self.read('/api/geography')
        self.assertEqual(len(geo['contracts']),5)
        for c,a,g in zip(report['contracts'],analysis['contracts'],geo['contracts']):
            self.assertEqual(c['contract_id'],a['contract_id']);self.assertEqual(c['contract_id'],g['contract_id'])
            self.assertEqual(sum(s['invoice_line_count'] for s in g['locations']),c['summary']['invoice_line_count'])
            self.assertEqual(sum(s['known_difference_pence'] for s in g['locations']),c['summary']['known_discrepancy_total_pence'])
            self.assertEqual(sum(a['daily_visits'].values()),15)
            self.assertEqual(self.request('/api/document?contract='+c['contract_id']+'&kind=contract')[1][:4],b'%PDF')
    def test_save_retry_reopen_and_cross_page_progress(self):
        line=self.read('/api/report')['contracts'][0]['lines'][0]
        data=dict(evidence_key=line['evidence_key'],status='confirmed_error',reviewer='QA only',note='Verified synthetic rate',expected_version=0)
        self.assertEqual(self.request('/api/reviews',data)[0],200)
        self.assertTrue(json.loads(self.request('/api/reviews',data)[1])['unchanged'])
        events=self.read('/api/reviews');self.assertEqual(len(events),1)
        self.assertEqual(dashboard.ReviewStore(self.db,self.report).events(),events)
        self.assertEqual(self.read('/api/analysis')['contracts'][0]['completed'],1)
        self.assertEqual(sum(s['remaining'] for s in self.read('/api/geography')['contracts'][0]['locations']),3)
        self.assertEqual(self.request('/api/reviews',dict(data,note='Stale different edit'))[0],400)
        self.assertEqual(len(self.read('/api/reviews')),1)
        data.update(status='awaiting_evidence',expected_version=events[0]['id'])
        self.assertEqual(self.request('/api/reviews',data)[0],200)
        self.assertEqual(self.read('/api/analysis')['contracts'][0]['completed'],0)
        self.assertEqual(len(self.read('/api/reviews')),2)
    def test_invalid_requests_and_local_boundary(self):
        self.assertEqual(self.request('/api/reviews',[])[0],400)
        self.assertEqual(self.request('/api/reviews',{'status':[]})[0],400)
        self.assertEqual(self.request('/api/report',headers={'Host':'outside.example'})[0],403)
        self.assertEqual(self.request('/api/reviews',{},headers={'Origin':'https://outside.example'})[0],403)
        self.assertEqual(self.request('/api/document?contract=../../private&kind=contract')[0],404)
    def test_stale_extraction_does_not_supply_evidence(self):
        folder,_=self.draft();(folder/'contract.pdf').write_bytes((folder/'contract.pdf').read_bytes()+b'\nchanged')
        link=self.read('/api/extraction-links')['CTR-002']
        self.assertEqual(link['status'],'stale');self.assertEqual(link['findings'],{})
        self.assertIn(b'STALE SOURCE',self.request('/extractions')[1])
    def test_damaged_draft_does_not_hide_valid_draft(self):
        _,llm=self.draft();(llm/'broken.json').write_text('{');(llm/'wrong-shape.json').write_text('[]')
        self.assertIn('CTR-002',self.read('/api/extraction-links'))
        status,body=self.request('/extractions');self.assertEqual(status,200);self.assertIn(b'skipped',body)
    def test_missing_report_returns_error_not_disconnect(self):
        self.report.unlink();status,body=self.request('/api/report')
        self.assertEqual(status,500);self.assertIn('error',json.loads(body))
        data=dict(status='needs_review',reviewer='QA',note='',evidence_key='missing',expected_version=0)
        status,body=self.request('/api/reviews',data);self.assertEqual(status,500);self.assertIn('error',json.loads(body))
    def test_bad_geography_returns_error_not_disconnect(self):
        (self.root/'Data/geography.json').write_text('{"synthetic":true}')
        status,body=self.request('/api/geography');self.assertEqual(status,500);self.assertIn('error',json.loads(body))
    def test_missing_database_table_returns_error_not_disconnect(self):
        with closing(sqlite3.connect(self.db)) as db, db:db.execute('DROP TABLE visits')
        status,body=self.request('/api/analysis');self.assertEqual(status,503);self.assertIn('error',json.loads(body))
