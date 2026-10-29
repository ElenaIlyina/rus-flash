#!/usr/bin/env python3
"""A production download builds independently of the entire development tree."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
from publish_content import payloads


class ProductionSeparationTest(unittest.TestCase):
    def test_published_inputs_match_validated_editorial_records(self):
        for name, expected in payloads().items():
            self.assertEqual(json.loads((ROOT/name).read_text()),expected,name)

    def test_student_app_has_no_review_tool_dependency(self):
        for path in (ROOT/'html').rglob('*'):
            if not path.is_file() or 'assets' in path.parts:
                continue
            self.assertNotIn('review-debug',path.read_text(),str(path))
        self.assertFalse((ROOT/'html/js/review-debug.js').exists())
        self.assertFalse((ROOT/'html/assets/data/review-debug.json').exists())
        for source in json.loads((ROOT/'data/knowledge/dictionary_sources.json').read_text())['sources']:
            self.assertTrue(source['file'].startswith('data/'))

    def test_clean_copy_builds_with_standard_library_only(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)
            for name in ['data','html','scripts','.github']:
                shutil.copytree(ROOT/name,target/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            for name in ['README.md','.gitignore','.gitattributes']:
                shutil.copyfile(ROOT/name,target/name)
            shutil.rmtree(target/'html/assets/data')
            self.assertFalse((target/'dev').exists())
            subprocess.run([sys.executable,'-S',str(target/'scripts/build_app_data.py')],check=True,capture_output=True,text=True)
            subprocess.run([sys.executable,'-S',str(target/'scripts/check_pages_artifact.py'),str(target/'html')],check=True,capture_output=True,text=True)
            catalog=json.loads((target/'html/assets/data/catalog.json').read_text())
            self.assertEqual(len(catalog['cards']),2140)
            original=json.loads((ROOT/'html/assets/data/catalog.json').read_text())
            self.assertEqual(catalog,original)
            # A previous developer build must not leak stale review assets.
            stale=target/'html/assets/data/review-debug.json'
            stale.write_text('[]')
            subprocess.run([sys.executable,'-S',str(target/'scripts/build_app_data.py')],check=True,capture_output=True,text=True)
            self.assertFalse(stale.exists())


if __name__=='__main__':unittest.main()
