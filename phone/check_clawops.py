"""실제 ClawOps SDK를 loopback 모의 제어/미디어 WS에 연결한다. 외부 전화망 호출 없음."""
import argparse
import asyncio
import audioop
import base64
import json
import tempfile
import uuid
from pathlib import Path
from aiohttp import web
from clawops.agent import ClawOpsAgent
from clawops_session import LocalSession
from handoff import Settings
from audio import Speech, synthesize
from worker import intake

async def until(predicate,timeout=120):
    async def wait():
        while not predicate(): await asyncio.sleep(0.02)
    await asyncio.wait_for(wait(),timeout)

async def scenario(text,reply,settings,transfer_status='completed',real=False):
    shared={};transfers=[];outbound=[];ended=asyncio.Event()
    ident='CA'+uuid.uuid4().hex
    with tempfile.TemporaryDirectory() as folder:
        async def process(messages,finish=False):return dict(reply)
        class FakeSpeech:
            def transcribe(self,pcm):
                assert len(pcm)>1600
                return text
        speech=await asyncio.to_thread(Speech) if real else FakeSpeech()
        tts=synthesize if real else lambda _:b'\0'*320
        session=LocalSession(settings,speech,process=intake if real else process,tts=tts,records=folder)
        async def control(request):
            ws=web.WebSocketResponse();await ws.prepare(request);shared['control']=ws
            async for msg in ws:
                event=json.loads(msg.data)
                if event['event']=='agent.hello':
                    await ws.send_json({'event':'call.incoming','callId':ident,'from':'01099998888',
                        'mediaUrl':shared['media_url']})
                elif event['event']=='call.transfer':
                    transfers.append(event['transfer'])
                    await ws.send_json({'event':'call.transfer.completed' if transfer_status=='completed' else 'call.transfer.failed',
                        'callId':ident,'requestId':event['transfer']['requestId'],'transfer':{'status':transfer_status}})
            return ws
        async def media(request):
            ws=web.WebSocketResponse();await ws.prepare(request);shared['media']=ws
            await ws.send_json({'event':'start','start':{'streamId':'MZmock','callId':ident,'accountId':'ACmock',
                'mediaFormat':{'encoding':'audio/x-mulaw','sampleRate':8000,'channels':1}}})
            try:
                async for msg in ws:
                    event=json.loads(msg.data)
                    if event['event']=='media':outbound.append(base64.b64decode(event['media']['payload'],validate=True))
                    if event['event']=='mark':
                        await asyncio.sleep(0.02)
                        await ws.send_json(event)
            finally:
                if not shared['control'].closed:
                    await shared['control'].send_json({'event':'call.ended','callId':ident,'status':'completed','duration':1})
            return ws
        app=web.Application();app.router.add_get('/v1/accounts/ACmock/agent/listen',control);app.router.add_get('/media',media)
        runner=web.AppRunner(app);await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        port=site._server.sockets[0].getsockname()[1]
        shared['media_url']=f'ws://127.0.0.1:{port}/media'
        agent=ClawOpsAgent(api_key='mock-no-real-key',account_id='ACmock',base_url=f'http://127.0.0.1:{port}',
            from_='07000000000',session=session,recording=False,builtin_tools=[],prewarm_enabled=False)
        @agent.on('call_end')
        async def done(call):ended.set()
        try:
            await agent.connect()
            await until(lambda:session.listening and 'media' in shared)
            pcm=await asyncio.to_thread(tts,text) if real else (b'\x00\x10'*4000)
            pcm+=b'\0'*16000
            ulaw=audioop.lin2ulaw(pcm,2)
            for offset in range(0,len(ulaw),160):
                if session.closed:break
                await shared['media'].send_json({'event':'media','media':{'payload':base64.b64encode(ulaw[offset:offset+160]).decode(),
                    'timestamp':str(offset//8)}})
                await asyncio.sleep(0.02)
            if reply.get('faq_id') not in (None,'없음'):
                await until(lambda:len(session.record['messages'])>=2 and session.listening)
                await shared['media'].send_json({'event':'dtmf','dtmf':{'digit':'#','track':'inbound_track'}})
            await asyncio.wait_for(ended.wait(),150)
            assert outbound and all(0<len(x)<=160 for x in outbound),'출력 μ-law 프레임 없음'
            saved=json.loads(session.path.read_text(encoding='utf-8'))
            assert saved['messages'] and saved['status']=='ended',saved
            if reply.get('faq_id') not in (None,'없음'):
                assert not transfers,('FAQ에서 발신 발생',saved)
                assert saved['decision']=='answer',saved
            else:
                assert len(transfers)==(1 if settings.enabled else 0),(text,transfers,saved)
                assert saved['handoff']['status']==(transfer_status if settings.enabled else 'dry_run'),saved
                if transfers:assert transfers[0]['to']==settings.number
            return {'case':text,'real_local_audio':real,'decision':saved['decision'],'handoff':saved['handoff'],
                'transfers':len(transfers),'output_frames':len(outbound),'transcript':saved['messages'][0]['content']}
        except BaseException as error:
            failure=Path('/runtime/clawops/failures');failure.mkdir(parents=True,exist_ok=True)
            (failure/(ident+'.json')).write_text(json.dumps({'case':text,'error':type(error).__name__,'record':session.record},ensure_ascii=False,indent=2),encoding='utf-8')
            raise
        finally:
            await agent.disconnect();await runner.cleanup()

async def main(real=False):
    if real:
        import torch
        torch.manual_seed(42)
    faq={'intent':'질문','faq_id':'cost','missing':[],'request':'가격','reply':'무료 로컬 테스트입니다.'}
    unknown={'intent':'질문','faq_id':'없음','missing':['등록된 답변 없음'],'request':'담당자 연결','reply':'등록된 정보가 없습니다.'}
    owner=Settings(True,'01012345678')
    cases=[await scenario('이 테스트는 유료인가요?',faq,owner,real=real),
           await scenario('담당자 연결해 주세요',unknown,owner,real=real),
           await scenario('처음 듣는 질문',unknown,owner,'no-answer'),
           await scenario('처음 듣는 질문',unknown,Settings())]
    path=Path('/runtime/clawops');path.mkdir(parents=True,exist_ok=True)
    (path/('mock-verification-real-audio.json' if real else 'mock-verification.json')).write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(cases,ensure_ascii=False,indent=2))
    print('PASS: SDK control/media WebSocket, FAQ, fixed-number transfer, no-answer, dry-run. External calls: 0')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--real-audio',action='store_true');args=parser.parse_args()
    asyncio.run(main(args.real_audio))
