import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from spark_contracts import extract_spark

class SparkTests(unittest.TestCase):
    def test_api_auth_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch('spark_contracts.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Logged in using API key',stderr='')) as run:
            p=Path(d)/'contract.txt';p.write_text('Synthetic contract')
            with self.assertRaisesRegex(ValueError,'ChatGPT sign-in'):
                extract_spark(p,Path(d)/'out')
            self.assertEqual(run.call_count,1)
    def test_api_keys_removed(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'OPENAI_API_KEY':'test','CODEX_API_KEY':'test'}), patch('spark_contracts.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='')) as run:
            p=Path(d)/'contract.txt';p.write_text('Synthetic contract')
            with self.assertRaises(ValueError):extract_spark(p,Path(d)/'out')
            self.assertNotIn('OPENAI_API_KEY',run.call_args.kwargs['env'])
            self.assertNotIn('CODEX_API_KEY',run.call_args.kwargs['env'])
