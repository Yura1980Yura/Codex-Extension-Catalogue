from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import build, scope_of

def skill(name='test', plugin=False):
    return {'id': 'plugin:bundle@market:'+name if plugin else 'local:'+name, 'name': name, 'state': 'present', 'source': {'plugin_id': 'bundle@market'} if plugin else {}, 'locations': [], 'observations': [], 'resource_ids': [], 'bundle': {'apps': ['connector_test'], 'title': 'Bundle'} if plugin else {}}
def installation(card):
    return {'entries': []}
def resource(id, connections=()):
    return {'id': id, 'connection_ids': list(connections), 'profile': {'title': id}, 'skills': []}

class Composition(unittest.TestCase):
    def test_declared_app_and_skill_are_one_extension(self):
        s=skill(plugin=True)
        views={'all':{'services':[{'id':'app:connector_test','name':'App','kind':'app','configured':True,'enabled':True,'sources':[]}]}}
        result=build([s],views,[resource('resource:test',['app:connector_test'])],[],installation)
        self.assertEqual(len(result),1)
        self.assertEqual({c['kind'] for c in result[0]['components']},{'app','skill','plugin'})

    def test_alias_does_not_leave_an_empty_duplicate(self):
        views={'all':{'services':[{'id':'mcp:blender_zoo_cafe','name':'Blender','kind':'mcp','configured':True,'sources':[]}]}}
        result=build([],views,[resource('resource:blender'),resource('resource:connection-old',['mcp:blender_zoo_cafe'])],[],installation,{'connections':{'mcp:blender_zoo_cafe':'resource:blender'}})
        self.assertEqual([a['id'] for a in result],['resource:blender'])

    def test_related_resource_is_not_composition(self):
        s=skill();s['resource_ids']=['resource:blender']
        result=build([s],{},[resource('resource:blender')],[],installation)
        own=next(a for a in result if a['skills'])
        self.assertNotEqual(own['id'],'resource:blender')
        self.assertIn('resource:blender',own['related'])

    def test_shared_helper_app_does_not_replace_existing_bundle_identity(self):
        s=skill(plugin=True)
        views={'all':{'services':[{'id':'app:connector_test','name':'Controller','kind':'app','configured':True,'sources':[]},{'id':'plugin:bundle@market','name':'Bundle','kind':'plugin','configured':True,'sources':[]}]}}
        result=build([s],views,[resource('resource:controller',['app:connector_test']),resource('resource:bundle',['plugin:bundle@market'])],[],installation)
        bundle=next(a for a in result if a['id']=='resource:bundle')
        self.assertEqual(len(bundle['skills']),1)
        self.assertIn('resource:controller',bundle['related'])

    def test_scope_uses_applied_layer(self):
        self.assertEqual(scope_of([{'scope':'user','applied':True},{'scope':'project','applied':False}]),'global')
        self.assertEqual(scope_of([{'scope':'user','applied':True},{'scope':'project','applied':True}]),'local')

    def test_cache_does_not_count_as_installed(self):
        s=skill(plugin=True);s.update(state='unconfirmed',has_user_annotations=True)
        result=build([s],{},[],[],installation)
        self.assertFalse(any(c.get('installed') for c in result[0]['components']))

if __name__=='__main__':unittest.main()
