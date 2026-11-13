'use strict';
const fs = require('node:fs');
const path = require('node:path');
const {Operations} = require('../../plugins/scarecrow/operations');
const {createServer} = require('../../plugins/scarecrow/server');
function fixture(root) {
  fs.mkdirSync(path.join(root,'Generated'),{recursive:true});
  fs.writeFileSync(path.join(root,'Generated/.marionette-managed'),'');
  fs.mkdirSync(path.join(root,'People'),{recursive:true});
  fs.mkdirSync(path.join(root,'.obsidian'),{recursive:true});
  const content = {
    'Welcome.md':'# Welcome\n\nSee [[People/Alice]] and [[Missing]].\n# Details\nTest code: STRAW-42\n',
    'People/Alice.md':'# Alice\nShe plays banjo. #music\n[[Welcome]]\n',
    '.obsidian/secret.md':'SECRET NOT FOR TOOLS'
  };
  const files = new Map(); const rootFile={path:'',children:[]};files.set('',rootFile);files.set('/',rootFile);
  for (const [name,text] of Object.entries(content)) {
    fs.writeFileSync(path.join(root,name),text);
    files.set(name,{path:name,extension:'md',stat:{mtime:123}});
  }
  const people={path:'People',children:[files.get('People/Alice.md')]};files.set('People',people);
  rootFile.children=[files.get('Welcome.md'),people,files.get('.obsidian/secret.md')];
  const cache = {
    'Welcome.md':{headings:[{heading:'Welcome',level:1,position:{start:{line:0}}},{heading:'Details',level:1,position:{start:{line:3}}}], links:[{link:'People/Alice'},{link:'Missing'}]},
    'People/Alice.md':{headings:[{heading:'Alice',level:1,position:{start:{line:0}}}],tags:[{tag:'#music'}],frontmatter:{tags:['music'],alias:'Friend'},links:[{link:'Welcome'}]}
  };
  let opened=null;
  const app={
    vault:{adapter:{getBasePath:()=>root}, getRoot:()=>rootFile, getAbstractFileByPath:p=>files.get(p),
      getMarkdownFiles:()=>[...new Set(files.values())].filter(f=>f.extension==='md'),
      cachedRead:async f=>fs.promises.readFile(path.join(root,f.path),'utf8')},
    metadataCache:{getFileCache:f=>cache[f.path],getFirstLinkpathDest:p=>files.get(p+'.md'),
      resolvedLinks:{'Welcome.md':{'People/Alice.md':1},'People/Alice.md':{'Welcome.md':1}},on:()=>({})},
    workspace:{getLeaf:()=>({openFile:async f=>{opened=f.path;}}),onLayoutReady:fn=>fn()}
  };
  return {app,files,cache,opened:()=>opened};
}
async function start(root) {
  const data=fixture(root), settings={port:27124,token:'a'.repeat(64),vault_id:'fixture'};
  const server=createServer(settings,new Operations(data.app),()=>true);
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  settings.port=server.address().port;
  return {...data,server,settings};
}
module.exports={fixture,start};
if(require.main===module) start(process.argv[2]).then(({server,settings})=>{
  process.stdout.write(JSON.stringify(settings)+'\n');
  process.on('SIGTERM',()=>{server.close();server.closeAllConnections();});
});
