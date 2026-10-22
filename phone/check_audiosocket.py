"""번호 없이 실제 PCM -> STT -> Node 접수 -> TTS 경로를 검증한다."""
import asyncio
import json
import time
import uuid
from pathlib import Path
from audio import FRAME_BYTES, packet, read_packet, synthesize

async def run():
    ident=str(uuid.uuid4());path=Path('/runtime/calls',ident+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'id':ident,'caller_id':'test-caller','caller_id_verified':False,'status':'starting'}),encoding='utf-8')
    reader,writer=await asyncio.open_connection('127.0.0.1',9092)
    writer.write(packet(1,uuid.UUID(ident).bytes));await writer.drain()
    received=0
    # 안내 음성이 끝날 때까지 기다려, 음성 재생 중 입력을 보내지 않는다.
    while True:
        try:
            kind,data=await asyncio.wait_for(read_packet(reader),0.8 if received else 30)
            assert kind==0x10
            received+=len(data)
        except asyncio.TimeoutError:
            assert received>0,'안내 음성 없음'
            break
    await asyncio.sleep(0.4)
    pcm=synthesize('이 테스트는 유료인가요?')+b'\0'*16000
    async def send():
        for offset in range(0,len(pcm),FRAME_BYTES):
            writer.write(packet(0x10,pcm[offset:offset+FRAME_BYTES].ljust(FRAME_BYTES,b'\0')))
            await writer.drain();await asyncio.sleep(0.02)
    await send()
    kind,data=await asyncio.wait_for(read_packet(reader),120)
    assert kind==0x10 and data,'AI 답변 오디오 없음'
    record=json.loads(path.read_text(encoding='utf-8'))
    assert record['result'] and len(record['messages'])==2,record
    assert record['result']['contact']=='test-caller'
    writer.write(packet(0));await writer.drain();writer.close();await writer.wait_closed()
    print('PASS: actual AudioSocket PCM -> Whisper -> Node intake -> Korean TTS; call',ident)

if __name__=='__main__': asyncio.run(run())
