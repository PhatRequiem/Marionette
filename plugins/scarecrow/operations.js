'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');

class RequestError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
const fields = {
  list: ['path'], search: ['query', 'folder', 'tag'], read: ['path', 'section'],
  inspect: ['path'], links: ['path'], tags: [], open: ['path']
};
function validate(form) {
  if (!form || Array.isArray(form) || typeof form !== 'object' ||
      !Object.hasOwn(fields, form.action)) throw new RequestError('Unknown action.');
  for (const [key, value] of Object.entries(form)) {
    if (key !== 'action' && !fields[form.action].includes(key)) throw new RequestError('Unexpected field: ' + key);
    if (typeof value !== 'string') throw new RequestError('Fields must be strings.');
  }
  if (['read', 'inspect', 'links', 'open'].includes(form.action) && !form.path) throw new RequestError('An exact note path is required.');
  if (form.action === 'search' && ![form.query, form.folder, form.tag].some(Boolean)) throw new RequestError('Search needs query, folder or tag.');
  for (const key of ['path', 'folder']) if (form[key] !== undefined) checkPath(form[key]);
  if (form.section === '') throw new RequestError('Section must name a heading.');
  return form;
}
function checkPath(value) {
  if (value === '') return;
  if (value.includes('\\') || value.includes('\0') || value.includes(':') ||
      value.split('/').some(part => !part || part.startsWith('.'))) throw new RequestError('Use a visible vault-relative path.');
}
// Search is lexical evidence, not a semantic or confidence score. Normalize the
// query and source identically; retain Unicode letters/numbers and token boundaries.
function tokens(text) {
  return text.normalize('NFKC').toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [];
}
function searchEvidence(name, content, terms) {
  const wanted = new Set(terms), found = new Set(), nearby = new Set(), phrases = new Set();
  const queryPairs = new Set(terms.slice(1).map((term,i) => terms[i] + '\0' + term));
  const lines = content.split('\n'), matching_lines = [];
  // Never award proximity across separate lines or between the path and content.
  for (const [index, text] of [name, ...lines].entries()) {
    const words = tokens(text);
    let matched = false;
    for (let i=0; i<words.length; i++) {
      if (!wanted.has(words[i])) continue;
      found.add(words[i]); matched = true;
      for (let j=i+1; j<Math.min(words.length,i+13); j++) {
        if (words[j] === words[i] || !wanted.has(words[j])) continue;
        nearby.add([words[i],words[j]].sort().join('\0'));
        if (j === i+1 && queryPairs.has(words[i] + '\0' + words[j])) phrases.add(words[i] + '\0' + words[j]);
      }
    }
    if (index && matched) matching_lines.push({line:index,text});
  }
  return {found, nearby, phrases, matching_lines};
}
function rankMatches(notes, terms) {
  const weights = new Map(terms.map(term => [term,
    1 + Math.log((1 + notes.length) / (1 + notes.filter(note => note.evidence.found.has(term)).length))]));
  return notes.filter(note => !terms.length || note.evidence.found.size).map(({evidence,...note}) => {
    const matched_terms = terms.filter(term => evidence.found.has(term));
    const termScore = matched_terms.reduce((sum,term) => sum + weights.get(term),0);
    const pairScore = pairs => [...pairs].reduce((sum,pair) => {
      const [a,b] = pair.split('\0'); return sum + Math.min(weights.get(a),weights.get(b));
    },0);
    // Each term/pair contributes once per note: repetition cannot inflate rank.
    return {...note, score:termScore + 0.5*pairScore(evidence.nearby) + pairScore(evidence.phrases),
      matched_terms, missing_terms:terms.filter(term => !evidence.found.has(term)),
      nearby_pairs:[...evidence.nearby].map(pair => pair.split('\0')),
      matched_phrases:[...evidence.phrases].map(pair => pair.replace('\0',' ')),
      matching_lines:evidence.matching_lines};
  }).sort((a,b) => b.score-a.score || a.path.localeCompare(b.path));
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
      const matches = [], counts = new Map(), terms = [...new Set(tokens(form.query || ''))];
      if (form.query !== undefined && !terms.length) throw new RequestError('Query needs at least one word or number.');
      for (const file of await this.files()) {
        if (form.folder && file.path !== form.folder && !file.path.startsWith(form.folder + '/')) continue;
        const tags = this.tags(this.metadata(file));
        if (form.action === 'tags') { for (const tag of tags) counts.set(tag, (counts.get(tag) || 0) + 1); continue; }
        if (form.tag && !tags.includes(form.tag.startsWith('#') ? form.tag : '#' + form.tag)) continue;
        const content = await vault.cachedRead(file);
        matches.push({path:file.path, tags, modified_ms:file.stat.mtime,
          evidence:searchEvidence(file.path, content, terms)});
      }
      if (form.action === 'tags') return {tags:[...counts].sort().map(([tag,notes]) => ({tag,notes}))};
      const ranked = rankMatches(matches, terms);
      return {matches:ranked, total:ranked.length,
        matching:'Any whole query token may match. Ranked by term rarity within filtered notes, nearby distinct terms (within 12 tokens on one line), and adjacent query phrases. Scores are relative lexical evidence, not confidence. Folder and exact-tag filters apply.'};
    }

    const file = await this.note(form.path), base = {path:file.path, modified_ms:file.stat.mtime};
    if (form.action === 'open') { await workspace.getLeaf(false).openFile(file); return {...base, opened:true}; }
    if (form.action === 'read') {
      const content = await vault.cachedRead(file);
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
