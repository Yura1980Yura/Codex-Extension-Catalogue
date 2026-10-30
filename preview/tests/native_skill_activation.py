"""Opt-in real Codex verification with disposable profile, skills and a junction."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from controls import Controls

class NativeExactSkills(unittest.TestCase):
    def test_individual_skill_inside_real_disposable_plugin(self):
        with tempfile.TemporaryDirectory(prefix='catalogue-native-plugin-') as temp:
            root=Path(temp);home=root/'home';profile=home/'.codex';profile.mkdir(parents=True);project=root/'project';project.mkdir();(project/'.git').mkdir()
            plugin=project/'plugins/probe';skill=plugin/'skills/probe/SKILL.md';skill.parent.mkdir(parents=True)
            skill.write_text('---\nname: catalogue-plugin-probe\ndescription: Disposable verification only.\n---\nNo operations.\n')
            (plugin/'.codex-plugin').mkdir();(plugin/'.codex-plugin/plugin.json').write_text(json.dumps({'name':'probe','version':'1.0.0','skills':'./skills/'}))
            market=project/'.agents/plugins/marketplace.json';market.parent.mkdir(parents=True);market.write_text(json.dumps({'name':'catalogue-probe','plugins':[{'name':'probe','source':{'source':'local','path':'./plugins/probe'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}]}))
            (profile/'config.toml').write_text('[features]\nplugins=true\n[projects.'+json.dumps(str(project))+']\ntrust_level="trusted"\n[plugins."probe@catalogue-probe"]\nenabled=true\n')
            controls=Controls({'home':str(home),'source_data':str(root/'data'),'runtime':str(Path(__file__).resolve().parents[2]/'app')},root/'work')
            (root/'data').mkdir();discovery=sys.modules['discovery']
            discovery.request('plugin/install',{'marketplacePath':str(market),'pluginName':'probe'},codex_home=profile,process_cwd=str(project))
            read,_=discovery.request('skills/list',{'cwds':[str(project)],'forceReload':True},codex_home=profile,process_cwd=str(project))
            item=next(s for row in read['data'] for s in row['skills'] if s['name'].split(':')[-1]=='catalogue-plugin-probe');path=Path(item['path'])
            card={'id':'plugin:probe@catalogue-probe:probe','name':'probe','locations':[{'path':str(path),'kind':'discovered'}],'observations':[]}
            controls.storage.atomic_json(root/'data/inventory.json',{'skills':{card['id']:card}})
            for enabled in (False,True):
                state=controls.activation.state(card,home,path=path)
                result=controls.activation.change(root/'data',home,project,card['id'],enabled,state['revision'],request_fn=discovery.request,path=path)
                self.assertEqual(result['verification'],'confirmed')
            self.assertTrue(path.exists());print('Real plugin skill off/on confirmed',flush=True)

    def test_project_system_vendor_and_junction_off_on(self):
        real=Path.home()/'.codex/config.toml';original=real.read_bytes() if real.exists() else None
        with tempfile.TemporaryDirectory(prefix='catalogue-native-skills-') as temp:
            root=Path(temp);home=root/'home';profile=home/'.codex';profile.mkdir(parents=True);project=root/'project';project.mkdir();source=root/'data';source.mkdir();work=root/'work';work.mkdir()
            controls=Controls({'home':str(home),'source_data':str(source),'runtime':str(Path(__file__).resolve().parents[2]/'app')},work)
            a=controls.activation;discovery=sys.modules['discovery']
            def create(path,name):
                path.parent.mkdir(parents=True);path.write_text('---\nname: '+name+'\ndescription: Disposable verification only.\n---\nNo operations.\n');return path
            paths=[('local:project',create(project/'.agents/skills/project-probe/SKILL.md','project-probe')),('vendor:probe',create(profile/'skills/vendor-probe/SKILL.md','vendor-probe'))]
            target=create(root/'shared/link-probe/SKILL.md','link-probe');alias=profile/'skills/link-probe'
            if os.name=='nt':
                completed=subprocess.run(['cmd','/c','mklink','/J',str(alias),str(target.parent)],capture_output=True)
                self.assertEqual(completed.returncode,0)
            else:alias.symlink_to(target.parent,target_is_directory=True)
            paths.append(('local:alias',alias/'SKILL.md'))
            read,_=discovery.request('skills/list',{'cwds':[str(project)],'forceReload':True},codex_home=profile,process_cwd=str(project))
            builtin=next(s for row in read['data'] for s in row['skills'] if s['scope']=='system');paths.append(('system:probe',Path(builtin['path'])))
            for key,path in paths:
                with self.subTest(key=key):
                    card={'id':key,'name':path.parent.name,'locations':[{'path':str(path),'kind':'installation'}],'observations':[]}
                    controls.storage.atomic_json(source/'inventory.json',{'skills':{key:card}})
                    digest=hashlib.sha256(path.read_bytes()).hexdigest()
                    for enabled in (False,True):
                        state=a.state(card,home,path=path)
                        result=a.change(source,home,project,key,enabled,state['revision'],request_fn=discovery.request,path=path)
                        self.assertEqual(result['verification'],'confirmed');self.assertEqual(a.state(card,home,path=path)['enabled'],enabled)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
                    print('Real Codex off/on confirmed:',key,flush=True)
        self.assertEqual(real.read_bytes() if real.exists() else None,original)

if __name__=='__main__':unittest.main()
