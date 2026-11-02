from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repository_discovery import GitHub, discover, git_source, github_repository, instruction_hashes

REVISION = 'a'*40


class RepositoryDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.file = self.root/'example/SKILL.md'
        self.file.parent.mkdir(); self.file.write_bytes(b'name: example\nInstruction\n')
        self.sha = next(iter(instruction_hashes(self.file.read_bytes())))
        self.skill = {'id': 'local:example', 'name': 'example'}
        self.addon = {'skills': [self.skill], 'components': [{'skill_id': 'local:example', 'installed': True}]}
        self.repos = {}; self.owned = []; self.hits = []; self.calls = []

    def api(self, endpoint, params):
        self.calls.append((endpoint, params))
        if endpoint == 'user/repos': return [{'full_name': name, 'fork': False} for name in self.owned]
        if endpoint == 'search/code': return {'items': self.hits}
        repository = '/'.join(endpoint.split('/')[1:3]); rows = self.repos.get(repository)
        if rows is None: raise ValueError('No access')
        if endpoint == 'repos/'+repository: return {'default_branch': 'main'}
        if '/commits/' in endpoint: return {'sha': REVISION}
        if '/git/trees/' in endpoint: return {'tree': [{'type': 'blob', 'path': path, 'sha': sha} for path, sha in rows], 'truncated': False}
        raise AssertionError(endpoint)

    def run_discovery(self, origin=None, official=()):
        with patch('repository_discovery.git_source', return_value=origin), patch('repository_discovery.OFFICIAL', official):
            return discover([self.addon], {self.skill['id']: {'path': str(self.file)}}, {}, self.root/'cache', self.api)

    def test_repository_parsing_removes_credentials_and_does_not_guess_relative_links(self):
        for url in ('https://user:secret@github.com/vendor/tool.git?token=secret', 'git@github.com:vendor/tool.git', 'ssh://git@github.com/vendor/tool.git'):
            self.assertEqual(github_repository(url), 'vendor/tool')
        for value in ('vendor/tool', 'docs/README.md', 'https://github.com/owner', 'https://github.com/topics/skills', 'https://github.com.evil.test/a/b', 'https://github.com:8443/a/b'):
            self.assertIsNone(github_repository(value))
        self.assertEqual(github_repository('vendor/tool', shorthand=True), 'vendor/tool')

    def test_instruction_hash_accepts_git_line_ending_conversion(self):
        self.assertTrue(instruction_hashes(b'\xef\xbb\xbfline\r\n') & instruction_hashes(b'line\n'))
        self.assertFalse(instruction_hashes(b'other\n') & instruction_hashes(b'line\n'))

    def test_owned_repository_exact_match_uses_verified_commit_and_encoded_folder(self):
        self.owned = ['owner/library']; self.repos['owner/library'] = [('skills/space here/SKILL.md', self.sha)]
        audit = self.run_discovery(); result = self.skill['repository_discovery']
        self.assertEqual(audit['linked'], 1); self.assertEqual(result['status'], 'verified')
        match = result['matches'][0]
        self.assertEqual(match['folder_url'], f'https://github.com/owner/library/tree/{REVISION}/skills/space%20here')
        self.assertTrue(match['exact_instruction']); self.assertIn('не устанавливает первичное авторство', match['evidence'])

    def test_project_remote_remains_useful_for_changed_or_unpublished_skill(self):
        self.repos['owner/project'] = [('skills/example/SKILL.md', 'b'*40)]
        origin = {'repository': 'owner/project', 'path': 'skills/example/SKILL.md', 'branch': 'feature/new'}
        self.run_discovery(origin)
        match = self.skill['repository_discovery']['matches'][0]
        self.assertEqual(match['method'], 'git'); self.assertFalse(match['exact_instruction'])
        self.assertIn('отличается', match['evidence'])
        self.assertTrue(any('/commits/feature%2Fnew' in endpoint for endpoint, _ in self.calls))
        self.repos['owner/project'] = []
        (self.root/'cache/skill-source-discovery.json').unlink(); self.run_discovery(origin)
        match = self.skill['repository_discovery']['matches'][0]
        self.assertIsNone(match['folder_url']); self.assertIn('не опубликован', match['evidence'])

    def test_declared_repository_does_not_invent_a_matching_skill_directory(self):
        self.skill['source'] = {'repository': 'vendor/project'}
        self.repos['vendor/project'] = [('other/SKILL.md', 'b'*40)]
        self.run_discovery(); match = self.skill['repository_discovery']['matches'][0]
        self.assertEqual(match['method'], 'declared'); self.assertIsNone(match['folder_url'])

    def test_resource_repository_is_explicitly_associated_without_guessing_skill_folder(self):
        self.addon['profile'] = {'website': 'https://github.com/vendor/resource'}
        self.repos['vendor/resource'] = [('skills/example/SKILL.md', 'b'*40)]
        self.run_discovery(); match = self.skill['repository_discovery']['matches'][0]
        self.assertEqual(match['method'], 'related'); self.assertIsNone(match['folder_url'])
        self.assertIn('Связанный проект', match['evidence'])

    def test_tree_failure_keeps_only_confirmed_repository_fact(self):
        self.skill['source'] = {'repository': 'vendor/project'}
        def api(endpoint, params):
            if endpoint == 'repos/vendor/project': return {'default_branch': 'main'}
            raise ValueError('Index unavailable')
        with patch.object(self, 'api', side_effect=api): self.run_discovery()
        match = self.skill['repository_discovery']['matches'][0]
        self.assertEqual(match['status'], 'verified'); self.assertIsNone(match['folder_url'])
        self.assertIn('Индекс файлов не подтверждён', match['evidence'])

    def test_shared_project_branch_is_requested_once_for_multiple_skills(self):
        self.repos['owner/project'] = [('skills/example/SKILL.md', self.sha)]
        self.addon['skills'].append({'id': 'local:second', 'name': 'example'})
        self.addon['components'].append({'skill_id': 'local:second', 'installed': True})
        origin = {'repository': 'owner/project', 'path': 'skills/example/SKILL.md', 'branch': 'feature/new'}
        with patch('repository_discovery.git_source', return_value=origin), patch('repository_discovery.OFFICIAL', ()):
            discover([self.addon], {skill['id']: {'path': str(self.file)} for skill in self.addon['skills']}, {}, self.root/'cache', self.api)
        self.assertEqual(sum('/commits/feature%2Fnew' in endpoint for endpoint, _ in self.calls), 1)

    def test_official_publisher_mapping_explains_local_version_difference(self):
        self.skill['id'] = 'system:example'; self.addon['components'][0]['skill_id'] = self.skill['id']
        self.repos['openai/skills'] = [('skills/.system/example/SKILL.md', 'b'*40)]
        self.run_discovery(official=('openai/skills',))
        self.assertEqual(self.skill['repository_discovery']['matches'][0]['method'], 'official')
        self.skill['id'] = 'local:example'; self.addon['components'][0]['skill_id'] = self.skill['id']
        self.run_discovery(official=('openai/skills',))
        self.assertEqual(self.skill['repository_discovery']['matches'], [])

    def test_offline_cached_evidence_preserves_original_date_and_rejects_bad_paths(self):
        self.owned = ['owner/library']; self.repos['owner/library'] = [('skills/example/SKILL.md', self.sha)]
        self.run_discovery(); checked = self.skill['repository_discovery']['matches'][0]['checked_at']
        cache = self.root/'cache/skill-source-discovery.json'; data = json.loads(cache.read_text())
        data['repositories']['owner/library@HEAD']['files'].append({'path': '../SKILL.md', 'sha': self.sha})
        cache.write_text(json.dumps(data))
        with patch.object(self, 'api', side_effect=ValueError('offline')): self.run_discovery()
        result = self.skill['repository_discovery']
        self.assertEqual(result['status'], 'cached'); self.assertEqual(len(result['matches']), 1)
        self.assertEqual(result['matches'][0]['checked_at'], checked)

    def test_same_name_and_unverified_search_hit_are_not_source_proof(self):
        self.hits = [{'repository': {'full_name': 'unrelated/copy'}, 'path': 'skills/example/SKILL.md', 'sha': self.sha}]
        self.repos['unrelated/copy'] = [('skills/example/SKILL.md', 'b'*40)]
        self.run_discovery(); self.assertEqual(self.skill['repository_discovery']['status'], 'not_found')
        self.assertEqual(self.skill['repository_discovery']['matches'], [])

    def test_search_exact_publication_is_labelled_without_changing_authorship(self):
        self.skill['author_profile'] = {'name': 'Actual author'}
        self.hits = [{'repository': {'full_name': 'public/copy'}, 'path': 'SKILL.md', 'sha': self.sha}]
        self.repos['public/copy'] = [('SKILL.md', self.sha)]
        self.run_discovery(); match = self.skill['repository_discovery']['matches'][0]
        self.assertTrue(match['file_url'].endswith('/SKILL.md')); self.assertIsNone(match['folder_url'])
        self.assertEqual(self.skill['author_profile']['name'], 'Actual author')
        for _, params in self.calls:
            self.assertNotIn(str(self.root), str(params)); self.assertNotIn('Instruction', str(params))

    def test_missing_github_access_and_uninstalled_findings_are_distinct(self):
        with patch.object(self, 'api', side_effect=ValueError('offline')): self.run_discovery()
        self.assertEqual(self.skill['repository_discovery']['status'], 'unavailable')
        self.addon['components'][0]['installed'] = False; self.calls.clear()
        self.assertEqual(self.run_discovery()['checked'], 0); self.assertEqual(self.calls, [])

    def test_request_budget_is_bounded(self):
        client = GitHub(request=lambda *_: {})
        for _ in range(120): client.api('test')
        with self.assertRaises(ValueError): client.api('test')
        self.assertEqual(client.calls, 120)

    def test_git_source_reads_real_remote_without_leaking_credentials(self):
        options = {'capture_output': True, 'check': True, 'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
        subprocess.run(['git', 'init', str(self.root)], **options)
        subprocess.run(['git', '-C', str(self.root), 'remote', 'add', 'origin', 'https://user:secret@github.com/vendor/tool.git'], **options)
        source = git_source(self.file)
        self.assertEqual(source['repository'], 'vendor/tool'); self.assertEqual(source['path'], 'example/SKILL.md')
        self.assertNotIn('secret', json.dumps(source))


if __name__ == '__main__': unittest.main()
