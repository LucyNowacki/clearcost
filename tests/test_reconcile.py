from contextlib import closing
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from reconcile import ROOT, load_scenario, reconcile, run, summarize


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'Data'/'Contracts'/'03_harbour_meter_testing'
        self.terms,self.visits,self.lines,_=load_scenario(self.folder)

    def test_five_oracles_and_sql(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.sqlite3'
            report=run(ROOT/'Data'/'Contracts',db,Path(tmp)/'report.json')
            for contractor in report['contracts']:
                # Ground truth is read only by tests, never by the engine.
                oracle=json.loads((ROOT/'Data'/'Contracts'/contractor['scenario_folder']/'expected_results.json').read_text())
                for result,truth in zip(contractor['lines'],oracle['expected_lines'],strict=True):
                    for key in ('line_id','job_id','classification','requires_review','billed_pence','expected_pence','discrepancy_pence'):
                        self.assertEqual(result[key],truth[key],(contractor['contract_id'],key))
                for key,value in oracle['expected_summary'].items():
                    if key in contractor['summary']: self.assertEqual(contractor['summary'][key],value)
            with closing(sqlite3.connect(db)) as connection, connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM findings').fetchone()[0],80)
                self.assertEqual(connection.execute('SELECT SUM(discrepancy_pence) FROM findings').fetchone()[0],98700)
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_oracle_files_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'input'; dest=root/'sample';dest.mkdir(parents=True)
            for name in ('contract.pdf','visits.csv','invoice_lines.csv'):
                shutil.copy(self.folder/name,dest/name)
            report=run(root,Path(tmp)/'db.sqlite3',Path(tmp)/'result.json')
            self.assertEqual(report['summary']['discrepancy_total_pence'],24000)

    def test_missing_record_is_unknown(self):
        results=reconcile(self.terms,self.visits[1:],self.lines)
        self.assertIsNone(results[0]['expected_pence'])
        self.assertIn('missing_visit_record',results[0]['issues'])
        summary=summarize(results)
        self.assertIsNone(summary['expected_total_pence'])
        self.assertIsNone(summary['discrepancy_total_pence'])
        self.assertGreater(summary['unverified_billed_total_pence'],0)

    def test_missing_completion_evidence(self):
        self.visits[0]['completion_reference']=''
        result=reconcile(self.terms,self.visits,self.lines)[0]
        self.assertIsNone(result['expected_pence'])

    def test_approved_supplement_is_not_error(self):
        result=reconcile(self.terms,self.visits,self.lines)[11]
        self.assertEqual(result['classification'],'match')
        self.assertEqual(result['expected_pence'],10000)

    def test_invalid_approval_is_unknown(self):
        self.visits[11]['approval_reference']='UNRECOGNISED'
        result=reconcile(self.terms,self.visits,self.lines)[11]
        self.assertIsNone(result['expected_pence'])

    def test_duplicate_order_uses_line_number(self):
        baseline=reconcile(self.terms,self.visits,self.lines)
        self.assertEqual(baseline,reconcile(self.terms,self.visits,list(reversed(self.lines))))
        self.assertEqual(baseline[-1]['classification'],'duplicate_job')

    def test_arithmetic_and_out_of_period(self):
        self.lines[0]['line_amount_pence']+=3
        result=reconcile(self.terms,self.visits,self.lines)[0]
        self.assertIn('line_arithmetic_mismatch',result['issues'])
        self.lines[0]['service_date']='2026-09-01'
        self.assertIsNone(reconcile(self.terms,self.visits,self.lines)[0]['expected_pence'])

    def test_invalid_currency_and_duplicate_record_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'sample';shutil.copytree(self.folder,dest)
            path=dest/'invoice_lines.csv'
            path.write_text(path.read_text().replace(',GBP,',',USD,'))
            with self.assertRaises(ValueError):load_scenario(dest)
            shutil.copy(self.folder/'invoice_lines.csv',path)
            visits=dest/'visits.csv'
            with visits.open('a') as f:f.write(visits.read_text().splitlines()[1]+'\n')
            with self.assertRaises(ValueError):load_scenario(dest)

    def test_rerun_preserves_separate_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite3';out=Path(tmp)/'report.json'
            first=run(ROOT/'Data'/'Contracts',db,out)
            second=run(ROOT/'Data'/'Contracts',db,out)
            self.assertNotEqual(first['run_id'],second['run_id'])
            with closing(sqlite3.connect(db)) as c, c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM runs').fetchone()[0],2)
                self.assertEqual(c.execute('SELECT COUNT(*) FROM findings').fetchone()[0],160)


if __name__=='__main__':unittest.main()
