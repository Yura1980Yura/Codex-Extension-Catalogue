from pathlib import Path
import json, sys, tempfile, unittest, os
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from skill_files import SkillFiles, SkillFileError, LockedInstruction
from server import Preview, write


class SkillFileOperations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.home=self.root/'home';self.work=self.root/'work'
        self.settings={'home':str(self.home),'source_data':str(self.root/'legacy')}
        self.files=SkillFiles(self.settings,self.work)
        self.folder=self.home/'.agents/skills/example';self.folder.mkdir(parents=True)
        (self.folder/'SKILL.md').write_text('---\nname: example\ndescription: Example\n---\nInstructions',encoding='utf-8')
        (self.folder/'helper.txt').write_text('support',encoding='utf-8')
        self.c={'id':'component','skill_id':'local:example','kind':'skill','path':str(self.folder/'SKILL.md'),'installed':True,'file_found':True}
        self.snapshot={'addons':[{'id':'addon','components':[self.c]}],'projects':[]}
        self.payload={'id':'addon','component_id':'component','action':'remove'}

    def apply(self,payload=None,record=lambda value:None):
        payload=payload or self.payload
        plan=self.files.plan(self.snapshot,payload)
        return self.files.apply(self.snapshot,{**payload,'revision':plan['revision'],'confirmed':True},record)

    def test_remove_moves_only_selected_instruction_and_preserves_every_other_file(self):
        other=self.folder.parent/'other';other.mkdir();events=[]
        child=self.folder/'nested/SKILL.md';child.parent.mkdir();child.write_text('another instruction')
        original=(self.folder/'SKILL.md').read_bytes()
        result=self.apply(record=events.append)
        self.assertTrue(self.folder.is_dir());self.assertFalse((self.folder/'SKILL.md').exists());self.assertTrue(other.is_dir())
        self.assertEqual((self.folder/'helper.txt').read_text(),'support');self.assertEqual(child.read_text(),'another instruction')
        backup=Path(result['backup']);self.assertEqual(backup.read_bytes(),original)
        self.assertEqual(result['files'],1);self.assertEqual(result['kind'],'instruction_only')
        self.assertFalse(backup.is_relative_to(self.home));self.assertEqual(len(events),1)

    def test_no_confirmation_or_changed_instruction_cannot_delete(self):
        plan=self.files.plan(self.snapshot,self.payload)
        with self.assertRaises(SkillFileError):self.files.apply(self.snapshot,{**self.payload,'revision':plan['revision']},lambda _:None)
        (self.folder/'SKILL.md').write_text('---\nname: example\ndescription: Changed\n---\n')
        with self.assertRaises(SkillFileError):self.files.apply(self.snapshot,{**self.payload,'revision':plan['revision'],'confirmed':True},lambda _:None)
        self.assertTrue(self.folder.is_dir())

    def test_changed_unrelated_helper_does_not_expand_or_cancel_instruction_only_operation(self):
        plan=self.files.plan(self.snapshot,self.payload)
        (self.folder/'helper.txt').write_text('user edit')
        self.files.apply(self.snapshot,{**self.payload,'revision':plan['revision'],'confirmed':True},lambda _:None)
        self.assertEqual((self.folder/'helper.txt').read_text(),'user edit')

    def test_nested_selected_skill_does_not_remove_parent_instruction(self):
        nested=self.folder/'nested/SKILL.md';nested.parent.mkdir();nested.write_bytes((self.folder/'SKILL.md').read_bytes())
        self.c['path']=str(nested)
        self.apply()
        self.assertFalse(nested.exists());self.assertTrue((self.folder/'SKILL.md').is_file())

    def test_hardlinked_instruction_cannot_remove_an_alias(self):
        alias=self.folder/'alias.md';os.link(self.folder/'SKILL.md',alias)
        with self.assertRaises(SkillFileError):self.apply()
        self.assertTrue(alias.is_file());self.assertTrue((self.folder/'SKILL.md').is_file())

    def test_replaced_file_with_same_bytes_invalidates_preview_identity(self):
        plan=self.files.plan(self.snapshot,self.payload)
        path=self.folder/'SKILL.md';path.rename(self.folder/'previous.md');path.write_bytes((self.folder/'previous.md').read_bytes())
        with self.assertRaises(SkillFileError):self.files.apply(self.snapshot,{**self.payload,'revision':plan['revision'],'confirmed':True},lambda _:None)
        self.assertTrue(path.is_file())

    def test_unknown_ids_and_plugin_system_arbitrary_paths_are_rejected(self):
        with self.assertRaises(SkillFileError):self.files.plan(self.snapshot,{**self.payload,'component_id':'foreign'})
        for path in [self.home/'.codex/skills/.system/example/SKILL.md',self.root/'outside/example/SKILL.md']:
            path.parent.mkdir(parents=True);path.write_text((self.folder/'SKILL.md').read_text())
            self.c['path']=str(path)
            with self.assertRaises(SkillFileError):self.files.plan(self.snapshot,self.payload)
        self.c.update(path=str(self.folder/'SKILL.md'),skill_id='plugin:example@market:example')
        with self.assertRaises(SkillFileError):self.files.plan(self.snapshot,self.payload)

    def test_history_failure_restores_removed_folder(self):
        def fail(_):raise OSError('fixture')
        with self.assertRaises(OSError):self.apply(record=fail)
        self.assertEqual((self.folder/'helper.txt').read_text(),'support')
        self.assertTrue((self.folder/'SKILL.md').is_file())

    def test_restore_recovers_only_instruction_and_preserves_subsequent_resource_edits(self):
        original=(self.folder/'SKILL.md').read_bytes();removed=self.apply()
        (self.folder/'helper.txt').write_text('new helper version')
        self.apply({'action':'restore','operation_id':removed['operation_id']})
        self.assertEqual((self.folder/'SKILL.md').read_bytes(),original)
        self.assertEqual((self.folder/'helper.txt').read_text(),'new helper version')
        self.assertEqual(self.files.removed()[0]['status'],'restored')

    def test_restore_never_overwrites_new_instruction(self):
        removed=self.apply();target=self.folder/'SKILL.md';target.write_text('new instruction')
        with self.assertRaises(SkillFileError):self.apply({'action':'restore','operation_id':removed['operation_id']})
        self.assertEqual(target.read_text(),'new instruction')

    def test_restore_rejects_modified_backup_and_forged_operation_id(self):
        removed=self.apply();Path(removed['backup']).write_text('tampered')
        for key in [removed['operation_id'],'../../config.toml']:
            with self.assertRaises(SkillFileError):self.apply({'action':'restore','operation_id':key})
        self.assertFalse((self.folder/'SKILL.md').exists())

    def test_restore_rejects_replaced_parent_directory(self):
        removed=self.apply();self.folder.rename(self.folder.with_name('previous'));self.folder.mkdir()
        with self.assertRaises(SkillFileError):self.apply({'action':'restore','operation_id':removed['operation_id']})
        self.assertFalse((self.folder/'SKILL.md').exists())

    def test_restore_history_failure_removes_only_just_created_file(self):
        removed=self.apply()
        def fail(_):raise OSError('fixture')
        with self.assertRaises(OSError):self.apply({'action':'restore','operation_id':removed['operation_id']},fail)
        self.assertFalse((self.folder/'SKILL.md').exists());self.assertTrue((self.folder/'helper.txt').exists())
        self.assertEqual(self.files.removed()[0]['status'],'removed')

    @unittest.skipUnless(os.name=='nt','Windows file sharing semantics')
    def test_windows_instruction_handle_blocks_writers_and_replacements(self):
        def record(_):
            with self.assertRaises(OSError):(self.folder/'SKILL.md').write_text('replacement')
            (self.folder/'helper.txt').write_text('still editable')
        self.apply(record=record)
        self.assertEqual((self.folder/'helper.txt').read_text(),'still editable')

    def test_found_bundle_can_install_to_project_without_promoting_to_confirmed(self):
        self.c['installed']=False
        project=self.root/'project';project.mkdir()
        self.snapshot['projects']=[{'id':'p','name':'Project','path':str(project),'source':'codex'}]
        result=self.apply({**self.payload,'action':'install','project_id':'p'})
        target=Path(result['destination'])
        self.assertEqual(target,project/'.agents/skills/example')
        self.assertEqual((target/'helper.txt').read_text(),'support');self.assertTrue(self.folder.is_dir())
        self.assertFalse(self.c['installed'])
        with self.assertRaises(SkillFileError):self.apply({**self.payload,'action':'install','project_id':'p'})

    def test_failed_install_history_does_not_leave_a_discoverable_copy(self):
        self.c['installed']=False;self.folder.rename(self.root/'finding')
        self.c['path']=str(self.root/'finding/SKILL.md')
        def fail(_):raise OSError('fixture')
        with self.assertRaises(OSError):self.apply({**self.payload,'action':'install'},fail)
        self.assertFalse(self.folder.exists());self.assertTrue((self.root/'finding/SKILL.md').exists())

    def test_file_reveal_resolves_only_known_component_and_does_not_run_instruction(self):
        write(self.work/'snapshot.json',self.snapshot)
        service=Preview(self.settings,self.work)
        with patch('server.open_folder',return_value={'opened':True}) as opened:
            service.reveal_skill({**self.payload,'path':str(self.root/'unrelated')})
            opened.assert_called_once_with(self.folder.resolve())

    def test_service_delete_updates_snapshot_and_history_without_refresh(self):
        write(self.work/'snapshot.json',self.snapshot)
        service=Preview(self.settings,self.work)
        plan=service.skill_plan(self.payload)
        with patch.object(service,'refresh') as refresh:
            result=service.skill_change({**self.payload,'revision':plan['revision'],'confirmed':True})
            refresh.assert_not_called()
        c=result['state']['addons'][0]['components'][0]
        self.assertFalse(c['installed']);self.assertFalse(c['file_found'])
        self.assertEqual(result['state']['overlay']['events'][0]['kind'],'preview_skill_remove')
        self.assertEqual(len(result['state']['removed_skills']),1)
        # A new discovery may remove the original card. Restoration uses a known
        # operation receipt, never a path supplied by the browser.
        write(self.work/'snapshot.json',{'addons':[],'projects':[]})
        payload={'action':'restore','operation_id':result['result']['operation_id']}
        plan=service.skill_plan(payload)
        with patch.object(service,'refresh') as refresh:
            restored=service.skill_change({**payload,'revision':plan['revision'],'confirmed':True})
            refresh.assert_not_called()
        self.assertEqual(restored['state']['removed_skills'][0]['status'],'restored')
        self.assertTrue((self.folder/'SKILL.md').is_file())

    def test_no_background_discovery_is_started(self):
        service=Preview(self.settings,self.work)
        with patch('server.threading.Thread') as thread,patch.object(service,'refresh') as refresh:
            service.start_watch();thread.assert_not_called();refresh.assert_not_called()
        self.assertFalse(service.watch_state['enabled'])

if __name__=='__main__':unittest.main()
