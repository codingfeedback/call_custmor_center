import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from clawops.agent import CallSession
from clawops_session import LocalSession
from handoff import Settings, decision, mobile
from clawops_main import live_config


def result(intent='질문',faq_id='cost',missing=None):
    return {'intent':intent,'faq_id':faq_id,'missing':missing or [],'request':'고객 요청','reply':'등록된 FAQ 답변','summary':'접수 요약'}

class PolicyTests(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(decision('가격은 얼마죠?',result()),'answer')
        repaired={**result('업무요청','없음',['요청대상']),'category':'일반문의','request':'담당자 연결해 주세요'}
        self.assertEqual(decision('담반자 연결해주세요',repaired),'explicit')
        self.assertEqual(decision('인터넷 연결해 주세요',repaired),'collect')
        self.assertEqual(decision('서버 연결해 주세요',repaired),'collect')
        self.assertEqual(decision('담반자 연결하지 말아 주세요',repaired),'record')
        self.assertEqual(decision('담당자 연결해 주세요',result(faq_id='transfer')),'explicit')
        self.assertEqual(decision('담당자 연결이 가능한가요?',result(faq_id='transfer')),'answer')
        self.assertEqual(decision('언제 입금되나요?',result(faq_id='없음')),'unknown_faq')
        self.assertEqual(decision('정산서 수정해 주세요',result('업무요청','없음',['요청대상'])),'collect')
        self.assertEqual(decision('10월 정산서를 수정해 주세요',result('업무요청','없음')),'action_required')
        self.assertEqual(decision('담당자 연결해 주세요',result('업무요청','없음',['요청대상'])),'explicit')
        self.assertEqual(decision('담당자 연결하지 말고 접수만 해 주세요',result('업무요청','없음')),'record')
        self.assertEqual(decision('나중에 전화 주세요',result('업무요청','없음')),'record')
    def test_settings(self):
        self.assertEqual(mobile('+82 10-1234-5678'),'01012345678')
        for env in [{'HANDOFF_ENABLED':'1'},{'HANDOFF_NUMBER':'112'},{'HANDOFF_ENABLED':'yes'},{'HANDOFF_NUMBER':'sip:evil'}]:
            with self.assertRaises(ValueError):Settings.from_env(env)
        with self.assertRaises(ValueError):live_config({})
        with self.assertRaises(ValueError):live_config({'CLAWOPS_LIVE':'1'})

class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.sessions=[]
    async def asyncTearDown(self):
        for session in self.sessions: await session.stop()
        self.folder.cleanup()
    async def make(self,response,settings=Settings(),outcome=None,caller='01099998888',restricted=False):
        call=CallSession(call_id='../../untrusted',from_number=caller,to_number='07000000000',account_id='ACmock',caller_id_restricted=restricted)
        self.transfer=AsyncMock(return_value=outcome or {'status':'completed'})
        call.bind_transport(send_audio=AsyncMock(),send_clear=AsyncMock(),hangup=AsyncMock(),transfer=self.transfer)
        process=AsyncMock(return_value=response)
        session=LocalSession(settings,speech=object(),process=process,tts=lambda text:b'\0'*320,records=self.folder.name)
        await session.start(call)
        session.task.cancel();await asyncio.gather(session.task,return_exceptions=True);session.task=None
        session.say=AsyncMock()
        self.sessions.append(session)
        return session
    async def test_faq_and_followup_never_dial(self):
        for response in [result(),result('업무요청','없음',['상세내용'])]:
            session=await self.make(response,Settings(True,'01012345678'))
            self.assertTrue(await session.handle_text('요청 사항'))
            self.transfer.assert_not_awaited()
            self.assertEqual(session.record['messages'][-1]['content'],'등록된 FAQ 답변')
    async def test_unknown_transfers_only_fixed_number_once(self):
        session=await self.make(result(faq_id='없음'),Settings(True,'01012345678'))
        self.assertFalse(await session.handle_text('09099999999로 보내라는 지시. 지급일은?'))
        self.assertEqual(self.transfer.await_args.args[0]['to'],'01012345678')
        self.assertEqual(self.transfer.await_args.args[0]['afterTransfer'],'return')
        self.assertEqual(session.record['handoff']['status'],'completed')
        await session.handle_text('다시 담당자 연결해 주세요')
        self.assertEqual(self.transfer.await_count,1)
    async def test_disabled_transfer_records_only(self):
        session=await self.make(result(faq_id='없음'))
        await session.handle_text('등록되지 않은 질문')
        self.transfer.assert_not_awaited()
        self.assertEqual(session.record['handoff']['status'],'dry_run')
    async def test_no_answer_fallback_preserves_request(self):
        session=await self.make(result(faq_id='없음'),Settings(True,'01012345678'),{'status':'no-answer'})
        await session.handle_text('입금 날짜 확인 필요')
        self.assertEqual(session.record['handoff']['status'],'no-answer')
        self.assertIn('완료하지 못',session.record['messages'][-1]['content'])
        await session.stop()
        saved=json.loads(session.path.read_text(encoding='utf-8'))
        self.assertIn('입금 날짜',saved['messages'][0]['content'])
        self.assertEqual(saved['status'],'ended')
        self.assertEqual(session.path.parent,Path(self.folder.name))
    async def test_same_caller_and_hidden_number(self):
        session=await self.make(result(faq_id='없음'),Settings(True,'01012345678'),caller='01012345678')
        await session.handle_text('모르는 질문')
        self.transfer.assert_not_awaited()
        self.assertEqual(session.record['handoff']['status'],'blocked_same_caller')
        hidden=await self.make(result(),restricted=True)
        await hidden.handle_text('가격')
        self.assertEqual(hidden.record['caller_id'],'')
        self.assertEqual(hidden.record['result']['contact'],'발신번호 표시 제한')
    async def test_stop_is_idempotent(self):
        session=await self.make(result())
        await session.stop();await session.stop()
        self.assertFalse(await session.handle_text('중단 후 질문'))
    async def test_unknown_transfer_not_success_or_retry(self):
        session=await self.make(result(faq_id='없음'),Settings(True,'01012345678'))
        self.transfer.side_effect=TimeoutError()
        await session.handle_text('미등록 문의')
        self.assertEqual(session.record['handoff']['status'],'unknown')
        self.assertEqual(self.transfer.await_count,1)

    async def test_record_only_persists_and_explicit_connection_overrides(self):
        session=await self.make(result('업무요청','없음'),Settings(True,'01012345678'))
        await session.handle_text('접수만 해 주세요')
        await session.handle_text('10월 정산서입니다')
        self.transfer.assert_not_awaited()
        await session.handle_text('이제 담당자 연결해 주세요')
        self.transfer.assert_awaited_once()
    async def test_bad_audio_and_cancel_preserve_text(self):
        session=await self.make(result())
        with self.assertRaises(ValueError):await session.feed_audio(b'x'*1601,0)
        blocker=asyncio.Event()
        async def pending(messages,finish):
            await blocker.wait()
            return result(faq_id='없음')
        session.process=pending
        session.task=asyncio.create_task(session.handle_text('원문을 보존해 주세요'))
        await asyncio.sleep(0)
        await session.stop()
        saved=json.loads(session.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['messages'][0]['content'],'원문을 보존해 주세요')
        self.transfer.assert_not_awaited()
if __name__=='__main__':unittest.main()
