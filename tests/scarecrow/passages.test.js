'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {splitPassages,readPassage}=require('../../plugins/scarecrow/passages');
const {Operations}=require('../../plugins/scarecrow/operations');
const {fixture}=require('./fixture');
const conversationPath='Generated/Contacts/Person/Conversations/session.md';
function literal(value){const runs=value.match(/`+/g)||[];const fence='`'.repeat(Math.max(3,...runs.map(s=>s.length+1),4));return fence+'text\n'+value+'\n'+fence+'\n';}
function message(id,kind,correlation,body) {
 const role=kind==='input'?'user':'assistant';
 return `## ${role} — time\n\nRecord ${id}\n\n`+literal(body)+'\n> [!info]- Message identifiers and status\n'+
 literal(JSON.stringify({id,message_id:correlation,role,kind},null,2)).trimEnd().split('\n').map(line=>'> '+line).join('\n')+'\n\n';
}
const header='---\nsession_id: "s"\nconversation_id: "c"\n---\n\n# Conversation\n\n';
test('export-shaped messages pair by correlation ID and retain source identifiers',()=>{
 const content=header+message(1,'input','a','GPU server?\n## literal fake heading')+message(2,'answer','a','Use Vulkan.')+
 message(3,'input','b','Dinner?')+message(4,'answer','different','Unmatched answer.');
 const passages=splitPassages(conversationPath,content);
 assert.equal(passages.length,3);
 assert.deepEqual(passages[0].messages.map(m=>m.record_id),[1,2]);
 assert.ok(passages[0].excerpt.includes('Use Vulkan'));
 assert.ok(!passages[0].excerpt.includes('Dinner'));
 for(const p of passages) assert.equal(content.split('\n').slice(p.start_line-1,p.end_line).join('\n'),p.excerpt);
 const result=readPassage(conversationPath,content,passages[0].passage_id,true);
 assert.ok(result.content.includes('Dinner'));assert.ok(!result.content.includes('Unmatched answer'));
 assert.equal(readPassage(conversationPath,content+'changed',passages[0].passage_id),null);
 assert.equal(splitPassages(conversationPath,content)[0].passage_id,passages[0].passage_id);
});
test('heading sections do not overlap and ignore fenced headings; long sections split at paragraphs',()=>{
 const content='# First\nserver\n```text\n## fake\n```\n## Second\nGPU';
 const parts=splitPassages('guide.md',content);
 assert.equal(parts.length,2);assert.equal(parts[1].heading,'Second');assert.equal(parts[1].start_line,6);
 const long='# Long\n\n'+('word '.repeat(610)+'\n\n').repeat(3)+'# Next\nother';
 const chunks=splitPassages('guide.md',long);
 assert.equal(chunks.length,4);
 assert.equal(chunks[0].unit,chunks[2].unit);
 assert.ok(readPassage('guide.md',long,chunks[1].passage_id,true).content.includes('other'));
 assert.equal(splitPassages('empty.md','').length,0);
});
test('passage ranking isolates scattered matches, groups hits, and reads exact or neighboring context',async t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'passage-test-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 const data=fixture(root),ops=new Operations(data.app);
 function add(name,text){fs.writeFileSync(path.join(root,name),text);data.files.set(name,{path:name,extension:'md',stat:{mtime:1}});data.cache[name]={};}
 add('GPU server.md','# Unrelated\ndinner recipe');
 add('Scattered.md','# One\nGPU\n# Two\nserver');
 add('Focused.md','# Hardware\nGPU server\n# Food\ndinner recipe\n# More hardware\nGPU server memory');
 const result=await ops.run({action:'search',query:'GPU server'});
 assert.equal(result.matches[0].path,'Focused.md');
 const pathOnly=result.matches.find(m=>m.path==='GPU server.md');
 assert.deepEqual(pathOnly.matched_phrases,[]);assert.deepEqual(pathOnly.matching_lines,[]);
 const focused=result.matches[0];assert.equal(focused.passages.length,2);
 const scattered=result.matches.find(m=>m.path==='Scattered.md');
 assert.ok(scattered.passages.every(p=>p.matched_terms.length===1));
 assert.equal(scattered.matched_terms.length,1);
 assert.ok(focused.passages[0].matching_lines.every(line=>line.line>=focused.passages[0].start_line));
 const hit=focused.passages[0];
 const read=await ops.run({action:'read',path:focused.path,passage_id:hit.passage_id});
 assert.equal(read.content,hit.excerpt);
 const neighbors=await ops.run({action:'read',path:focused.path,passage_id:hit.passage_id,context:'neighbors'});
 assert.ok(neighbors.content.includes('dinner recipe'));
 await assert.rejects(ops.run({action:'read',path:focused.path,context:'neighbors'}),/Context/);
 await assert.rejects(ops.run({action:'read',path:focused.path,passage_id:hit.passage_id,section:'Hardware'}),/without section/);
 add('Focused.md','Changed');
 await assert.rejects(ops.run({action:'read',path:focused.path,passage_id:hit.passage_id}),/stale/);
});
