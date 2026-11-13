"""Bounded request-form handler shared by the operator CLI and Qwen-Agent adapter."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import time

from diagnostics import message_id as validate_id
from storage import open_read

MAX_EVENTS = 256
MAX_BYTES = 1024 * 1024
MAX_RESULT = 64 * 1024


# Definitions travel with the facts; the model need not infer units or boundaries.
FIELD_MEANINGS = {
    'processing': {
        'prompt_tokens': 'Input tokens for one model request, including history, instructions and tool results; not just the user message. Cached input is included.',
        'completion_tokens': 'Generated tokens for one request, including reasoning and any tool-call text; not just the visible answer.',
        'total_tokens': 'Prompt plus completion tokens for that request; not generated tokens.',
        'recorded_token_totals': 'Sums over available usage records only. Repeated history is counted again across requests; not unique context size or proof all requests were retained.',
        'processing_boundary_elapsed_ms': 'Elapsed between recorded application processing boundaries; includes tool work and overhead, not pure model generation time.',
        'tools': 'Explicit tool outcomes; completed message processing does not imply every tool succeeded. Unknown means no retained outcome.',
        'connections': 'Client and server HTTP observations joined by request UUID; durations overlap and must not be added. Component identifies the emitter, source identifies evidence storage.',
        'budgets': 'Configured allowances and prompt sizes, not actual generated usage.',
    },
    'delivery': {
        'timings_ms': 'All durations are milliseconds. Intervals overlap; do not add them.',
        'adapter_queue_ms': 'Time from Discord adapter receipt until its turn lock is acquired.',
        'main_queue_ms': 'Time waiting for the main application to handle the turn.',
        'processing_ms': 'Main application turn processing, including model requests and tools.',
        'local_response_ms': 'Local request round trip, including main queue and processing.',
        'receipt_to_delivery_ms': 'Discord adapter receipt through completed answer sending, including queueing and processing; not send-only time.',
        'receipt_to_failure_ms': 'Discord adapter receipt until the recorded failure; not successful delivery time.',
        'chunks_sent': 'Count of retained answer-chunk send records, not necessarily the full original count.',
    },
    'setup': {
        'fields': 'Dated startup observations, not current status. Runtime version belongs to llama.cpp, not Vulkan. GPU layers describes offload count, not GPU utilization.',
        'Reasoning format': 'Wire format for separating reasoning from the answer; not the model family.',
    },
    'status': {'obsidian': 'Fresh authenticated Scarecrow status probe, separately timestamped. Tool registration alone does not establish connectivity.', 'tools': 'Tools bound at the instant of this probe; the application may rebind tools for each contact turn.'},
    'errors': {'failures': 'Recognized failures in retained evidence only. An empty list does not establish an error-free run.'},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def validate(form):
    if not isinstance(form, dict) or not {'lookup', 'target'} <= form.keys() or set(form) - {'lookup','target','message_id'}:
        raise ValueError('Use lookup and target; message_id is allowed only for a specific message.')
    lookup, target = form['lookup'], form['target']
    if not isinstance(lookup, str) or not isinstance(target, str):
        raise ValueError('lookup and target must be strings.')
    valid = (lookup == 'setup' and target == 'startup') or (lookup == 'status' and target == 'current') or (lookup in ('processing','delivery','errors') and target in ('previous_message','message_id'))
    if not valid:
        raise ValueError('Unsupported lookup/target combination.')
    if target == 'message_id':
        if not isinstance(form.get('message_id'), str):
            raise ValueError('message_id must be an existing message ID string.')
        validate_id(form['message_id'])
    elif 'message_id' in form:
        raise ValueError('message_id is only allowed with target message_id.')


def message_records(db, session, identifier):
    """Only message-tagged evidence, including retained windows; bounded before decoding."""
    sql = "SELECT id,recorded_at,stream,length(raw) AS bytes,0 AS truncated,raw,'events' AS origin FROM events WHERE session_id=? AND message_id=?"
    args = [session,identifier]
    if db.execute('PRAGMA user_version').fetchone()[0] >= 2:
        sql += " UNION ALL SELECT event_id,recorded_at,stream,length(raw),truncated,raw,'error_evidence' FROM error_evidence WHERE session_id=? AND message_id=?"
        args += [session,identifier]
    # Streaming presentation chunks do not supply processing/delivery/error facts.
    # Exclude them before evidence limits, including protected copies.
    if db.execute('PRAGMA user_version').fetchone()[0] >= 5:
        sql = sql.replace('WHERE session_id=? AND message_id=?',
                          "WHERE session_id=? AND message_id=? AND (event_type IS NULL OR event_type <> 'reasoning_delta')")
    rows = []
    size = 0
    # LIMIT caps matching rows, and SQL length checks avoid materializing oversized BLOBs.
    sql = "SELECT id,recorded_at,stream,bytes,truncated,CASE WHEN bytes<=? THEN raw ELSE NULL END AS raw,origin FROM (" + sql + ') ORDER BY id LIMIT ?'
    for row in db.execute(sql,[MAX_BYTES,*args,MAX_EVENTS+1]):
        size += row['bytes']
        if size > MAX_BYTES or len(rows) == MAX_EVENTS:
            raise ValueError('Message evidence exceeds query limits.')
        item = dict(row)
        item['raw'] = row['raw'].decode('utf-8',errors='replace')
        rows.append(item)
    return rows


def connection_fields(raw):
    match = re.fullmatch(r'Client: (?:\[(?:message|request|tool) [^\]\r\n]+\] )*Connection event: (.*)\n?', raw, re.S)
    if not match:
        return None
    try:
        fields = json.loads(match[1])
    except ValueError:
        return None
    if not isinstance(fields, dict):
        return None
    request_id = fields.get('request_id')
    if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9-]{36}', request_id):
        return None
    return fields


def records(db, session, identifier):
    rows = message_records(db, session, identifier)
    ids = {f['request_id'] for row in rows if not row['truncated']
           and (f := connection_fields(row['raw'])) and f.get('source') == 'Obsidian'}
    if not ids or db.execute('PRAGMA user_version').fetchone()[0] < 5:
        return rows
    # The message-owned client record is the authority for correlation. Never
    # attach global events by time, or another message's tagged records.
    for table, key, truncated in [('events', 'id', '0'), ('error_evidence', 'event_id', 'truncated')]:
        clauses = ' OR '.join('instr(CAST(raw AS TEXT),?)>0' for _ in ids)
        sql = f"""SELECT {key} AS id,recorded_at,stream,length(raw) AS bytes,
            {truncated} AS truncated,CASE WHEN length(raw)<=? THEN raw ELSE NULL END AS raw
            FROM {table} WHERE session_id=? AND message_id IS NULL
            AND event_type='connection_event' AND ({clauses}) ORDER BY {key} LIMIT ?"""
        for row in db.execute(sql, [MAX_BYTES, session, *sorted(ids), MAX_EVENTS+1]):
            if row['raw'] is None:
                raise ValueError('Connection evidence exceeds query limits.')
            item = dict(row)
            item['raw'] = row['raw'].decode('utf-8', errors='replace')
            item['origin'] = table
            fields = connection_fields(item['raw'])
            if fields and fields.get('source') == 'Scarecrow' and fields['request_id'] in ids:
                rows.append(item)
            if len(rows) > 2*MAX_EVENTS:
                raise ValueError('Connection evidence exceeds query limits.')
    return merge(rows)


def merge(rows):
    result = {}
    for row in rows:
        old = result.get(row['id'])
        if old:
            if old['truncated'] and not row['truncated']:
                result[row['id']] = row
            elif not old['truncated'] and not row['truncated'] and any(old[k] != row[k] for k in ('raw','recorded_at','stream')):
                raise ValueError('Conflicting copies of an event.')
        else:
            result[row['id']] = row
    if len(result) > MAX_EVENTS or sum(len(r['raw'].encode()) for r in result.values()) > MAX_BYTES:
        raise ValueError('Merged evidence exceeds query limits.')
    return [result[k] for k in sorted(result)]


def extract(lookup, rows, identifier, conversation):
    output = {'processing': {'outcome': 'unknown', 'finish_reason': None, 'requests': [], 'tools': [], 'connections': [], 'budgets': [], 'started_at': None,'ended_at':None},
              'delivery': {'outcome':'unknown','chunks_sent':0,'timings_ms':{}},
              'errors': {'failures':[]}}[lookup]
    evidence, notes = [], []
    starts = ends = 0
    tools = {}
    connection_ids = {f['request_id'] for row in rows if row['raw'].startswith('Client: [message '+identifier+'] ')
                      and not row['truncated'] and (f := connection_fields(row['raw'])) and f.get('source') == 'Obsidian'}
    for row in rows:
        if row['truncated']:
            notes.append('Truncated protected evidence excluded.')
            continue
        raw = row['raw'].rstrip('\n')
        ref = {'event_id':row['id'],'recorded_at':row['recorded_at'],'source':row['origin']}
        used = False
        tag = re.fullmatch(r'Client: \[message '+re.escape(identifier)+r'\] (?:\[request (\d+)\] )?(?:\[tool (\d+)\] )?(.*)',raw,re.S) if row['stream']=='diagnostic' else None
        if tag:
            req,tool,text=tag.groups()
            if lookup == 'processing':
                boundary=re.fullmatch(r'========== MESSAGE (START|END) \| processing(?: \| (completed|failed|interrupted))? ==========',text)
                if boundary:
                    used=True
                    if boundary[1]=='START':
                        starts+=1;output['started_at']=row['recorded_at']
                    else:
                        ends+=1;output['ended_at']=row['recorded_at'];output['outcome']=boundary[2] or 'unknown'
                elif text.startswith('Runtime usage: '):
                    usage=json.loads(text[len('Runtime usage: '):])
                    if not isinstance(usage,dict):raise ValueError('Malformed token usage.')
                    counts={k:usage.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')}
                    if any(v is not None and (type(v) is not int or v<0) for v in counts.values()):raise ValueError('Malformed token usage.')
                    output['requests'].append({'request_number':req,**counts,**ref});used=True
                elif text.startswith(('Tool call identity: ', 'Tool summary: ', 'Tool result summary: ')):
                    identity=json.loads(text.split(': ',1)[1])
                    if not isinstance(identity,dict) or not isinstance(identity.get('name'),str):raise ValueError('Malformed tool identity.')
                    item=tools.setdefault((req,tool), {'request_number':req,'tool_number':tool,'name':identity['name'],
                        'protocol_tool_call_id':None,'action':None,'outcome':'unknown','evidence':[],**ref})
                    if item['name'] != identity['name']:raise ValueError('Conflicting tool identity.')
                    for key in ('protocol_tool_call_id','action','outcome'):
                        value=identity.get(key)
                        if isinstance(value,str):item[key]=value
                    item['evidence'].append(ref);used=True
                elif match:=re.fullmatch(r'(?:Prompt budget|Tool-loop prompt budget): (\d+) tokens \+ (\d+) reply allowance < (\d+)(?:; removed_exchanges=(\d+))?\.',text):
                    prompt,allowance,capacity=map(int,match.groups()[:3])
                    output['budgets'].append({'request_number':req,'prompt_tokens':prompt,'reply_allowance':allowance,'capacity':capacity,'removed_exchanges':int(match[4]) if match[4] else None,**ref});used=True
                elif text.startswith('Reply completed: finish_reason='):
                    output['finish_reason']=text.removeprefix('Reply completed: finish_reason=').removesuffix('.');used=True
            elif lookup=='errors':
                from retention import failure_identity
                if failure_identity('diagnostic',raw.encode()):
                    output['failures'].append({'component':failure_identity('diagnostic',raw.encode())[3], 'request_number':req,'tool_number':tool,'detail':text[:300],**ref});used=True
                elif text.startswith(('Message interrupted:', 'Model Request interrupted:', 'Tool Call interrupted:')):
                    output['failures'].append({'component':'interruption','detail':text[:300],**ref});used=True
        fields = connection_fields(raw) if row['stream']=='diagnostic' else None
        if fields and fields['request_id'] in connection_ids and (tag or fields.get('source')=='Scarecrow'):
            from vault_diagnostics import clean_event
            safe_fields = clean_event(fields)
            if safe_fields['event'] not in ('request_started','request_received','request_completed','request_failed','request_aborted'):
                continue
            if lookup=='processing':
                output['connections'].append({**safe_fields, **ref});used=True
                # Preserve the integration source separately from evidence origin.
                output['connections'][-1]['component']=safe_fields['source']
                output['connections'][-1]['http_request_id']=output['connections'][-1].pop('request_id')
            elif lookup=='errors' and not tag and fields.get('event') in ('request_failed','request_aborted'):
                output['failures'].append({'component':'vault','http_request_id':fields['request_id'],
                    'http_status':fields.get('http_status'),'detail':fields['event'],**ref});used=True
        if row['stream']=='discord' and lookup in ('delivery','errors'):
            match=re.fullmatch(r'\S+ (.*?) (\{.*\})',raw,re.S)
            if not match:continue
            title,fields=match[1],json.loads(match[2])
            if not isinstance(fields,dict):raise ValueError('Malformed Discord record.')
            if fields.get('log_message_id')!=identifier:continue
            if conversation!='discord:'+str(fields.get('sender_id')):raise ValueError('Discord sender does not match conversation scope.')
            if lookup=='delivery':
                if title=='========== MESSAGE END | Discord delivery ==========':
                    ends+=1
                    if fields.get('outcome') not in ('delivered','failed','interrupted','unsupported','ignored'):raise ValueError('Invalid delivery outcome.')
                    output['outcome']=fields['outcome'];used=True
                if title=='Discord chunk sent.' and fields.get('kind')=='answer':
                    output['chunks_sent']+=1;used=True
                for key in ('adapter_queue_ms','main_queue_ms','processing_ms','local_response_ms','total_ms'):
                    v=fields.get(key)
                    if type(v) in (int,float) and 0<=v<float('inf'):
                        if key == 'total_ms':
                            # A failure timer must never be labeled successful delivery.
                            name = ('receipt_to_delivery_ms' if title == 'Discord answer delivered.' else
                                    'receipt_to_failure_ms' if title.startswith('Discord turn failed;') else None)
                            if name is None:continue
                        else:name=key
                        output['timings_ms'][name]=v;used=True
            elif title.startswith(('Discord turn failed;', 'Discord chunk failed.')):
                output['failures'].append({'component':'delivery','detail':title,**ref});used=True
        if used:evidence.append(ref)
    if starts>1 or ends>1:raise ValueError('Repeated message boundaries are ambiguous.')
    if lookup=='processing':
        output['tools']=list(tools.values())
        if starts!=1 or ends!=1:
            output['outcome']='incomplete' if evidence else 'unknown'
            notes.append('Processing boundaries are incomplete; retained evidence may be missing.')
        elif output['started_at'] and output['ended_at']:
            elapsed=(datetime.fromisoformat(output['ended_at'])-datetime.fromisoformat(output['started_at'])).total_seconds()*1000
            output['processing_boundary_elapsed_ms']=round(elapsed,3) if elapsed>=0 else None
        requests = output['requests']
        numbers = [r['request_number'] for r in requests]
        if len(set(numbers)) != len(numbers):raise ValueError('Repeated request usage is ambiguous.')
        output['recorded_token_totals'] = {
            'usage_records': len(requests),
            'input_tokens_summed': sum(r['prompt_tokens'] for r in requests) if requests and all(r['prompt_tokens'] is not None for r in requests) else None,
            'generated_tokens_including_reasoning': sum(r['completion_tokens'] for r in requests) if requests and all(r['completion_tokens'] is not None for r in requests) else None,
        }
        notes.append('Token usage is per request; receipt time is not pure generation time.')
    if lookup=='delivery':notes.append('No delivery ending means unknown; timings overlap and must not be added.')
    if lookup=='errors':notes.append('No matching recognized failures does not prove success; missing or expired evidence may be unavailable.')
    return output,evidence,list(dict.fromkeys(notes))


def setup(path):
    from setup_datasheet import START,END
    with Path(path).open('rb') as stream:raw=stream.read(128*1024+1)
    if len(raw)>128*1024:raise ValueError('Setup datasheet exceeds limit.')
    text=raw.decode()
    if text.count(START)!=1 or text.count(END)!=1:raise ValueError('Invalid datasheet markers.')
    if text.index(END)<text.index(START):raise ValueError('Datasheet markers are out of order.')
    block=text.split(START,1)[1].split(END,1)[0]
    fields=[]
    for line in block.splitlines():
        parts=line.split('|')
        if len(parts)==5 and parts[0]==parts[-1]=='':
            name,value,source=(x.strip() for x in parts[1:4])
            if name == 'Runtime version':name = 'llama.cpp runtime version'
            if name not in ('Fact','---'):fields.append({'name':name,'value':value,'source':source})
    stamp=re.search(r'Updated \(UTC\): (\S+)',block)
    state=re.search(r'Startup status: \*\*(\w+)\*\*',block)
    return {'observed_at':stamp[1] if stamp else None,'startup_status':state[1] if state else 'unknown','fields':fields}


def current(socket_path):
    result={'model_server':'unknown','discord':'unknown','tools':None,'processing':'unknown','obsidian':{'status':'unknown','observed_at':None}}
    if not socket_path:return result
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5);client.connect(str(socket_path))
            client.sendall(b'{"query":"status"}\n')
            with client.makefile('rb') as stream:raw=stream.readline(16385)
            if len(raw)>16384:raise ValueError('Status result exceeds limit.')
            reply=json.loads(raw)
            if reply.get('type')=='operator_status':return reply['data']
    except (OSError,ValueError):pass
    return result


def handle(form, *, database=None, session=None, conversation=None, before_message_id=None, datasheet=None, socket_path=None, live=True):
    validate(form)
    result={'lookup':form['lookup'],'status':'ok','queried_at':now(),'data':{},'evidence':[],'limitations':[], 'field_meanings':FIELD_MEANINGS[form['lookup']]}
    if form['lookup']=='setup':
        result['data']=setup(datasheet)
        result['evidence']=[{'source':'setup-datasheet.md','observed_at':result['data']['observed_at']}]
        result['limitations']=['Recorded startup information, not current status.']
        if not result['data']['fields']:result['status']='unavailable'
        elif result['data']['startup_status']!='ready':result['status']='partial'
    elif form['lookup']=='status':
        result['data']=current(socket_path)
        if socket_path:
            from operator_status import probe
            discord=probe(socket_path)
            if discord:
                result['data']['discord']=discord['discord']
                result['evidence'].append({'source':'Discord status probe','observed_at':discord['observed_at']})
        result['status']='partial' if any(result['data'].get(k) in (None,'unknown') for k in ('model_server','discord','tools','processing')) else 'ok'
        if result['data'].get('observed_at'):
            result['evidence'].append({'source':'local status probe','observed_at':result['data']['observed_at']})
        obsidian=result['data'].get('obsidian')
        if not isinstance(obsidian,dict) or obsidian.get('status') in ('unknown','unavailable'):
            result['status']='partial'
        if isinstance(obsidian,dict):
            result['evidence'].append({'source':'Scarecrow status probe','observed_at':obsidian.get('observed_at')})
        result['limitations']=['Missing observations are unknown; unavailable vault probes do not prove Obsidian is closed. Each observation has its own time.','Startup records are never substituted for current status.']
    else:
        if not database or not session or not conversation:raise ValueError('Operator must bind database, session and conversation.')
        with closing(open_read(database)) as db:
            deadline=time.monotonic()+2
            db.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
            db.execute('BEGIN')
            version=db.execute('PRAGMA user_version').fetchone()[0]
            generation=db.execute('SELECT generation FROM memory_epoch').fetchone()[0] if version>=4 else None
            if form['target']=='previous_message':
                if not before_message_id:raise ValueError('previous_message requires an operator-supplied triggering message ID.')
                validate_id(before_message_id)
                anchors=db.execute("SELECT id FROM messages WHERE session_id=? AND conversation_id=? AND message_id=? AND role='user' AND kind='input'",(session,conversation,before_message_id)).fetchall()
                if len(anchors)!=1:raise ValueError('Triggering message is missing or ambiguous in this scope.')
                row=db.execute("SELECT message_id FROM messages WHERE session_id=? AND conversation_id=? AND role='user' AND kind='input' AND id<? ORDER BY id DESC LIMIT 1",(session,conversation,anchors[0][0])).fetchone()
                identifier=row[0] if row else None
            else:identifier=form['message_id']
            scopes=db.execute('SELECT DISTINCT conversation_id FROM messages WHERE session_id=? AND message_id=?',(session,identifier)).fetchall()
            if not identifier or not scopes:
                result.update(status='unavailable',limitations=['Message not found in the bound session/conversation.'])
                return result
            if {r[0] for r in scopes}!={conversation}:raise ValueError('Message is outside the bound conversation scope.')
            saved=records(db,session,identifier)
        if live:
            from ram_logs import read_live
            found=read_live(database,session,'message',0,message_id=identifier)
            if found:
                payload=json.loads(found[1])
                if payload.get('generation')!=generation:raise ValueError('Memory reset during query; retry.')
                if payload.get('error'):raise ValueError(payload['error'])
                saved+=payload['events']
            else:result['limitations'].append('Live message evidence unavailable; only saved records inspected.')
        with closing(open_read(database)) as db:
            if generation is not None and db.execute('SELECT generation FROM memory_epoch').fetchone()[0]!=generation:raise ValueError('Memory reset during query; retry.')
        data,evidence,notes=extract(form['lookup'],merge(saved),identifier,conversation)
        result.update(data=data,evidence=evidence,message_id=identifier,
                      message_id_meaning='Incoming user message ID anchoring this exchange, not the outgoing assistant reply ID.')
        result['limitations']+=notes
        if not evidence:result['status']='unavailable' if form['lookup']!='errors' else 'no_matches'
        elif data.get('outcome') in ('unknown','incomplete'):result['status']='partial'
    if len(json.dumps(result,allow_nan=False).encode())>MAX_RESULT:raise ValueError('Query result exceeds limit.')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    root=Path(__file__).resolve().parents[2]
    parser.add_argument('--database',type=Path,default=root/'data/conversations/marionette.sqlite3')
    parser.add_argument('--session');parser.add_argument('--conversation');parser.add_argument('--before-message-id')
    parser.add_argument('--datasheet',type=Path,default=root/'docs/active/setup-and-maintenance/setup-datasheet.md')
    parser.add_argument('--socket',type=Path,default=root/'data/session/chat.sock')
    parser.add_argument('--saved-only',action='store_true')
    args=parser.parse_args()
    import sys,sqlite3
    try:
        raw=sys.stdin.buffer.read(4097)
        if len(raw)>4096:raise ValueError('Request exceeds 4 KiB.')
        form=json.loads(raw)
        result=handle(form,database=args.database,session=args.session,conversation=args.conversation,before_message_id=args.before_message_id,datasheet=args.datasheet,socket_path=args.socket,live=not args.saved_only)
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as error:
        print(json.dumps({'status':'error','error':str(error)}));return 1
    print(json.dumps(result,indent=2,allow_nan=False));return 0


if __name__=='__main__':
    raise SystemExit(main())
