from pathlib import Path
import json
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app/skill-catalog/scripts'))
import catalog
import skill_package


class SkillPackage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name).resolve();self.skill=self.home/'.codex/skills/example';self.skill.mkdir(parents=True)
        self.path=self.skill/'SKILL.md';self.path.write_text('---\nname: example\ndescription: Русское назначение\n---\n# Инструкция\nПолный русский оригинал.','utf-8')
        self.meta={'schema':1,'name':'example','instruction_language':'ru','helps':'Понятное описание','source':{'author':'Asemic','repository':'example/library','url':'https://github.com/example/library/tree/main/skills/example'},'documentation':[{'id':'README.md','title':'Назначение и запуск'}]}
        (self.skill/'README.md').write_text('# Возможности\nДокументация','utf-8')
        (self.skill/'agents').mkdir()
        (self.skill/'agents/openai.yaml').write_text('interface:\n  display_name: "Начать проект"\n  default_prompt: "Используй $example: подготовь согласованный план."\n','utf-8')
        self.save()
    def save(self):(self.skill/'catalog.json').write_text(json.dumps(self.meta,ensure_ascii=False),'utf-8')

    def test_native_description_author_prompt_and_documents_reach_card(self):
        def discovery(cwds,explicit):return {'data':[{'cwd':str(self.home),'skills':[{'name':'example','path':str(self.path),'scope':'user','enabled':True}]}]}
        data=self.home/'.codex/skill-catalog'
        catalog.refresh(data,self.home,str(self.home),discovery_fn=discovery)
        _,cards=catalog.load_cards(data,str(self.home));card=next(c for c in cards if c['name']=='example')
        self.assertEqual(card['title_ru'],'Начать проект');self.assertEqual(card['author_profile']['name'],'Asemic')
        self.assertTrue(card['instruction_localization']['readable']);self.assertEqual(card['description'],'Русское назначение')
        self.assertIn('$example',card['default_prompt']);self.assertTrue(card['activation']['supported'])
        docs=skill_package.documents(self.path,card['documentation'])
        self.assertIn('Документация',docs['README.md']['text'])

    def test_documents_cannot_escape_package_or_request_unsupported_files(self):
        (self.home/'private.md').write_text('private')
        self.meta['documentation'] += [{'id':'../../../private.md','title':'Outside'},{'id':'agents/openai.yaml','title':'Not markdown'}]
        self.save();meta=skill_package.load(self.path,'example')
        self.assertEqual([d['id'] for d in meta['documentation']],['README.md'])
        self.assertEqual(skill_package.documents(self.path,[{'id':'../../../private.md','title':'X'}]),{})

    def test_metadata_does_not_grant_installation_or_enabled_state(self):
        self.meta.update(installed=True,enabled=True,control={'supported':True},origin='builtin')
        self.save();meta=skill_package.load(self.path,'example')
        self.assertFalse(set(meta)&{'installed','enabled','control','origin'})
        (self.skill/'catalog.json').write_text('{broken')
        self.assertIsInstance(skill_package.load(self.path,'example'),dict)

    def test_multiple_prompts_are_read_as_text_and_keep_the_authors_default(self):
        self.meta['prompts']=[{'title':'Подготовить план','text':'Используй $example: подготовь план.'},
                              {'title':'Проверить результат','text':'Используй $example: проверь результат.'},
                              {'title':'Дубль','text':'Используй $example: подготовь план.'},
                              {'title':'bad','text':False}, {'title':'x'*161,'text':'bad'}]
        self.save()
        data=self.home/'.codex/skill-catalog'
        catalog.refresh(data,self.home,str(self.home),discovery_fn=lambda cwds,explicit:{'data':[]})
        _,cards=catalog.load_cards(data,str(self.home));card=next(c for c in cards if c['name']=='example')
        self.assertEqual([p['title'] for p in card['prompts']],['Подготовить план','Проверить результат'])
        self.assertEqual(card['default_prompt'],'Используй $example: подготовь согласованный план.')


if __name__=='__main__':unittest.main()
