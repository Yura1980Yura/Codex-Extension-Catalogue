from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import audit
from model import norm


class AuditCounts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check(self, paths, components, session_paths=(), views=None):
        inventory = {'discovery_status': 'ok', 'skills': {
            str(i): {'locations': [{'kind': 'session', 'path': p}]}
            for i, p in enumerate(paths)}}
        return audit(inventory, views or {}, [{'components': components}],
                     {'skills': [{'path': p} for p in session_paths]}, [])

    def skill(self, name, confirmed=False, enabled=None):
        path = str(self.root/name/'SKILL.md')
        return {'id': name, 'kind': 'skill', 'path': path, 'file_found': True,
                'installed': confirmed, 'enabled': enabled,
                'observations': [{'kind': 'discovery', 'path': path, 'enabled': enabled}]
                if confirmed else []}

    def test_17_found_skills_in_both_sources_are_not_34_missing_records(self):
        parts = [self.skill(str(i)) for i in range(17)]
        paths = [c['path'] for c in parts]
        result = self.check(paths, parts, paths)
        self.assertEqual(result['missing_skill_paths'], [])
        self.assertEqual(result['missing_session_paths'], [])
        self.assertEqual(result['missing_record_count'], 0)
        self.assertEqual(len(result['unconfirmed_skill_paths']), 17)
        self.assertEqual(result['compared_skill_paths'], 17)
        self.assertTrue(result['complete'])

    def test_genuinely_missing_path_shared_by_sources_is_counted_once(self):
        absent = str(self.root/'absent/SKILL.md')
        result = self.check([absent], [], [absent, absent])
        self.assertEqual(result['missing_record_paths'], [norm(absent)])
        self.assertEqual(result['missing_record_count'], 1)
        self.assertEqual(result['unconfirmed_skill_paths'], [])
        self.assertFalse(result['complete'])

    def test_enabled_and_disabled_discoveries_both_confirm_presence(self):
        parts = [self.skill('on', True, True), self.skill('off', True, False)]
        result = self.check([c['path'] for c in parts], parts)
        self.assertEqual(result['unconfirmed_skill_paths'], [])
        self.assertEqual(result['missing_record_count'], 0)
        self.assertTrue(result['complete'])

    def test_confirmation_uses_discovery_not_installation_or_experience_flags(self):
        part = self.skill('found')
        part.update(installed=True, verified_experience=[{'result': 'old success'}])
        result = self.check([part['path']], [part])
        self.assertEqual(result['unconfirmed_skill_paths'], [norm(part['path'])])

    def test_missing_connection_shared_by_contexts_is_one_record(self):
        views = {key: {'status': 'effective', 'apps_status': 'reported', 'services': [
            {'id': 'mcp:missing', 'configured': True},
            {'id': 'mcp:present', 'configured': True}]} for key in ['all', 'project']}
        part = {'id': 'mcp:present', 'kind': 'mcp', 'contexts': {
            key: {'installed': False, 'enabled': False} for key in views}}
        result = self.check([], [part], views=views)
        self.assertEqual(result['missing_connection_ids'], ['mcp:missing'])
        self.assertEqual(len(result['missing_connections']), 2)
        self.assertEqual(result['missing_record_count'], 1)

    def test_only_actual_skill_records_represent_skill_paths(self):
        path = str(self.root/'skill/SKILL.md')
        result = self.check([path], [{'id': 'program', 'kind': 'program',
                                    'path': path, 'installed': True}])
        self.assertEqual(result['missing_record_count'], 1)

    def test_bare_cache_outside_compared_sources_is_not_an_extra_mismatch(self):
        known, cache = self.skill('known'), self.skill('old-cache')
        result = self.check([known['path']], [known, cache])
        self.assertEqual(result['compared_skill_paths'], 1)
        self.assertEqual(result['unconfirmed_skill_paths'], [norm(known['path'])])

    def test_source_failure_and_duplicates_still_prevent_success(self):
        part = self.skill('known', True)
        views = {'all': {'status': 'file_only', 'apps_status': 'unavailable', 'services': []}}
        result = self.check([part['path']], [part, part], views=views)
        self.assertEqual(result['missing_record_count'], 0)
        self.assertEqual(result['duplicate_component_ids'], ['known'])
        self.assertEqual(result['source_failures'], ['all'])
        self.assertFalse(result['complete'])


if __name__ == '__main__':
    unittest.main()
