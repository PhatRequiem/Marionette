'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const {SearchIndex, tokens} = require('./search');
const {splitPassages, readPassage} = require('./passages');

class RequestError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
const fields = {
  list: ['path'], search: ['query', 'folder', 'tag', 'mode', 'limit', 'offset'], read: ['path', 'section', 'passage_id', 'context'],
  inspect: ['path'], links: ['path'], tags: [], open: ['path']
};
function validate(form) {
  if (!form || Array.isArray(form) || typeof form !== 'object' ||
      !Object.hasOwn(fields, form.action)) throw new RequestError('Unknown action.');
  for (const [key, value] of Object.entries(form)) {
    if (key !== 'action' && !fields[form.action].includes(key)) throw new RequestError('Unexpected field: ' + key);
    if (['limit','offset'].includes(key)) {
      if (!Number.isSafeInteger(value) || value < (key==='limit'?1:0) || value > (key==='limit'?10:1000000)) throw new RequestError('Invalid search pagination.');
      continue;
    }
    if (typeof value !== 'string') throw new RequestError('Fields must be strings.');
  }
  if (['read', 'inspect', 'links', 'open'].includes(form.action) && !form.path) throw new RequestError('An exact note path is required.');
  if (form.action === 'search' && ![form.query, form.folder, form.tag].some(Boolean)) throw new RequestError('Search needs query, folder or tag.');
  for (const key of ['path', 'folder']) if (form[key] !== undefined) checkPath(form[key]);
  if (form.query && form.query.length>256) throw new RequestError('Search query must be at most 256 characters.');
  if (form.mode !== undefined && !['exact','prefix','fuzzy'].includes(form.mode)) throw new RequestError('Search mode must be exact, prefix or fuzzy.');
  if (form.passage_id !== undefined && (!/^[a-f0-9]{24}:\d+-\d+$/.test(form.passage_id) || form.section !== undefined)) throw new RequestError('Use a returned passage_id without section.');
  if (form.context !== undefined && (!form.passage_id || !['none','neighbors'].includes(form.context))) throw new RequestError('Context requires passage_id and must be none or neighbors.');
  if (form.section === '') throw new RequestError('Section must name a heading.');
  return form;
}
function checkPath(value) {
  if (value === '') return;
  if (value.includes('\\') || value.includes('\0') || value.includes(':') ||
      value.split('/').some(part => !part || part.startsWith('.'))) throw new RequestError('Use a visible vault-relative path.');
}
class Operations {
  constructor(app) { this.app = app; }
  async safe(file) {
    if (!file) return false;
    try {
      if (file === this.app.vault.getRoot()) return true;
      checkPath(file.path);
      const root = await fs.realpath(this.app.vault.adapter.getBasePath());
      // Exclude symlinks, including links into another contact/config directory.
      let current = root;
      for (const part of file.path.split('/').filter(Boolean)) {
        current = path.join(current, part);
        if ((await fs.lstat(current)).isSymbolicLink()) return false;
      }
      return true;
    } catch { return false; }
  }
  async note(name) {
    const file = this.app.vault.getAbstractFileByPath(name);
    if (!(await this.safe(file)) || file.extension !== 'md') throw new RequestError('Markdown note not found.', 404);
    return file;
  }
  metadata(file) {
    const cache = this.app.metadataCache.getFileCache(file);
    if (!cache) throw new RequestError('Note metadata is not ready; retry shortly.', 503);
    return cache;
  }
  tags(cache) {
    const front = cache.frontmatter?.tags;
    const list = Array.isArray(front) ? front : typeof front === 'string' ? front.split(/[ ,]+/) : [];
    return [...new Set([...(cache.tags || []).map(t => t.tag), ...list.filter(t => typeof t === 'string')]
      .filter(Boolean).map(t => t.startsWith('#') ? t : '#' + t))].sort();
  }
  async files() {
    const result = [];
    for (const file of this.app.vault.getMarkdownFiles()) if (await this.safe(file)) result.push(file);
    return result.sort((a,b) => a.path.localeCompare(b.path));
  }
  async run(input) {
    const form = validate(input), {vault, metadataCache, workspace} = this.app;
    if (form.action === 'list') {
      const folder = vault.getAbstractFileByPath(form.path || '/');
      if (!folder || !Array.isArray(folder.children) || !(await this.safe(folder))) throw new RequestError('Folder not found.', 404);
      const entries = [];
      for (const file of folder.children) if (await this.safe(file)) entries.push({path:file.path, type:Array.isArray(file.children) ? 'folder' : 'file'});
      return {path:form.path || '', entries:entries.sort((a,b) => a.path.localeCompare(b.path))};
    }
    if (form.action === 'tags' || form.action === 'search') {
      const index = new SearchIndex(form.query ? {body:1,path:0.1,title:0.2,headings:0.5} : undefined), counts = new Map(), terms = [...new Set(tokens(form.query || ''))];
      if (form.query !== undefined && !terms.length) throw new RequestError('Query needs at least one word or number.');
      for (const file of await this.files()) {
        if (form.folder && file.path !== form.folder && !file.path.startsWith(form.folder + '/')) continue;
        const metadata = this.metadata(file), tags = this.tags(metadata);
        if (form.action === 'tags') { for (const tag of tags) counts.set(tag, (counts.get(tag) || 0) + 1); continue; }
        if (form.tag && !tags.includes(form.tag.startsWith('#') ? form.tag : '#' + form.tag)) continue;
        const content = await vault.cachedRead(file);
        const base={path:file.path,tags,modified_ms:file.stat.mtime};
        if(terms.length) {
          for(const passage of splitPassages(file.path,content)) {
            index.add({...base,...passage},passage.excerpt,passage.heading ? [passage.heading] : []);
          }
        } else index.add(base,content,[]);
      }
      if (form.action === 'tags') return {tags:[...counts].sort().map(([tag,notes]) => ({tag,notes}))};
      const ranked = index.search(form.query || '', form.mode || 'exact');
      const grouped=new Map();
      for(const hit of ranked) {
        if(!grouped.has(hit.path)) grouped.set(hit.path,{...hit,passages:[]});
        if(hit.passage_id) {
          const {path,tags,modified_ms,...passage}=hit;
          grouped.get(hit.path).passages.push(passage);
        }
      }
      const offset=form.offset || 0, limit=form.limit || 5, all=[...grouped.values()];
      const clip=(text,n)=>String(text||'').slice(0,n);
      const compact=hit=>{
        const text=hit.matching_lines.filter(line=>line.line>0 && !line.text.startsWith('>')).map(line=>line.text).join(' ');
        const preview=text || hit.excerpt || '';
        return {passage_id:hit.passage_id,start_line:hit.start_line,end_line:hit.end_line,
          heading:clip(hit.heading,100),preview:clip(preview,240),preview_truncated:preview.length>240,
          matched_terms:hit.matched_terms,missing_terms:hit.missing_terms,
          term_matches:hit.term_matches.slice(0,12),term_matches_truncated:hit.term_matches.length>12,
          messages:hit.messages};
      };
      const result={matches:[],total:all.length,total_passages:terms.length?ranked.length:0,
        offset,next_offset:null,truncated:false,
        next_action:'Previews locate evidence, not full context. Read a selected path + passage_id before answering. Use neighbors only if context is missing. modified_ms is mirror file time, not event time.'};
      for(const hit of all.slice(offset,offset+limit)) {
        const note={path:hit.path,modified_ms:hit.modified_ms,score:hit.score,
          matched_terms:hit.matched_terms,missing_terms:hit.missing_terms,
          matched_phrases:hit.matched_phrases,nearby_pairs:hit.nearby_pairs,
          matching_lines:hit.matching_lines.slice(0,2).map(line=>({line:line.line,text:clip(line.text,160)})),
          passages_total:hit.passages.length,passages:hit.passages.slice(0,2).map(compact)};
        result.matches.push(note);
        // Reserve room for pagination fields; never silently cut source references.
        if(Buffer.byteLength(JSON.stringify(result),'utf8')>12000) {result.matches.pop();break;}
      }
      if(!result.matches.length && offset<all.length) throw new RequestError('Search result exceeds preview budget; narrow query or folder.');
      result.truncated=offset+result.matches.length<all.length;
      result.next_offset=result.truncated?offset+result.matches.length:null;
      return result;
    }

    const file = await this.note(form.path), base = {path:file.path, modified_ms:file.stat.mtime};
    if (form.action === 'open') { await workspace.getLeaf(false).openFile(file); return {...base, opened:true}; }
    if (form.action === 'read') {
      const content = await vault.cachedRead(file);
      if(form.passage_id !== undefined) {
        const result=readPassage(file.path,content,form.passage_id,form.context==='neighbors');
        if(!result) throw new RequestError('Passage is stale or missing; search again.',409);
        return {...base,...result};
      }
      if (form.section === undefined) return {...base, content};
      const headings = this.metadata(file).headings || [], found = headings.filter(h => h.heading === form.section);
      if (found.length !== 1) throw new RequestError(found.length ? 'Heading is ambiguous; read the full note.' : 'Heading not found.', 404);
      const h = found[0], next = headings.slice(headings.indexOf(h)+1).find(n => n.level <= h.level);
      return {...base, section:form.section, start_line:h.position.start.line+1,
        content:content.split('\n').slice(h.position.start.line, next?.position.start.line).join('\n')};
    }
    const cache = this.metadata(file);
    if (form.action === 'inspect') {
      const properties = {...cache.frontmatter}; delete properties.position;
      return {...base, tags:this.tags(cache), properties,
        headings:(cache.headings || []).map(h => ({heading:h.heading, level:h.level, line:h.position.start.line+1}))};
    }
    const outgoing = [];
    for (const link of [...(cache.links || []), ...(cache.embeds || [])]) {
      const linkpath = link.link.split('#')[0];
      const target = linkpath ? metadataCache.getFirstLinkpathDest(linkpath, file.path) : file;
      if (target && !(await this.safe(target))) continue;
      outgoing.push({link:link.link, path:target?.path || null, resolved:!!target});
    }
    const backlinks = [];
    for (const [source, targets] of Object.entries(metadataCache.resolvedLinks)) {
      if (targets[file.path] && await this.safe(vault.getAbstractFileByPath(source))) backlinks.push({path:source, count:targets[file.path]});
    }
    return {...base, outgoing, backlinks, basis:'Obsidian metadata cache; links may briefly lag edits.'};
  }
}
module.exports = {Operations, RequestError, validate};
