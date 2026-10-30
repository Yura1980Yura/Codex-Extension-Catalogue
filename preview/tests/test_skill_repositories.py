from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from skill_repositories import indexes,match


class RepositoryReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'SKILL.md';self.path.write_text('A personal instruction','utf-8')
        self.config={'skill_repositories':[{'repository':'owner/library','branch':'main','author':'Owner'}]}

    def test_personal_origin_and_same_name_do_not_prove_repository_provenance(self):
        index={'repository':'other/library','revision':'a'*40,'checked_at':'2026-10-30','status':'verified','skills':{'example':[{'path':'skills/example','sha':'different'}]}}
        self.assertIsNone(match({'name':'example','origin':'personal'},self.path,index))

    def test_nonobject_cache_is_ignored_without_blocking_a_valid_index(self):
        (self.root/'skill-repositories.json').write_text('[]','utf-8')
        response=SimpleNamespace(returncode=0,stdout=json.dumps({'sha':'a'*40,'tree':[]}).encode())
        with patch('skill_repositories.shutil.which',return_value='gh'),patch('skill_repositories.subprocess.run',return_value=response):
            self.assertEqual(indexes(self.config,self.root)['owner/library']['status'],'verified')

    def test_wrong_settings_shape_does_not_abort_catalogue_collection(self):
        result=indexes({'skill_repositories':{'repository':'owner/library'}},self.root)
        self.assertTrue(any(value.get('warning') for value in result.values()))

    def test_missing_github_keeps_cached_index_and_original_check_time(self):
        cached={'owner/library':{'skills':{'example':[]},'revision':'a'*40,'checked_at':'2026-10-01','status':'verified'}}
        (self.root/'skill-repositories.json').write_text(json.dumps(cached),'utf-8')
        with patch('skill_repositories.shutil.which',return_value=None):result=indexes(self.config,self.root)
        self.assertEqual(result['owner/library']['status'],'cached')
        self.assertEqual(result['owner/library']['checked_at'],'2026-10-01')
        self.assertIn('warning',result['owner/library'])


if __name__=='__main__':unittest.main()
