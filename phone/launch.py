import os
import signal
import subprocess
import time
from pathlib import Path
from config import render

for name, value in render(os.environ).items():
    Path('/etc/asterisk', name).write_text(value, encoding='utf-8')
ready = Path('/runtime/voice-ready')
ready.unlink(missing_ok=True)
children = []
def stop():
    for child in children:
        child.terminate()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()

signal.signal(signal.SIGTERM, lambda *_: exit(0))
signal.signal(signal.SIGINT, lambda *_: exit(0))
try:
    children.append(subprocess.Popen(['python', '/app/phone/worker.py']))
    while not ready.exists():
        if children[0].poll() is not None:
            raise RuntimeError('음성 서버 시작 실패')
        time.sleep(1)
    children.append(subprocess.Popen(['asterisk', '-f']))
    while all(child.poll() is None for child in children):
        time.sleep(1)
    raise RuntimeError('전화 프로세스가 종료됐습니다.')
finally:
    stop()
