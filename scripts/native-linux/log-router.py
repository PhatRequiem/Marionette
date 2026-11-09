#!/usr/bin/env python3
"""Number and route diagnostics to two files without a third raw log."""
import datetime
import re
import sys

RECORD = re.compile(rb'^\d[\d.]*\s+([A-Z])\s+(.*)')
COMPONENT = re.compile(rb'^(srv|slot|que|res)\s+([^:]+):\s*(.*)')
SERVER_FUNCTIONS = {b'init_listene', b'server_setup', b'server_run_i', b'server_on_li',
                    b'server_strea', b'get_availabl', b'stop', b'init'}
MODEL_FUNCTIONS = {b'load_model', b'load', b'update', b'decode', b'process_sing',
                   b'eval_llama_c', b'update_slots', b'reset', b'launch_slot_',
                   b'create_check', b'init_sampler', b'process_toke',
                   b'handle_last_', b'print_timing', b'release'}
QUEUE_FUNCTIONS = {b'start_loop', b'post', b'process_new_', b'yield_to_que',
                   b'add_waiting_', b'remove_waiti', b'send'}
MODEL_PREFIXES = (b'llama_', b'ggml_', b'load_tensors:', b'print_info:',
                  b'print_meta:', b'build_graph:', b'common_init_', b'Parsed message:')


def category(line):
    # Unrecognized and unprefixed continuation lines are deliberately shared.
    record = RECORD.match(line)
    if not record:
        return 'both'
    level, message = record.groups()
    if level not in (b'I', b'D', b'T'):
        return 'both'
    component = COMPONENT.match(message)
    if component:
        owner, function, detail = component.groups()
        function = function.strip()
        if owner in (b'que', b'res') and function in QUEUE_FUNCTIONS:
            return 'server'
        if owner == b'srv' and (
            function in SERVER_FUNCTIONS or detail.startswith(b'http:')
            or b'terminating stream' in detail or b'cleaning up before exit' in detail
            or detail == b'all slots are idle'
        ):
            return 'server'
        if owner in (b'srv', b'slot') and (
            function in MODEL_FUNCTIONS or (owner == b'slot' and function == b'operator()')
        ):
            return 'model'
    if message.startswith(MODEL_PREFIXES):
        return 'model'
    return 'both'


def route(source, server, model):
    for number, line in enumerate(source, 1):
        destination = category(line)
        # Runtime elapsed timestamps and original bytes are left untouched.
        # Receipt time also timestamps launcher messages lacking a runtime clock.
        now = datetime.datetime.now().astimezone().isoformat(timespec='microseconds')
        event = f'[event {number:08d}] [{now}] '.encode() + line
        for name, output in [('server', server), ('model', model)]:
            if destination in (name, 'both'):
                output.write(event)
                output.flush()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: log-router.py SERVER_LOG MODEL_LOG')
    with open(sys.argv[1], 'ab', buffering=0) as server, open(sys.argv[2], 'ab', buffering=0) as model:
        route(sys.stdin.buffer, server, model)
