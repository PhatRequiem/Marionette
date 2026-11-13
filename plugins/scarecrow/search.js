'use strict';

// Independent Scarecrow implementation of standard lexical retrieval techniques.
// BM25 references and deliberate scoring choices are documented in the guide.
const FIELD_WEIGHTS = {body:1, path:0.5, title:2, headings:1.5};
const K1 = 1.2, B = 0.75;
function tokens(text) {
  return text.normalize('NFKC').toLowerCase().match(/[\p{L}\p{N}_]+/gu) || [];
}
function frequencies(words) {
  const result = new Map();
  for (const word of words) result.set(word, (result.get(word) || 0) + 1);
  return result;
}
// At most one insertion, deletion, substitution, or adjacent transposition.
// Code points avoid treating a Unicode surrogate pair as two characters.
function oneEdit(a, b) {
  const left = [...a], right = [...b];
  if (Math.abs(left.length-right.length) > 1) return false;
  let i=0;
  while (i<left.length && i<right.length && left[i] === right[i]) i++;
  if (i === left.length || i === right.length) return true;
  if (left.length === right.length) {
    if (left.slice(i+1).join('') === right.slice(i+1).join('')) return true;
    return left[i] === right[i+1] && left[i+1] === right[i] &&
      left.slice(i+2).join('') === right.slice(i+2).join('');
  }
  return left.length > right.length ? left.slice(i+1).join('') === right.slice(i).join('') :
    left.slice(i).join('') === right.slice(i+1).join('');
}
function evidence(doc, terms, sourceTerms) {
  const wanted = new Set(terms), nearby = new Set(), phrases = new Set();
  const queryPairs = new Set(terms.slice(1).map((term,i) => terms[i]+'\0'+term));
  const matching_lines = [];
  for (const {line,text,words} of doc.lines) {
    if (!line && doc.note.passage_id) continue; // Shared paths are not passage proximity evidence.
    if (line && words.some(word => sourceTerms.has(word))) matching_lines.push({line,text});
    for (let i=0; i<words.length; i++) {
      if (!wanted.has(words[i])) continue;
      for (let j=i+1; j<Math.min(words.length,i+13); j++) {
        if (words[j] === words[i] || !wanted.has(words[j])) continue;
        nearby.add([words[i],words[j]].sort().join('\0'));
        if (j === i+1 && queryPairs.has(words[i]+'\0'+words[j])) phrases.add(words[i]+'\0'+words[j]);
      }
    }
  }
  return {nearby, phrases, matching_lines};
}
class SearchIndex {
  constructor(weights=FIELD_WEIGHTS) {
    this.weights=weights;
    this.documents = new Map();
    this.postings = new Map(); // token -> set of document/passage keys
    this.lengths = Object.fromEntries(Object.keys(this.weights).map(field => [field,0]));
  }
  remove(name) {
    const doc = this.documents.get(name);
    if (!doc) return;
    for (const term of doc.terms) {
      const posting = this.postings.get(term);
      posting.delete(name);
      if (!posting.size) this.postings.delete(term);
    }
    for (const field of Object.keys(this.weights)) this.lengths[field] -= doc.fields[field].length;
    this.documents.delete(name);
  }
  add(note, content, headings=[]) {
    const id=note.passage_id ? note.path+"#"+note.passage_id : note.path;
    this.remove(id);
    const title = note.path.split('/').at(-1).replace(/\.md$/i,'');
    const texts = {body:content, path:note.path, title, headings:headings.join('\n')};
    const fields = {}, terms = new Set();
    for (const [field,text] of Object.entries(texts)) {
      const words = tokens(text);
      fields[field] = {length:words.length, counts:frequencies(words)};
      this.lengths[field] += words.length;
      for (const term of words) terms.add(term);
    }
    const lines = [note.path,...content.split('\n')].map((text,line) => ({line:line ? line+(note.start_line || 1)-1 : 0,text,words:tokens(text)}));
    this.documents.set(id,{note, fields, terms, lines});
    for (const term of terms) {
      if (!this.postings.has(term)) this.postings.set(term,new Set());
      this.postings.get(term).add(id);
    }
  }
  idf(term) {
    const count = this.postings.get(term)?.size || 0;
    return Math.log1p((this.documents.size-count+0.5)/(count+0.5));
  }
  termScore(doc, term) {
    let score = 0;
    for (const [field,weight] of Object.entries(this.weights)) {
      const {length,counts} = doc.fields[field], frequency = counts.get(term) || 0;
      if (!frequency) continue;
      const average = this.lengths[field]/this.documents.size;
      score += weight * this.idf(term) * frequency*(K1+1) /
        (frequency + K1*(1-B+B*length/average));
    }
    return score;
  }
  expand(term, mode) {
    const result = [];
    if (this.postings.has(term)) result.push({term,kind:'exact',weight:1});
    if (mode === 'exact') return result;
    for (const candidate of this.postings.keys()) {
      if (candidate === term) continue;
      if (mode === 'prefix' && [...term].length >= 3 && candidate.startsWith(term)) {
        result.push({term:candidate,kind:'prefix',weight:0.7});
      } else if (mode === 'fuzzy' && [...term].length >= 4 && oneEdit(term,candidate)) {
        result.push({term:candidate,kind:'fuzzy',weight:0.5});
      }
    }
    return result;
  }
  search(query='', mode='exact') {
    if (!['exact','prefix','fuzzy'].includes(mode)) throw new Error('Unknown search mode.');
    const terms = [...new Set(tokens(query))];
    const expansions = new Map(terms.map(term => [term,this.expand(term,mode)]));
    const candidates = new Set();
    for (const variants of expansions.values()) for (const variant of variants) {
      for (const name of this.postings.get(variant.term)) candidates.add(name);
    }
    if (!terms.length) for (const name of this.documents.keys()) candidates.add(name);
    const matches = [];
    for (const name of candidates) {
      const doc = this.documents.get(name), matched_terms = [], term_matches = [], sourceTerms = new Set();
      let score = 0;
      for (const [queryTerm,variants] of expansions) {
        let best = 0;
        for (const variant of variants) {
          if (!doc.terms.has(variant.term)) continue;
          sourceTerms.add(variant.term);
          term_matches.push({query:queryTerm,term:variant.term,kind:variant.kind});
          best = Math.max(best, variant.weight*this.termScore(doc,variant.term));
        }
        if (best) {score += best;matched_terms.push(queryTerm);}
      }
      const {nearby,phrases,matching_lines} = evidence(doc,terms,sourceTerms);
      const pairScore = pairs => [...pairs].reduce((sum,pair) => {
        const [a,b] = pair.split('\0');return sum+Math.min(this.idf(a),this.idf(b));
      },0);
      score += 0.5*pairScore(nearby)+pairScore(phrases);
      matches.push({...doc.note,score,matched_terms,missing_terms:terms.filter(term => !matched_terms.includes(term)),
        term_matches,nearby_pairs:[...nearby].map(pair => pair.split('\0')),
        matched_phrases:[...phrases].map(pair => pair.replace('\0',' ')),matching_lines});
    }
    return matches.sort((a,b) => b.score-a.score || a.path.localeCompare(b.path) || (a.start_line || 0)-(b.start_line || 0));
  }
}
module.exports = {SearchIndex, tokens};
