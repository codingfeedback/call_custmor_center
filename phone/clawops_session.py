"""ClawOps Session protocol -> 기존 로컬 STT/접수/TTS. 음성은 G.711 μ-law."""
import asyncio
import audioop
import json
import os
import time
import uuid
from pathlib import Path
from audio import Segmenter, Speech, synthesize
from worker import intake, GREETING
from handoff import Settings, decision, mobile, spoken

class LocalSession:
    def __init__(self, settings=None, speech=None, process=intake, tts=synthesize, records='/runtime/clawops/calls'):
        self.settings=settings or Settings()
        self.speech=speech
        self.process=process
        self.tts=tts
        self.records=Path(records)
        self.call=None
        self.task=None
        self.listening=False
        self.closed=False
        self.queue=asyncio.Queue(maxsize=100)
        self.record=None
        self.path=None
        self.transfer_attempted=False
        self.record_only=False

    async def prewarm(self):
        if self.speech is None: self.speech=await asyncio.to_thread(Speech)
        await asyncio.to_thread(self.tts,GREETING)

    async def attach(self, call):
        await self.start(call)

    async def start(self, call):
        if self.task: raise RuntimeError('중복 세션')
        self.call=call
        self.records.mkdir(parents=True,exist_ok=True)
        # 통신망 call_id를 파일 경로에 사용하지 않는다.
        ident=str(uuid.uuid4())
        self.path=self.records/(ident+'.json')
        caller='' if call.caller_id_restricted else call.from_number
        self.record={'id':ident,'call_id':call.call_id,'caller_id':caller,'caller_id_verified':False,
                     'status':'active','messages':[],'result':None,'handoff':None,'started_at':time.time()}
        self.save()
        # start()는 미디어 연결 전에 호출되므로 즉시 반환하고 수신 루프를 막지 않는다.
        self.task=asyncio.create_task(self.run())

    def save(self):
        if not self.path: return
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.record,ensure_ascii=False,indent=2),encoding='utf-8')
        os.chmod(temp,0o600)
        temp.replace(self.path)

    async def feed_audio(self, audio, timestamp):
        if not isinstance(audio,bytes) or not 1<=len(audio)<=1600:
            raise ValueError('잘못된 μ-law 프레임')
        if self.listening and not self.closed:
            try: self.queue.put_nowait(('audio',audio))
            except asyncio.QueueFull:
                self.record['error']='audio_backlog'
                await self.call.hangup()

    async def feed_dtmf(self, digits):
        if self.listening and '#' in digits:
            try: self.queue.put_nowait(('end',b''))
            except asyncio.QueueFull: pass

    async def say(self, text):
        if self.closed: return
        self.listening=False
        while not self.queue.empty(): self.queue.get_nowait()
        pcm=await asyncio.to_thread(self.tts,text[:2500])
        if self.closed: return
        audio=audioop.lin2ulaw(pcm,2)
        # shortcut: SDK의 재생 완료 공개 인터페이스가 없어 20ms로 송신한다. 실회선 지연이 크면 mark 연동으로 교체.
        for offset in range(0,len(audio),160):
            if self.closed: return
            await self.call.send_audio(audio[offset:offset+160])
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.3)
        self.listening=not self.closed

    async def handle_text(self,text):
        text=text.strip()[:3000]
        if not text or self.closed or self.transfer_attempted: return False
        self.listening=False
        messages=self.record['messages']
        messages.append({'role':'user','content':text})
        self.save()
        finish=text.rstrip('.!?') in ('접수 종료','통화 종료','종료해 주세요')
        result=await self.process(messages,finish)
        if self.closed: return False
        result['contact']=self.record['caller_id'] or '발신번호 표시 제한'
        self.record['result']=result
        action='record' if finish else decision(text,result)
        if action=='record': self.record_only=True
        elif action=='explicit': self.record_only=False
        if self.record_only and action in ('unknown_faq','action_required'): action='record'
        self.record['decision']=action
        self.save()
        if action in ('explicit','unknown_faq','action_required'):
            return await self.handoff(action)
        reply='요청 내용을 기록했습니다. 감사합니다.' if finish else spoken(result,action)
        self.record['messages'].append({'role':'assistant','content':reply})
        self.save()
        await self.say(reply)
        return not finish

    async def handoff(self,reason):
        target=self.settings.number
        try: self_call=bool(target) and mobile(self.record['caller_id'])==target
        except ValueError: self_call=False
        state={'reason':reason,'status':'planned','attempts':0}
        self.record['handoff']=state
        if not self.settings.enabled or self_call or self.transfer_attempted:
            state['status']='blocked_same_caller' if self_call else ('already_attempted' if self.transfer_attempted else 'dry_run')
            reply='담당자 확인이 필요한 내용을 기록했습니다. 현재는 전화 연결을 하지 않습니다.'
            self.record['messages'].append({'role':'assistant','content':reply})
            self.save();await self.say(reply)
            return False
        # 중복 판단으로 이중 발신하지 않도록 먼저 기록하고 자동 재시도하지 않는다.
        self.transfer_attempted=True
        state.update(status='requesting',attempts=1)
        self.save()
        reply='담당자 확인이 필요한 문의입니다. 담당자에게 연결하겠습니다.'
        self.record['messages'].append({'role':'assistant','content':reply})
        self.save();await self.say(reply)
        self.listening=False
        try:
            outcome=await self.call.transfer(target,mode='warm',after_transfer='return',timeout=25,
                caller_id_mode='account',whisper=(self.record['result'].get('request') or '담당자 확인 요청')[:200])
            state['status']=outcome.get('status','unknown')
        except (TimeoutError,ConnectionError):
            # 발신 여부가 불명확하므로 재발신하거나 성공으로 처리하지 않는다.
            state['status']='unknown'
        except Exception as error:
            state.update(status='error',error=type(error).__name__)
        self.save()
        if not self.closed:
            reply='담당자와의 통화가 종료되었습니다. 감사합니다.' if state['status']=='completed' else '담당자 연결을 완료하지 못했습니다. 요청 내용과 표시된 발신번호를 기록했습니다. 감사합니다.'
            self.record['messages'].append({'role':'assistant','content':reply})
            self.save();await self.say(reply)
        return False

    async def run(self):
        try:
            if self.speech is None: self.speech=await asyncio.to_thread(Speech)
            await self.say(GREETING)
            start=time.monotonic()
            for _ in range(15):
                segment=Segmenter();pcm=None
                deadline=min(start+300,time.monotonic()+45)
                while pcm is None:
                    kind,audio=await asyncio.wait_for(self.queue.get(),max(0,deadline-time.monotonic()))
                    if kind=='end':
                        await self.say('접수를 종료합니다. 감사합니다.')
                        return
                    pcm=segment.push(audioop.ulaw2lin(audio,2))
                if not pcm: continue
                self.listening=False
                text=await asyncio.to_thread(self.speech.transcribe,pcm)
                if self.closed: return
                if not text:
                    await self.say('잘 듣지 못했습니다. 다시 말씀해 주세요.')
                    continue
                if not await self.handle_text(text): return
        except asyncio.TimeoutError:
            await self.say('응답이 없어 접수를 종료합니다. 감사합니다.')
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.record['error']=type(error).__name__
            self.save()
            if not self.closed:
                await self.say('처리 중 오류가 발생했습니다. 받은 내용은 기록했습니다. 감사합니다.')
        finally:
            if not self.closed: await self.call.hangup()

    async def stop(self):
        if self.closed: return
        self.closed=True;self.listening=False
        if self.task and self.task is not asyncio.current_task():
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
        if self.record:
            if self.record.get('handoff',{} ) and self.record['handoff']['status']=='requesting':
                self.record['handoff']['status']='unknown'
            self.record['status']='error' if self.record.get('error') else 'ended'
            self.record['ended_at']=time.time()
            self.save()

    def get_telemetry(self):
        return None
