"""Validate exported data boundaries and links without a running dashboard."""
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from build_static import build


class StaticBuildTests(unittest.TestCase):
    def test_export_contains_only_examples_and_relative_links(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);data=build(root)
            self.assertEqual(data['report']['summary']['known_discrepancy_total_pence'],98700)
            self.assertEqual(sum(c['completed'] for c in data['analysis']['contracts']),0)
            self.assertEqual(sum(c['visit_count'] for c in data['analysis']['contracts']),75)
            self.assertNotIn('/home/',(root/'data.json').read_text())
            self.assertNotIn('reviewer',(root/'data.json').read_text())
            self.assertEqual(len(list(root.glob('documents/*/*.pdf'))),10)
            self.assertFalse(list(root.rglob('*.sqlite3')))
            for page in root.glob('*.html'):
                text=page.read_text()
                self.assertFalse(re.search(r'href="/(?!/)',text),page.name)
                self.assertNotIn("fetch('/api",text)
                for link in re.findall(r'(?:href|src)="([^"${}]+)"',text):
                    if link.startswith(('https:','http:','#')):continue
                    path=link.split('?')[0].split('#')[0]
                    self.assertTrue((root/path).is_file(),(page.name,link))
            seed2=build(root)
            self.assertEqual(seed2['dataset_id'],data['dataset_id'])
            # Evidence identifiers must also survive a rebuild of the same input.
            self.assertEqual(seed2['report']['contracts'][0]['lines'][0]['evidence_key'],data['report']['contracts'][0]['lines'][0]['evidence_key'])
