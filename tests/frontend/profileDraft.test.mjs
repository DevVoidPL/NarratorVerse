import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

// Use the project's existing compiler; no added test framework or browser mock.
const source=await readFile(new URL('../../src/profileDraft.ts',import.meta.url),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const {createDraft,receiveProfile,editDraft,editOcr,isDirty,savePayload,savedMatches}=
 await import('data:text/javascript;base64,'+Buffer.from(compiled).toString('base64'));
const profile=(id='one')=>({id,name:'Test',settings:{speech_rate:1,volume:.85,capture_source:'window',read_speaker_names:false,audio_balance_db:-12},ocr:{mode:'automatic'}});

test('edits do not mutate the persisted profile; only edited keys are sent',()=>{
 const saved=profile();let draft=createDraft(saved);
 draft=editDraft(draft,'speech_rate',1.3);draft=editDraft(draft,'speech_rate',1.4);
 draft=editDraft(draft,'read_speaker_names',true);
 assert.equal(saved.settings.speech_rate,1);
 assert.deepEqual(savePayload(draft),{values:{speech_rate:1.4,read_speaker_names:true}});
 assert.equal(isDirty(draft),true);
});
test('profile events and tab navigation cannot erase a dirty draft',()=>{
 const saved=profile();const draft=editDraft(createDraft(saved),'volume',.4);
 assert.equal(receiveProfile(draft,{...saved,settings:{...saved.settings,volume:.8}}),draft);
});
test('changing profile or discarding starts from saved values',()=>{
 const draft=editDraft(createDraft(profile()),'volume',.3);
 const other=receiveProfile(draft,profile('two'));
 assert.equal(other.profileId,'two');assert.equal(other.values.volume,.85);
 assert.equal(isDirty(other),false);assert.equal(isDirty(createDraft(profile())),false);
});
test('OCR mode is an independent dirty edit and is sent even with no value changes',()=>{
 const draft=editOcr(createDraft(profile()),'classic');
 assert.equal(isDirty(draft),true);
 assert.deepEqual(savePayload(draft),{values:{},ocr_mode:'classic'});
 assert.equal(savedMatches(draft,profile()),false);
 assert.equal(savedMatches(draft,{...profile(),ocr:{mode:'classic'}}),true);
});
test('successful save requires readback of the same profile and values',()=>{
 const saved=profile();const draft=editDraft(createDraft(saved),'audio_balance_db',-18);
 assert.equal(savedMatches(draft,saved),false);
 const updated={...saved,settings:{...saved.settings,audio_balance_db:-18}};
 assert.equal(savedMatches(draft,updated),true);
 assert.equal(savedMatches(draft,{...updated,id:'other'}),false);
 assert.equal(isDirty(createDraft(updated)),false);
});
test('capture source is part of the same profile save payload',()=>{
 const draft=editDraft(createDraft(profile()),'capture_source','monitor');
 assert.deepEqual(savePayload(draft),{values:{capture_source:'monitor'}});
});

test('UI uses Polish labels only; language of subtitles remains selectable',async()=>{
 const app=await readFile(new URL('../../src/App.svelte',import.meta.url),'utf8');
 assert.ok(!app.includes('settingsOpen'));
 assert.ok(!app.includes('sidebar-bottom'));
 assert.ok(!app.includes("getItem('language')"));
 assert.ok(app.includes('value="english_to_polish"'));
 assert.ok(app.includes('value="polish"'));
 assert.ok(app.includes('u.importVoice'));
 assert.ok(app.includes("rpc('settings',savePayload(submitted))"));
 assert.ok(app.includes('savedMatches(submitted,saved)'));
 const {compile}=await import('svelte/compiler');
 // Compile without running Tauri. Also check the two dialogs/icons components.
 for(const name of ['App','RegionEditor','Icon']){
   const code=await readFile(new URL(`../../src/${name}.svelte`,import.meta.url),'utf8');
   const result=compile(code,{filename:`${name}.svelte`,generate:'client'});
   assert.deepEqual(result.warnings,[],`${name}: ${JSON.stringify(result.warnings)}`);
 }
});

test('Polish-only dictionaries and ASCII README stay consistent',async()=>{
 const app=await readFile(new URL('../../src/App.svelte',import.meta.url),'utf8');
 const editor=await readFile(new URL('../../src/RegionEditor.svelte',import.meta.url),'utf8');
 const dictionaries={};
 for(const name of ['i18n','ui','adaptive','audioBalance']){
   const code=await readFile(new URL(`../../src/${name}.ts`,import.meta.url),'utf8');
   assert.ok(!/\b(?:en|es|pl)\s*:\s*\{/.test(code),`${name} still has language variants`);
   const js=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
   dictionaries[name]=Object.values(await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64')))[0];
 }
 for(const [alias,name] of [['t','i18n'],['u','ui'],['a','adaptive'],['b','audioBalance']]){
   const code=alias==='t'?app+'\n'+editor:app;
   for(const match of code.matchAll(new RegExp(`\\b${alias}\\.([A-Za-z][A-Za-z0-9_]*)`,'g'))){
     assert.ok(Object.hasOwn(dictionaries[name],match[1]),`Missing label ${alias}.${match[1]}`);
   }
 }
 const readme=await readFile(new URL('../../README.md',import.meta.url),'utf8');
 assert.ok(/^[\x00-\x7f]*$/.test(readme),'README must be Polish without diacritics');
 const dictionary=await readFile(new URL('../../src/i18n.ts',import.meta.url),'utf8');
 assert.ok(dictionary.includes('Czytaj imiona postaci'));
});