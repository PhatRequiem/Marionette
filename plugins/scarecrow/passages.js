'use strict';
const {createHash} = require('node:crypto');
const {tokens} = require('./search');

// Parse headings from the same text we score, never from a possibly stale cache.
// Fences protect literal headings inside exported conversations and code samples.
function headings(lines) {
  const result=[]; let fence=null, front=lines[0]==='---';
  for(let i=0;i<lines.length;i++) {
    const line=lines[i];
    if(front) {if(i && line==='---') front=false;continue;}
    const marker=line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
    if(fence) {
      if(marker && marker[1][0]===fence[0] && marker[1].length>=fence.length && !marker[2].trim()) fence=null;
      continue;
    }
    if(marker) {fence=marker[1];continue;}
    const h=line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if(h) result.push({start:i,level:h[1].length,title:h[2]});
  }
  return result;
}
function message(lines,start,end) {
  const text=lines.slice(start,end).join('\n');
  // Metadata is a separate quoted block written by our exporter, after the body fence.
  const match=text.match(/\n> \[!info\]- Message identifiers and status\n> (`{3,})text\n([\s\S]*?)\n> \1\s*$/);
  if(!match) return null;
  try {
    const data=JSON.parse(match[2].split('\n').map(line=>line.replace(/^> ?/,'')).join('\n'));
    const record=text.match(/^## [^\n]+\n\nRecord (\d+)\n/);
    if(!record || String(data.id)!==record[1] || !['input','answer'].includes(data.kind)) return null;
    return {record_id:data.id,message_id:data.message_id,role:data.role,kind:data.kind,recorded_at:typeof data.recorded_at==='string' ? data.recorded_at : null};
  } catch {return null;}
}
function splitPassages(path,content) {
  const lines=content.split('\n'), hs=headings(lines), units=[];
  const conversation=path.startsWith('Generated/Contacts/') && path.includes('/Conversations/') &&
    /^---\n/.test(content) && /^session_id:/m.test(content.split('\n---')[0]) && /^conversation_id:/m.test(content.split('\n---')[0]);
  if(conversation) {
    const starts=hs.filter(h=>h.level===2);
    for(let i=0;i<starts.length;i++) {
      const h=starts[i], end=starts[i+1]?.start ?? lines.length;
      const meta=message(lines,h.start,end), prior=units.at(-1);
      if(meta?.kind==='answer' && meta.role==='assistant' && meta.message_id &&
          prior?.messages.length===1 && prior.messages[0].kind==='input' &&
          prior.messages[0].message_id===meta.message_id) {
        prior.end=end;prior.messages.push(meta);
      } else units.push({start:h.start,end,heading:h.title,messages:meta?[meta]:[]});
    }
  }
  if(!units.length) {
    const starts=[...hs];
    if(!starts.length || starts[0].start>0) starts.unshift({start:0,title:''});
    for(let i=0;i<starts.length;i++) units.push({start:starts[i].start,end:starts[i+1]?.start??lines.length,heading:starts[i].title,messages:[]});
  }
  const digest=createHash('sha256').update(content).digest('hex').slice(0,24), passages=[];
  for(const [unitIndex,unit] of units.entries()) {
    // Exchange pairs stay intact. Documentation uses blank-line boundaries with
    // a soft 600-token target; a single indivisible paragraph may exceed it.
    let start=unit.start, size=0, fence=null;
    const emit=end=>{
      if(!lines.slice(start,end).some(line=>line.trim())) {start=end;return;}
      const start_line=start+1,end_line=end;
      passages.push({passage_id:`${digest}:${start_line}-${end_line}`,start_line,end_line,
        heading:unit.heading,unit:unitIndex,messages:unit.messages,excerpt:lines.slice(start,end).join('\n')});
      start=end;size=0;
    };
    for(let i=unit.start;i<unit.end;i++) {
      size+=tokens(lines[i]).length;
      const mark=lines[i].match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
      if(mark) {if(!fence) fence=mark[1];else if(mark[1][0]===fence[0] && mark[1].length>=fence.length && !mark[2].trim()) fence=null;}
      if(!conversation && !fence && !lines[i].trim() && size>=600) emit(i+1);
    }
    emit(unit.end);
  }
  return passages;
}
function readPassage(path,content,id,neighbors=false) {
  const passages=splitPassages(path,content), index=passages.findIndex(p=>p.passage_id===id);
  if(index<0) return null;
  const chosen=passages[index];
  // Neighbor context includes complete adjacent logical units, including all
  // chunks of the selected documentation section.
  const selected=neighbors ? passages.filter(p=>Math.abs(p.unit-chosen.unit)<=1) : [chosen];
  const start_line=selected[0].start_line,end_line=selected.at(-1).end_line;
  return {passage_id:id,start_line,end_line,passages:selected.map(({excerpt,...p})=>p),
    content:content.split('\n').slice(start_line-1,end_line).join('\n')};
}
module.exports={splitPassages,readPassage};
