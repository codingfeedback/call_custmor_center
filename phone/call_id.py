#!/usr/bin/python3
import json
import os
import sys
import uuid
from pathlib import Path

env = {}
for line in sys.stdin:
    if not line.strip():
        break
    key, _, value = line.partition(':')
    env[key] = value.strip()[:128]
call_id = str(uuid.uuid4())
folder = Path('/runtime/calls')
folder.mkdir(parents=True, exist_ok=True)
path = folder / (call_id + '.json')
with open(path, 'x', encoding='utf-8') as stream:
    os.chmod(path, 0o600)
    json.dump({'id': call_id, 'caller_id': env.get('agi_callerid', ''), 'caller_id_verified': False, 'status': 'starting'}, stream, ensure_ascii=False)
print('SET VARIABLE CALL_UUID "' + call_id + '"', flush=True)
sys.stdin.readline()
