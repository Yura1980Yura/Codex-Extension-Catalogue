"""Opt-in: real Codex discovery around deletion of a disposable project skill."""
import hashlib, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skill_files import SkillFiles
from collect import runtime_path
sys.path.insert(0, str(runtime_path({})/'skill-catalog/scripts'))
import discovery


class NativeSkillFiles(unittest.TestCase):
    def test_codex_stops_finding_removed_instruction_and_finds_restored_bytes(self):
        with tempfile.TemporaryDirectory(prefix='catalog-skill-removal-') as folder:
            root=Path(folder).resolve()
            project=root/'project'; project.mkdir()
            skill=project/'.agents/skills/catalog-removal-probe/SKILL.md'
            skill.parent.mkdir(parents=True)
            original=b'---\nname: catalog-removal-probe\ndescription: Disposable catalogue verification only.\n---\nDo not execute any operations.\n'
            skill.write_bytes(original)
            support=skill.with_name('support.txt'); support.write_text('Keep this file',encoding='utf-8')
            files=SkillFiles({'home':str(Path.home())},root/'work')
            snapshot={'projects':[{'id':'probe','name':'Probe','path':str(project)}],
                'addons':[{'id':'probe','components':[{'id':'skill','kind':'skill',
                    'skill_id':'local:probe','path':str(skill),'installed':True}]}]}
            events=[]
            def detected():
                result,_=discovery.request('skills/list',{'cwds':[str(project)],'forceReload':True},process_cwd=str(project))
                self.assertFalse([e for row in result['data'] for e in row.get('errors',[])])
                return [s for row in result['data'] for s in row['skills'] if Path(s['path']).resolve()==skill]
            def apply(payload):
                plan=files.plan(snapshot,payload)
                return files.apply(snapshot,{**payload,'revision':plan['revision'],'confirmed':True},events.append)
            self.assertEqual(len(detected()),1)
            removed=apply({'action':'remove','id':'probe','component_id':'skill'})
            self.assertFalse(skill.exists()); self.assertEqual(detected(),[])
            self.assertEqual(Path(removed['backup']).read_bytes(),original)
            self.assertEqual(support.read_text('utf-8'),'Keep this file')
            apply({'action':'restore','operation_id':removed['operation_id']})
            self.assertEqual(skill.read_bytes(),original); self.assertEqual(len(detected()),1)
            self.assertEqual([e['action'] for e in events],['remove','restore'])
            print('Fresh Codex: present -> absent -> present; support preserved; restored SHA256 '+hashlib.sha256(original).hexdigest())

if __name__=='__main__': unittest.main()
