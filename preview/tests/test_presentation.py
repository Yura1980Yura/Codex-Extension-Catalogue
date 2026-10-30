from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'preview'),str(ROOT/'app/skill-catalog/scripts')]
import skill_package
from presentation import enrich,initial_tags
from skill_repositories import match


class Presentation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.instruction=self.root/'SKILL.md'
        self.instruction.write_text('---\nname: product-workshop\ndescription: Исследование\n---\n# Навык','utf-8')
        self.skill={'id':'one','name':'product-workshop','origin':'personal','author_profile':{'name':'55user3125','links':[]}}
        self.addon={'id':'a','title':'Продуктовая мастерская','skills':[self.skill],'components':[],'tags':[],'directions':[],'profile':{}}
        self.instructions={'one':{'text':self.instruction.read_text('utf-8'),'path':str(self.instruction)}}

    def test_refresh_discovers_added_changed_and_deleted_documents(self):
        folder=self.root/'references';folder.mkdir();doc=folder/'research.md';doc.write_text('# Исследование\nПервая версия','utf-8')
        report=enrich([self.addon],self.instructions,skill_package,{},[])
        self.assertEqual(report['documents'],1)
        self.assertIn('Первая версия',self.instructions['one']['documents']['references/research.md']['text'])
        doc.write_text('# Исследование\nВторая версия','utf-8')
        (self.root/'README.md').write_text('# Запуск\nТребования','utf-8')
        report=enrich([self.addon],self.instructions,skill_package,{},[])
        self.assertEqual(report['documents'],2)
        self.assertIn('Вторая версия',self.instructions['one']['documents']['references/research.md']['text'])
        doc.unlink();report=enrich([self.addon],self.instructions,skill_package,{},[])
        self.assertEqual(report['documents'],1)
        self.assertEqual([row['id'] for row in self.skill['documentation']],['README.md'])

    def test_nested_skills_and_outside_documents_are_not_relabelled_as_package_docs(self):
        (self.root/'README.md').write_text('# Главный документ','utf-8')
        nested=self.root/'another';nested.mkdir();(nested/'SKILL.md').write_text('different skill','utf-8');(nested/'README.md').write_text('# Другая инструкция','utf-8')
        entries,issues=skill_package.document_index(self.root,[{'id':'../outside.md','title':'Чужой'}])
        self.assertEqual([d['id'] for d in entries],['README.md']);self.assertEqual(issues[0]['id'],'../outside.md')

    def test_broken_optional_metadata_does_not_hide_existing_readme(self):
        (self.root/'catalog.json').write_text('{invalid','utf-8');(self.root/'README.md').write_text('# Запуск','utf-8')
        info=skill_package.load(self.instruction,'product-workshop')
        self.assertEqual(info['documentation'][0]['id'],'README.md');self.assertTrue(info['documentation_issues'])

    def test_repository_match_is_evidence_not_a_name_only_claim_for_other_authors(self):
        raw=self.instruction.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        index={'repository':'owner/library','revision':'a'*40,'status':'verified','checked_at':'2026-10-30T10:00:00Z','skills':{'product-workshop':[{'path':'skills/product-workshop','sha':blob}]}}
        hit=match(self.skill,self.instruction,index);self.assertIn('/tree/'+('a'*40)+'/skills/product-workshop',hit['url']);self.assertIn('совпадает',hit['evidence'])
        index['skills']['product-workshop'][0]['sha']='changed'
        self.assertIsNone(match(self.skill,self.instruction,index))
        self.skill['source']={'repository':'owner/library'}
        self.assertIn('отличается',match(self.skill,self.instruction,index)['evidence'])
        self.skill.update(origin='third_party',source={'repository':'different/repo'})
        self.assertIsNone(match(self.skill,self.instruction,index))

    def test_tags_are_initial_defaults_and_do_not_change_installation_facts(self):
        self.addon['tags']=['свой тег'];report=enrich([self.addon],self.instructions,skill_package,{},[])
        self.assertIn('свой тег',self.addon['tags']);self.assertIn('техническое задание',self.addon['tags'])
        self.assertNotIn('installed',self.skill);self.assertTrue(self.skill['instruction_available'])
        for name in ('aria-review','dialogue-gym','unknown-service','artifact-template-financial-budget','plugin-management'):
            self.assertTrue(initial_tags({'id':name,'title':name,'skills':[],'components':[]},[]))


if __name__=='__main__':unittest.main()
