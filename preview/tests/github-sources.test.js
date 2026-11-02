import test from 'node:test';
import assert from 'node:assert/strict';
import {githubSource,repositoryLinksFor} from '../web/model.js';

test('repository and exact skill folder come from declared metadata with a separate verified revision',()=>{
 const skill={repository_evidence:'Проверено в GitHub',source:{repository:'owner/library',url:'https://github.com/owner/library/tree/main/skills/example'},author_profile:{links:[
  {url:'https://github.com/owner',label:'GitHub автора'},
  {url:'https://github.com/owner/library/tree/main/skills/example'},
  {url:'https://github.com/owner/library/tree/abcdef/skills/example',label:'Навык в репозитории'}]}};
 const result=repositoryLinksFor(skill);assert.equal(result.repositories.length,1);
 assert.equal(result.repositories[0].url,'https://github.com/owner/library');
 assert.deepEqual(result.repositories[0].locations.map(l=>l.label),['Открыть папку навыка','Проверенная версия']);
 assert.equal(result.profiles[0].url,'https://github.com/owner');
});

test('third-party author links and explicit releases are supported without any ownership filter',()=>{
 const result=repositoryLinksFor({origin:'third_party',author_profile:{links:[{url:'https://github.com/vendor/tool'},{url:'https://github.com/vendor/tool/releases'}]}});
 assert.equal(result.repositories[0].url,'https://github.com/vendor/tool');assert.equal(result.repositories[0].locations[0].label,'Выпуски и загрузки');
});

test('a GitHub profile and a skill name never invent a repository or folder',()=>{
 const result=repositoryLinksFor({name:'example',author_profile:{links:[{url:'https://github.com/author'}]}});
 assert.equal(result.repositories.length,0);assert.equal(result.profiles.length,1);
 assert.deepEqual(repositoryLinksFor({name:'example',source:null}),{repositories:[],profiles:[]});
 assert.deepEqual(repositoryLinksFor({name:'example',author_profile:{links:[{url:'docs/README.md'}]}}),{repositories:[],profiles:[]});
});

test('repository-only metadata does not guess a package subdirectory',()=>{
 const result=repositoryLinksFor({name:'same-name',source:{repository:'vendor/tool.git'}});
 assert.equal(result.repositories[0].url,'https://github.com/vendor/tool');assert.deepEqual(result.repositories[0].locations,[]);
});

test('unsafe URLs and unrelated GitHub site routes do not become repository links',()=>{
 for(const value of ['owner/repo','javascript:alert(1)','https://github.com.evil.test/owner/repo','https://user:password@github.com/owner/repo','https://github.com/topics/skills','https://github.com:8443/owner/repo'])assert.equal(githubSource(value),null);
 const source=githubSource('https://github.com/owner/repo/tree/main/skills/a?token=private#fragment');
 assert.equal(source.url,'https://github.com/owner/repo/tree/main/skills/a');
});

test('independent declared sources retain separate repositories',()=>{
 const result=repositoryLinksFor({source:{repository:'owner/package'},author_profile:{links:[{url:'https://github.com/vendor/upstream/blob/main/SKILL.md'}]}});
 assert.equal(result.repositories.length,2);assert.equal(result.repositories[1].locations[0].label,'Открыть файл навыка');
});

test('a second metadata link never claims a verified version without evidence',()=>{
 const result=repositoryLinksFor({source:{url:'https://github.com/owner/library/tree/main/skills/example'},author_profile:{links:[{url:'https://github.com/owner/library/tree/old/skills/example',label:'Навык в репозитории'}]}});
 assert.equal(result.repositories[0].locations[1].label,'Дополнительный источник');
});
