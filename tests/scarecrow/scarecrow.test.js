'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {Operations}=require('../../plugins/scarecrow/operations');
const {fixture,start}=require('./fixture');
function temp(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'scarecrow-test-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}
test('browse, search, sections, metadata, links and tag counts',async t=>{
 const data=fixture(temp(t)), ops=new Operations(data.app);
 assert.deepEqual((await ops.run({action:'list'})).entries.map(e=>e.path),['People','Welcome.md']);
 assert.equal((await ops.run({action:'search',query:'banjo',tag:'music',folder:'People'})).total,1);
 assert.equal((await ops.run({action:'search',query:'absent'})).total,0);
 assert.equal((await ops.run({action:'tags'})).tags[0].notes,1);
 assert.equal((await ops.run({action:'read',path:'Welcome.md',section:'Details'})).content,'# Details\nTest code: STRAW-42\n');
 assert.equal((await ops.run({action:'inspect',path:'People/Alice.md'})).properties.alias,'Friend');
 const links=await ops.run({action:'links',path:'Welcome.md'});
 assert.equal(links.outgoing[0].path,'People/Alice.md');assert.equal(links.outgoing[1].resolved,false);
 assert.equal(links.backlinks[0].path,'People/Alice.md');
 await ops.run({action:'open',path:'Welcome.md'});assert.equal(data.opened(),'Welcome.md');
 await assert.rejects(ops.run({action:'open',path:'Missing.md'}));assert.equal(data.files.has('Missing.md'),false);
});
test('reject writes, paths, hidden files and symlinks, including search and graph results',async t=>{
 const root=temp(t),data=fixture(root),ops=new Operations(data.app);
 fs.symlinkSync(path.join(root,'.obsidian/secret.md'),path.join(root,'Leak.md'));
 data.files.set('Leak.md',{path:'Leak.md',extension:'md'});
 for(const form of [{action:'write',path:'Welcome.md'},{action:'read',path:'../secret'},{action:'read',path:'/etc/passwd'},
 {action:'read',path:'.obsidian/secret.md'},{action:'read',path:'Leak.md'},{action:'read',path:'Welcome.md',code:'x'}])await assert.rejects(ops.run(form));
 assert.equal((await ops.run({action:'search',query:'SECRET'})).total,0);
 data.cache['Welcome.md'].links.push({link:'Leak'});
 data.app.metadataCache.resolvedLinks['Leak.md']={'Welcome.md':1};
 const result=await ops.run({action:'links',path:'Welcome.md'});
 assert.equal(JSON.stringify(result).includes('Leak'),false);
});
test('missing and duplicate heading/cache errors are explicit',async t=>{
 const data=fixture(temp(t)),ops=new Operations(data.app);
 data.cache['Welcome.md'].headings.push(data.cache['Welcome.md'].headings[0]);
 await assert.rejects(ops.run({action:'read',path:'Welcome.md',section:'Welcome'}),/ambiguous/);
 await assert.rejects(ops.run({action:'read',path:'Welcome.md',section:'Unknown'}),/not found/);
 delete data.cache['Welcome.md'];await assert.rejects(ops.run({action:'inspect',path:'Welcome.md'}),/not ready/);
});
test('HTTP authentication, origin, routes, reset, large results and shutdown',async t=>{
 const root=temp(t),data=await start(root),{server,settings}=data;
 t.after(()=>{server.close();server.closeAllConnections();});
 const url=`http://127.0.0.1:${settings.port}`;
 const headers={Authorization:'Bearer '+settings.token,'Content-Type':'application/json'};
 assert.equal((await fetch(url+'/v1/status')).status,403);
 assert.equal((await fetch(url+'/v1/status',{headers:{...headers,Origin:'https://example.com'}})).status,403);
 assert.equal((await (await fetch(url+'/v1/status',{headers})).json()).vault_id,'fixture');
 assert.equal((await fetch(url+'/v1/query',{method:'DELETE',headers})).status,404);
 const call=body=>fetch(url+'/v1/query',{method:'POST',headers,body:JSON.stringify(body)});
 assert.equal((await call({action:'delete',path:'Welcome.md'})).status,400);
 fs.writeFileSync(path.join(root,'Welcome.md'),'large text '.repeat(110000));
 assert.ok((await (await call({action:'read',path:'Welcome.md'})).json()).data.content.length>1000000);
 fs.unlinkSync(path.join(root,'Generated/.marionette-managed'));
 assert.equal((await call({action:'read',path:'Welcome.md'})).status,503);
 await new Promise(resolve=>server.close(resolve));server.closeAllConnections();
 await assert.rejects(fetch(url+'/v1/status',{headers}));
});
test('plugin load/unload and reload release listener',async t=>{
 const Module=require('node:module'),original=Module._load, data=fixture(temp(t));
 class Plugin {loadData(){return {port:27125,token:'a'.repeat(64),vault_id:'fixture'};}addSettingTab(tab){this.tab=tab;}registerEvent(){}}
 Module._load=function(name,...rest){if(name==='obsidian')return {Plugin,PluginSettingTab:class{constructor(){this.containerEl={empty(){}};}},Setting:class{setName(){return this;}setDesc(text){assert.equal(typeof text,'string');return this;}},Notice:class{}};return original.call(this,name,...rest);};
 let Scarecrow;try{Scarecrow=require('../../plugins/scarecrow/main');}finally{Module._load=original;}
 for(let i=0;i<2;i++){
  const plugin=new Scarecrow();plugin.app=data.app;
  await plugin.onload();t.after(()=>plugin.onunload());
  await new Promise((resolve,reject)=>{plugin.server.once('listening',resolve);plugin.server.once('error',reject);});
  assert.equal(plugin.ready,true);plugin.tab.display();
  const server=plugin.server;const closed=new Promise(resolve=>server.once('close',resolve));plugin.onunload();await closed;
  assert.equal(plugin.server,null);assert.equal(plugin.ready,false);
 }
});
test('authenticated diagnostics stream correlates requests without content and ends on unload',async t=>{
 const {server,settings}=await start(temp(t));
 t.after(()=>{server.close();server.closeAllConnections();});
 const url=`http://127.0.0.1:${settings.port}`,headers={Authorization:'Bearer '+settings.token};
 assert.equal((await fetch(url+'/v1/events')).status,403);
 const stream=await fetch(url+'/v1/events',{headers});
 assert.equal(stream.headers.get('x-vault-id'),'fixture');
 const reader=stream.body.getReader(), decoder=new TextDecoder();let text='';
 const until=async needle=>{while(!text.includes(needle)){const chunk=await reader.read();assert.equal(chunk.done,false);text+=decoder.decode(chunk.value);} };
 await until('listener_observed');
 const request_id='12345678-1234-1234-1234-123456789abc';
 const result=await fetch(url+'/v1/query',{method:'POST',headers:{...headers,'Content-Type':'application/json','X-Request-ID':request_id},body:JSON.stringify({action:'search',query:'private search'})});
 assert.equal(result.headers.get('x-request-id'),request_id);
 await result.json();await until('request_completed');
 assert.ok(text.includes(request_id));assert.ok(text.includes('duration_ms'));assert.ok(text.includes('"action":"search"'));
 assert.equal(text.includes('private search'),false);assert.equal(text.includes(settings.token),false);assert.equal(text.includes('STRAW-42'),false);
 const denied=await fetch(url+'/v1/query',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:'{"action":"write"}'});
 await denied.json();await until('request_failed');
 server.endDiagnostics();await until('plugin_stopping');
 await reader.cancel();
});

test('rank partial matches with rarity, bounded proximity and ordered phrases',async t=>{
 const root=temp(t),data=fixture(root),ops=new Operations(data.app);
 function add(name,text){fs.writeFileSync(path.join(root,name),text);data.files.set(name,{path:name,extension:'md',stat:{mtime:123}});data.cache[name]={};}
 add('A.md','Marionette inference server');
 add('B.md','Marionette server inference');
 add('C.md','Marionette\ninference\nserver');
 add('D.md','server');
 add('E.md','observer');
 let result=await ops.run({action:'search',query:'Marionette inference server'});
 assert.deepEqual(result.matches.map(m=>m.path),['A.md','B.md','C.md','D.md']);
 assert.deepEqual(result.matches[0].matched_phrases,['marionette inference','inference server']);
 assert.deepEqual(result.matches[3].missing_terms,['marionette','inference']);
 assert.deepEqual(result.matches[2].nearby_pairs,[]);
 assert.deepEqual(result.matches[0].matching_lines,[{line:1,text:'Marionette inference server'}]);
 const score=result.matches[0].score;
 result=await ops.run({action:'search',query:'MARIONETTE inference server server!!!'});
 assert.equal(result.matches[0].score,score);
 assert.deepEqual((await ops.run({action:'search',query:'absentword server'})).matches.map(m=>m.path).sort(),['A.md','B.md','C.md','D.md']);
 add('Rare.md','quokka');
 result=await ops.run({action:'search',query:'server quokka'});
 assert.equal(result.matches[0].path,'Rare.md');
 add('Far.md','alpha '+ 'padding '.repeat(12)+'beta');
 add('Near.md','alpha '+ 'padding '.repeat(11)+'beta');
 result=await ops.run({action:'search',query:'alpha beta'});
 assert.deepEqual(result.matches.map(m=>m.path),['Near.md','Far.md']);
 assert.deepEqual(result.matches[1].nearby_pairs,[]);
 add('Unicode.md','ＣＡＦÉ llama.cpp');
 assert.equal((await ops.run({action:'search',query:'café LLAMA.CPP'})).matches[0].path,'Unicode.md');
 assert.equal((await ops.run({action:'search',query:'banjo absent',folder:'People',tag:'music'})).total,1);
 assert.equal((await ops.run({action:'search',query:'server',folder:'People'})).total,0);
 assert.equal((await ops.run({action:'search',folder:'People'})).matches[0].score,0);
 for(const query of ['', '   ', '!!!']) await assert.rejects(ops.run({action:'search',query}),/at least one|Search needs/);
 assert.equal((await ops.run({action:'search',query:'notpresent'})).total,0);
});

test('search modes preserve filters and refresh after edits, renames and deletes',async t=>{
 const root=temp(t),data=fixture(root),ops=new Operations(data.app);
 assert.equal((await ops.run({action:'search',query:'banj'})).total,0);
 assert.equal((await ops.run({action:'search',query:'banj',mode:'prefix',tag:'music',folder:'People'})).total,1);
 assert.equal((await ops.run({action:'search',query:'banjp',mode:'fuzzy',folder:'People'})).total,1);
 assert.equal((await ops.run({action:'search',query:'banj',mode:'prefix',tag:'other'})).total,0);
 await assert.rejects(ops.run({action:'search',query:'banjo',mode:'unknown'}),/mode/);
 await assert.rejects(ops.run({action:'read',path:'Welcome.md',mode:'fuzzy'}),/Unexpected/);
 fs.writeFileSync(path.join(root,'People/Alice.md'),'New mandolin');
 assert.equal((await ops.run({action:'search',query:'banjo'})).total,0);
 assert.equal((await ops.run({action:'search',query:'mandolin'})).total,1);
 fs.renameSync(path.join(root,'People/Alice.md'),path.join(root,'People/Renamed.md'));
 const file=data.files.get('People/Alice.md');data.files.delete(file.path);
 file.path='People/Renamed.md';data.files.set(file.path,file);data.cache[file.path]=data.cache['People/Alice.md'];
 assert.equal((await ops.run({action:'search',query:'mandolin'})).matches[0].path,'People/Renamed.md');
 fs.unlinkSync(path.join(root,file.path));data.files.delete(file.path);
 assert.equal((await ops.run({action:'search',query:'mandolin'})).total,0);
});
