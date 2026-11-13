'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {SearchIndex} = require('../../plugins/scarecrow/search');
function add(index,path,content,headings=[]) {index.add({path,tags:[],modified_ms:1},content,headings);}

test('BM25 score agrees with hand calculation; empty index and no hits are safe',()=>{
 const index = new SearchIndex();
 assert.deepEqual(index.search('needle'),[]);
 add(index,'a.md','needle');add(index,'b.md','hay hay hay');
 // N=2, df=1, tf=1, body length=1, average=2; no path/title match or pair bonus.
 const expected = Math.log(2)*2.2/(1+1.2*(0.25+0.75/2));
 assert.ok(Math.abs(index.search('needle')[0].score-expected)<1e-12);
 assert.deepEqual(index.search('absent'),[]);
 assert.deepEqual(index.search().map(m=>m.path),['a.md','b.md']);
});
test('short focused notes outrank long incidental matches; frequency saturates',()=>{
 const index = new SearchIndex();
 add(index,'a.md','needle');add(index,'b.md','needle '+'hay '.repeat(100));
 assert.equal(index.search('needle')[0].path,'a.md');
 const single = new SearchIndex(), repeated = new SearchIndex();
 add(single,'a.md','needle');add(repeated,'a.md','needle '.repeat(1000));
 assert.ok(repeated.search('needle')[0].score < 2.2*single.search('needle')[0].score);
});
test('titles and metadata headings contribute explicit field boosts',()=>{
 const index = new SearchIndex();
 add(index,'a.md','needle');add(index,'b.md','needle',['needle']);add(index,'needle.md','needle');
 assert.deepEqual(index.search('needle').map(m=>m.path),['needle.md','b.md','a.md']);
});
test('prefix and fuzzy are opt-in, report source terms, and do not invent exact phrases',()=>{
 const index = new SearchIndex();add(index,'a.md','inference server');
 assert.deepEqual(index.search('infer'),[]);
 let match=index.search('infer','prefix')[0];
 assert.deepEqual(match.term_matches,[{query:'infer',term:'inference',kind:'prefix'}]);
 assert.deepEqual(match.matching_lines,[{line:1,text:'inference server'}]);
 assert.deepEqual(index.search('in','prefix'),[]);
 for(const query of ['sever','serrver','serxer','sevrer']) {
  match=index.search(query,'fuzzy')[0];
  assert.equal(match.term_matches[0].term,'server');
  assert.equal(match.term_matches[0].kind,'fuzzy');
 }
 assert.deepEqual(index.search('sxxver','fuzzy'),[]);
 assert.deepEqual(index.search('srv','fuzzy'),[]);
 match=index.search('infer serv','prefix')[0];
 assert.deepEqual(match.matched_terms,['infer','serv']);
 assert.deepEqual(match.matched_phrases,[]);assert.deepEqual(match.nearby_pairs,[]);
 assert.deepEqual(index.search('server','fuzzy')[0].term_matches,[{query:'server',term:'server',kind:'exact'}]);
});
test('replacement and deletion remove obsolete postings and match a fresh rebuild',()=>{
 const index = new SearchIndex();add(index,'a.md','oldtoken');add(index,'b.md','needle needle');
 add(index,'a.md','needle');
 assert.deepEqual(index.search('oldtoken'),[]);
 index.remove('b.md');index.remove('missing.md');
 const fresh = new SearchIndex();add(fresh,'a.md','needle');
 assert.deepEqual(index.search('needle'),fresh.search('needle'));
 index.remove('a.md');assert.equal(index.postings.size,0);assert.deepEqual(index.search('needle'),[]);
});
test('Unicode normalization, deterministic ties and duplicate queries',()=>{
 const index=new SearchIndex();add(index,'b.md','ＣＡＦÉ');add(index,'a.md','café');
 assert.deepEqual(index.search('CAFÉ café!!!'),index.search('café'));
 assert.deepEqual(index.search('café').map(m=>m.path),['a.md','b.md']);
});
