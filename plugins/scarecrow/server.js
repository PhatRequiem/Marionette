'use strict';
const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const {RequestError} = require('./operations');
function authorized(value, token) {
  const expected = Buffer.from('Bearer ' + token), received = Buffer.from(value || '');
  return expected.length === received.length && crypto.timingSafeEqual(expected, received);
}
function createServer(settings, operations, ready) {
  if (!Number.isInteger(settings.port) || settings.port < 1024 || settings.port > 65535 ||
      !/^[a-f0-9]{64}$/.test(settings.token || '') || !settings.vault_id) throw new Error('Run Scarecrow setup to configure this vault.');
  const server = http.createServer(async (req,res) => {
    const send = (status, data) => { if (!res.destroyed) {res.writeHead(status, {'Content-Type':'application/json', 'Cache-Control':'no-store'});res.end(JSON.stringify(data));} };
    try {
      if (req.headers.host !== `127.0.0.1:${settings.port}` || req.headers.origin || !authorized(req.headers.authorization, settings.token)) {
        send(403, {status:'error', error:'Access denied.'}); req.resume(); return;
      }
      const root = operations.app.vault.adapter.getBasePath();
      if (!(await fs.stat(path.join(root, 'Generated/.marionette-managed')).catch(() => null))?.isFile()) throw new RequestError('Vault mirror is absent or reset.', 503);
      if (!ready()) throw new RequestError('Obsidian is still indexing this vault.', 503);
      if (req.method === 'GET' && req.url === '/v1/status') {
        send(200, {status:'ok', vault_id:settings.vault_id, plugin:'Scarecrow', version:'0.1.0', read_only:true});return;
      }
      if (req.method !== 'POST' || req.url !== '/v1/query') { send(404,{status:'error',error:'Unknown route.'});req.resume();return; }
      if ((req.headers['content-type'] || '').split(';')[0] !== 'application/json') throw new RequestError('Use application/json.', 415);
      const chunks=[]; for await (const chunk of req) chunks.push(chunk);
      let form; try {form=JSON.parse(Buffer.concat(chunks).toString('utf8'));} catch {throw new RequestError('Invalid JSON.');}
      const data = await operations.run(form);
      // A reset during an asynchronous read must not return the old vault data.
      if (!(await fs.stat(path.join(root, 'Generated/.marionette-managed')).catch(() => null))?.isFile()) throw new RequestError('Vault was reset.', 503);
      send(200,{status:'ok',vault_id:settings.vault_id,source:'Obsidian mirror',data});
    } catch (error) { send(error instanceof RequestError ? error.status : 503, {status:'error', error:error instanceof RequestError ? error.message : 'Vault operation unavailable.'}); }
  });
  server.requestTimeout=60000; server.headersTimeout=60000;
  server.setTimeout(60000, socket => socket.destroy());
  return server;
}
module.exports = {createServer};
