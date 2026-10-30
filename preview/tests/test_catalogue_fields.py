from copy import deepcopy
from pathlib import Path
import json, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue_fields import addition_dates, metadata
from server import Preview, write
from source_locations import decorate, folder


class CatalogueFields(unittest.TestCase):
    def test_dates_migrate_known_skills_keep_unknowns_and_survive_removal_and_refresh(self):
        addon = {'id':'skill','components':[{'kind':'skill','skill_id':'s'}, {'kind':'program'}]}
        old = {'id':'mcp','components':[{'kind':'mcp'}]}
        rows, registry = [addon, old], {}
        self.assertTrue(addition_dates(rows, registry, {'s':{'first_seen':'2026-10-20T12:00:00Z'}}, '2026-10-30T12:00:00Z'))
        self.assertEqual(addon['added_at'], '2026-10-20T12:00:00+00:00')
        self.assertIsNone(old['added_at'])
        before = deepcopy(registry)
        self.assertFalse(addition_dates(rows, registry, {}, '2026-10-31T12:00:00Z'))
        self.assertEqual(registry,before)
        self.assertFalse(addition_dates([],registry,{},'2026-11-01T12:00:00Z'))
        new = {'id':'new','components':[]}
        self.assertTrue(addition_dates([new],registry,{},'2026-11-01T12:00:00Z'))
        self.assertEqual(new['added_at'],'2026-11-01T12:00:00+00:00')
        self.assertFalse(addition_dates([addon],registry,{},'2026-11-02T12:00:00Z'))
        self.assertEqual(registry['items']['skill'], before['items']['skill'])

    def test_invalid_or_missing_historical_dates_are_not_invented(self):
        for stamp in [None, 'garbage', '2026-10-20T12:00:00']:
            rows=[{'id':'s','components':[{'kind':'skill','skill_id':'s'}]}]
            addition_dates(rows,{}, {'s':{'first_seen':stamp}},'2026-10-30T12:00:00Z')
            self.assertIsNone(rows[0]['added_at'])

    def test_metadata_rejects_unknown_values_without_accepting_a_config_path(self):
        payload={'origins':['personal','third_party'],'billings':['free','paid'],'directions':['design']}
        self.assertEqual(metadata(payload,[{'id':'design'}]),payload)
        for change in [{'origins':['invented']},{'billings':'free'},{'directions':['../config.toml']}]:
            with self.assertRaises(ValueError):metadata({**payload,**change},[{'id':'design'}])

    def test_personal_metadata_and_complete_tags_persist_with_history_and_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp)
            snapshot={'addons':[{'id':'a','tags':['original','remove'],'origin':'builtin','billing':'included','directions':['code']}], 'directions':[{'id':'code'},{'id':'design'}]}
            write(work/'snapshot.json',snapshot);service=Preview({},work)
            write(work/'annotations.json',{'revision':0,'items':{'a':{'tags':['old-extra'],'custom':'preserve'}},'events':[]})
            result=service.annotate({'id':'a','action':'metadata','revision':0,'origins':['personal','third_party'],'billings':['free','paid'],'directions':['design','code']})
            result=service.annotate({'id':'a','action':'tags','revision':result['revision'],'text':'original, renamed, renamed'})
            self.assertEqual(result['items']['a']['tags_override'],['original','renamed'])
            self.assertEqual(result['items']['a']['custom'],'preserve')
            self.assertEqual([e['kind'] for e in result['events']],['preview_metadata','preview_tags'])
            self.assertEqual(result['events'][1]['value']['before'],['original','remove','old-extra'])
            with self.assertRaises(ValueError):service.annotate({'id':'a','action':'tags','revision':0,'text':'overwrite'})
            write(work/'snapshot.json', {**snapshot,'updated_at':'2026-11-01T12:00:00Z'})
            self.assertEqual(json.loads((work/'annotations.json').read_text())['items'],result['items'])
            cleared=service.annotate({'id':'a','action':'tags','revision':result['revision'],'text':''})
            self.assertEqual(cleared['items']['a']['tags_override'],[])

    def test_source_paths_are_selected_from_snapshot_for_each_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'config.toml';file.write_text('test')
            skill=root/'skill'/'SKILL.md';skill.parent.mkdir();skill.write_text('test')
            snapshot={'addons':[{'id':'a','components':[
                {'id':'m','kind':'mcp','contexts':{'all':{'sources':[{'path':str(file)}]}}},
                {'id':'s','kind':'skill','path':str(skill)}]}]}
            decorated=decorate(deepcopy(snapshot));parts=decorated['addons'][0]['components']
            for component, facts, expected in [(parts[0],parts[0]['contexts']['all'],root),(parts[1],parts[1],skill.parent)]:
                entry=facts['source_locations'][0]
                payload={'id':'a','component_id':component['id'],'source_id':entry['id']}
                self.assertEqual(folder(snapshot,payload),expected.resolve())
                with self.assertRaises(ValueError):folder(snapshot,{**payload,'source_id':'../../other'})
            entry=parts[0]['contexts']['all']['source_locations'][0]
            with self.assertRaises(ValueError):folder(snapshot,{'id':'a','component_id':'m','source_id':entry['id'],'context':'foreign'})
            file.unlink()
            with self.assertRaisesRegex(ValueError,'недоступны'):folder(snapshot,{'id':'a','component_id':'m','source_id':entry['id']})

    def test_reveal_uses_existing_foreground_explorer_helper(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'SKILL.md';file.write_text('test')
            snapshot={'addons':[{'id':'a','components':[{'id':'s','kind':'skill','path':str(file)}]}]}
            write(root/'snapshot.json',snapshot);entry=decorate(deepcopy(snapshot))['addons'][0]['components'][0]['source_locations'][0]
            with patch('server.open_folder',return_value={'opened':True,'foreground':True}) as opener:
                result=Preview({},root).reveal_source({'id':'a','component_id':'s','source_id':entry['id']})
            opener.assert_called_once_with(root.resolve());self.assertTrue(result['foreground'])

    def test_plugin_program_and_account_sources_keep_their_actual_locations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest=root/'plugin.json';manifest.write_text('{}')
            program=root/'tool.exe';program.write_text('test')
            snapshot={'addons':[{'id':'a','skills':[{'id':'plugin:sample@local:skill','bundle':{'path':str(manifest)}}], 'components':[
                {'id':'plugin','kind':'plugin','name':'sample@local'},
                {'id':'program','kind':'program','path':str(program)},
                {'id':'account','kind':'app','sources':[{'path':'Codex app/installed'}]}]}]}
            parts=decorate(snapshot)['addons'][0]['components']
            self.assertEqual(parts[0]['source_locations'][0]['path'],str(manifest))
            self.assertEqual(parts[1]['source_locations'][0]['path'],str(program))
            self.assertEqual(parts[2]['source_locations'],[])


if __name__=='__main__':unittest.main()
