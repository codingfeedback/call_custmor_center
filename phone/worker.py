import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from audio import FRAME_BYTES, Segmenter, Speech, packet, read_packet, synthesize

CALLS = Path('/runtime/calls')
GREETING = '인공지능 접수 비서입니다. 통화 내용은 접수와 요약을 위해 텍스트로 기록됩니다. 어떤 업무로 연락하셨나요?'
busy = False

async def intake(messages, finish=False):
    process = await asyncio.create_subprocess_exec('node', '/app/phone/intake.mjs', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(process.communicate(json.dumps({'messages': messages, 'finish': finish}, ensure_ascii=False).encode()), 185)
        if process.returncode:
            raise RuntimeError('접수 프로그램 오류')
        return json.loads(out)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise

async def handle(reader, writer, speech):
    global busy
    if busy:
        writer.close()
        await writer.wait_closed()
        return
    busy = True
    receiving = None
    call = None
    path = None
    listening = False
    queue = asyncio.Queue(maxsize=100)
    try:
        kind, payload = await asyncio.wait_for(read_packet(reader), 5)
        if kind != 1 or len(payload) != 16:
            raise ValueError('UUID 헤더 필요')
        ident = str(uuid.UUID(bytes=payload))
        path = CALLS / (ident + '.json')
        call = json.loads(path.read_text(encoding='utf-8'))
        if call.get('status') != 'starting' or call.get('id') != ident:
            raise ValueError('등록되지 않은 통화')
        call.update(status='active', messages=[], result=None)

        def save():
            path.write_text(json.dumps(call, ensure_ascii=False, indent=2), encoding='utf-8')

        async def receive():
            while True:
                kind, data = await read_packet(reader)
                if kind == 0:
                    raise EOFError()
                if kind == 0xff:
                    raise RuntimeError('Asterisk 음성 오류')
                if kind not in (0x10, 3):
                    raise ValueError('지원하지 않는 음성 형식')
                if listening:
                    if queue.full():
                        raise RuntimeError('음성 처리 지연')
                    queue.put_nowait((kind, data))

        async def say(text):
            nonlocal listening
            listening = False
            while not queue.empty():
                queue.get_nowait()
            pcm = await asyncio.to_thread(synthesize, text)
            for offset in range(0, len(pcm), FRAME_BYTES):
                if receiving.done():
                    receiving.result()
                writer.write(packet(0x10, pcm[offset:offset + FRAME_BYTES].ljust(FRAME_BYTES, b'\0')))
                await writer.drain()
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.25)
            listening = True

        receiving = asyncio.create_task(receive())
        save()
        await say(GREETING)
        turn = Segmenter()
        for _ in range(15):
            pcm = None
            deadline = time.monotonic() + 45
            while pcm is None:
                get = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait([get, receiving], timeout=max(0, deadline - time.monotonic()), return_when=asyncio.FIRST_COMPLETED)
                if receiving in done:
                    get.cancel()
                    receiving.result()
                if get not in done:
                    get.cancel()
                    raise TimeoutError('무응답')
                kind, data = get.result()
                if kind == 3 and data == b'#':
                    await say('접수를 종료합니다. 감사합니다.')
                    return
                if kind == 0x10:
                    pcm = turn.push(data)
            if not pcm:
                continue
            listening = False
            text = await asyncio.to_thread(speech.transcribe, pcm)
            if not text:
                await say('잘 듣지 못했습니다. 다시 말씀해 주세요.')
                continue
            call['messages'].append({'role': 'user', 'content': text[:3000]})
            save()
            finish = text.strip().rstrip('.!?') in ('접수 종료', '통화 종료', '종료해 주세요')
            result = await intake(call['messages'], finish)
            result['contact'] = call.get('caller_id') or '발신번호 표시 제한'
            call['result'] = result
            call['messages'].append({'role': 'assistant', 'content': result['reply']})
            save()
            await say(result['reply'])
            if finish:
                return
    except (EOFError, asyncio.IncompleteReadError, ConnectionError):
        pass
    except Exception as error:
        if call is not None:
            call['error'] = type(error).__name__
        print('전화 처리 실패:', type(error).__name__, flush=True)
    finally:
        if receiving:
            receiving.cancel()
            await asyncio.gather(receiving, return_exceptions=True)
        if call is not None and path is not None:
            call['status'] = 'error' if 'error' in call else 'ended'
            call['ended_at'] = time.time()
            path.write_text(json.dumps(call, ensure_ascii=False, indent=2), encoding='utf-8')
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass
        finally:
            busy = False

async def main():
    CALLS.mkdir(parents=True, exist_ok=True)
    # 첫 전화 전에 STT·한국어 TTS를 실제로 준비한다.
    speech = await asyncio.to_thread(Speech)
    await asyncio.to_thread(synthesize, GREETING)
    server = await asyncio.start_server(lambda r, w: handle(r, w, speech), '127.0.0.1', 9092)
    Path('/runtime/voice-ready').write_text('ready', encoding='utf-8')
    print('AudioSocket ready: 127.0.0.1:9092', flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
