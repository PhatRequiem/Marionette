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
  const subscribers = new Set();
  const emit = (source, event, fields={}) => {
    const line = JSON.stringify({source,event,time:new Date().toISOString(),...fields}) + '\n';
    // No replay queue or payload logs. A slow/disconnected subscriber reconnects.
    for (const response of subscribers) if (!response.write(line)) response.destroy();
  };
  const server = http.createServer(async (req,res) => {
    const supplied = req.headers['x-request-id'];
    const request_id = typeof supplied === 'string' && /^[a-f0-9-]{36}$/.test(supplied) ? supplied : crypto.randomUUID();
    const started = performance.now();
    let tracked = false, action;
    const route = req.url === '/v1/query' ? 'query' : req.url === '/v1/status' ? 'status' : 'unknown';
    res.on('finish', () => {
      if (tracked) emit('Scarecrow', res.statusCode >= 400 ? 'request_failed' : 'request_completed',
        {request_id,route,...(action ? {action} : {}),http_status:res.statusCode,duration_ms:Math.round((performance.now()-started)*100)/100});
    });
    res.on('close', () => {
      if (tracked && !res.writableFinished) emit('Scarecrow','request_aborted',{request_id,route});
    });
    const send = (status, data) => { if (!res.destroyed) {res.writeHead(status, {'Content-Type':'application/json', 'Cache-Control':'no-store', 'X-Request-ID':request_id});res.end(JSON.stringify(data));} };
    try {
      if (req.headers.host !== `127.0.0.1:${settings.port}` || req.headers.origin || !authorized(req.headers.authorization, settings.token)) {
        tracked = true;
        send(403, {status:'error', error:'Access denied.'}); req.resume(); return;
      }
      if (req.method === 'GET' && req.url === '/v1/events') {
        const mirror = (await fs.stat(path.join(operations.app.vault.adapter.getBasePath(), 'Generated/.marionette-managed')).catch(() => null))?.isFile();
        res.writeHead(200, {'Content-Type':'application/x-ndjson','Cache-Control':'no-store', 'X-Vault-ID':settings.vault_id});
        res.write(JSON.stringify({source:'Scarecrow',event:'listener_observed',time:new Date().toISOString()})+'\n');
        res.write(JSON.stringify({source:'Obsidian',event:!mirror ? 'mirror_unavailable' : ready() ? 'ready' : 'indexing',time:new Date().toISOString()})+'\n');
        subscribers.add(res);
        const heartbeat = setInterval(() => {if (!res.write('\n')) res.destroy();}, 15000);
        res.on('close', () => {clearInterval(heartbeat);subscribers.delete(res);});
        return;
      }
      tracked = true;
      emit('Scarecrow','request_received',{request_id,route});
      const root = operations.app.vault.adapter.getBasePath();
      if (!(await fs.stat(path.join(root, 'Generated/.marionette-managed')).catch(() => null))?.isFile()) throw new RequestError('Vault mirror is absent or reset.', 503);
      if (!ready()) throw new RequestError('Obsidian is still indexing this vault.', 503);
      if (req.method === 'GET' && req.url === '/v1/status') {
        send(200, {status:'ok', vault_id:settings.vault_id, plugin:'Scarecrow', version:'0.3.0', read_only:true});return;
      }
      if (req.method !== 'POST' || req.url !== '/v1/query') { send(404,{status:'error',error:'Unknown route.'});req.resume();return; }
      if ((req.headers['content-type'] || '').split(';')[0] !== 'application/json') throw new RequestError('Use application/json.', 415);
      const chunks=[]; for await (const chunk of req) chunks.push(chunk);
      let form; try {form=JSON.parse(Buffer.concat(chunks).toString('utf8'));} catch {throw new RequestError('Invalid JSON.');}
      if (['list','search','read','inspect','tags','links','open'].includes(form?.action)) action=form.action;
      const data = await operations.run(form);
      // A reset during an asynchronous read must not return the old vault data.
      if (!(await fs.stat(path.join(root, 'Generated/.marionette-managed')).catch(() => null))?.isFile()) throw new RequestError('Vault was reset.', 503);
      send(200,{status:'ok',vault_id:settings.vault_id,source:'Obsidian mirror',data});
    } catch (error) { send(error instanceof RequestError ? error.status : 503, {status:'error', error:error instanceof RequestError ? error.message : 'Vault operation unavailable.'}); }
  });
  server.diagnostic = emit;
  server.endDiagnostics = () => {emit('Scarecrow','plugin_stopping');for (const response of subscribers) response.end();};
  server.on('listening', () => emit('Scarecrow','listener_started'));
  server.on('error', () => emit('Scarecrow','listener_failed'));
  server.requestTimeout=60000; server.headersTimeout=60000;
  server.setTimeout(60000, socket => socket.destroy());
  return server;
}
module.exports = {createServer};
