import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from llm_contracts import FIELDS, validate, parse_response, extract

class ExtractionTests(unittest.TestCase):
    def result(self):
        return {'terms':[{'field':f,'value':None,'page':None,'quote':None,'uncertainty':'Not stated.'} for f in FIELDS], 'warnings':[]}
    def test_exact_evidence(self):
        result=self.result()
        result['terms'][0].update(value='CTR-002',page=1,quote='Contract CTR-002',uncertainty=None)
        self.assertEqual(validate(result,['Contract CTR-002']),result)
        with self.assertRaises(ValueError):validate(result,['Contract CTR-003'])
    def test_duplicate_fields(self):
        result=self.result();result['terms'][1]=copy.deepcopy(result['terms'][0])
        with self.assertRaises(ValueError):validate(result,['text'])
    def test_missing_uncertainty(self):
        result=self.result();result['terms'][0]['uncertainty']=None
        with self.assertRaises(ValueError):validate(result,['text'])
    def test_refusal_and_incomplete(self):
        for response in [{'status':'incomplete'}, {'status':'completed','output':[{'content':[{'type':'refusal'}]}]}]:
            with self.assertRaises(ValueError):parse_response(response,['text'])
    def test_completed_response(self):
        result=self.result()
        self.assertEqual(parse_response({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(result)}]}]},['text']),result)
    def test_offline_never_calls_api(self):
        with tempfile.TemporaryDirectory() as d, patch('llm_contracts.urlopen') as call:
            path=Path(d)/'contract.txt';path.write_text('A synthetic contract.')
            prepared=extract(path,Path(d)/'out')
            self.assertEqual(json.loads(prepared.read_text())['status'],'prepared_not_run')
            call.assert_not_called()
    def test_live_mock_and_cache(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}), patch('llm_contracts.urlopen') as call:
            import io
            response={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(self.result())}]}]}
            call.return_value.__enter__.return_value=io.StringIO(json.dumps(response))
            path=Path(d)/'contract.txt';path.write_text('A synthetic contract.')
            out=extract(path,Path(d)/'out',True)
            self.assertEqual(json.loads(out.read_text())['status'],'draft_needs_human_review')
            self.assertEqual(extract(path,Path(d)/'out',True),out)
            self.assertEqual(call.call_count,1)
