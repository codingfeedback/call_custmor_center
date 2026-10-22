"""본인 번호 발급 뒤에만 켜는 ClawOps SDK 역방향 WebSocket 연결."""
import asyncio
import os
import re
from clawops.agent import ClawOpsAgent
from clawops_session import LocalSession
from handoff import Settings
from audio import Speech, synthesize
from worker import GREETING


def live_config(env):
    if env.get('CLAWOPS_LIVE','0')!='1':
        raise ValueError('외부 연결 비활성. 번호 없는 검증은 check_clawops.py를 실행하세요.')
    values={key:env.get(key,'').strip() for key in ('CLAWOPS_API_KEY','CLAWOPS_ACCOUNT_ID','CLAWOPS_NUMBER')}
    if any(not value or 'CHANGE_ME' in value or 'your-' in value for value in values.values()):
        raise ValueError('실제 ClawOps API 키·Account ID·070 번호를 설정하세요.')
    number=values['CLAWOPS_NUMBER'].replace('-','').replace(' ','')
    if number.startswith('+82'): number='0'+number[3:]
    if not re.fullmatch(r'070[0-9]{8}',number): raise ValueError('CLAWOPS_NUMBER는 발급받은 070 번호여야 합니다.')
    values['CLAWOPS_NUMBER']=number
    settings=Settings.from_env(env)
    return values,settings

async def main():
    values,settings=live_config(os.environ)
    speech=await asyncio.to_thread(Speech)
    await asyncio.to_thread(synthesize,GREETING)
    # 로컬 모델은 하나를 공유하고 수락 훅에서 동시 1통화만 허용한다.
    agent=ClawOpsAgent(api_key=values['CLAWOPS_API_KEY'],account_id=values['CLAWOPS_ACCOUNT_ID'],
        base_url='https://api.claw-ops.com',from_=values['CLAWOPS_NUMBER'],
        session_factory=lambda:LocalSession(settings,speech=speech),recording=False,builtin_tools=[],prewarm_enabled=False)
    occupied=set()
    @agent.on_incoming
    async def screen(call):
        if occupied: await call.reject('busy')
        else: occupied.add(call.call_id)
    @agent.on('call_end')
    async def release(call): occupied.discard(call.call_id)
    print('로컬 음성 준비 완료. ClawOps 수신 연결 시작. 전환 활성화:',settings.enabled,flush=True)
    await agent.serve(handover_wait=0)

if __name__=='__main__':
    asyncio.run(main())
