"""전화 전환은 고정 설정 번호만 사용하며 모델 출력에서 번호를 읽지 않는다."""
import re
from dataclasses import dataclass


def mobile(value):
    value=value.replace('-', '').replace(' ', '')
    if value.startswith('+82'): value='0'+value[3:]
    if not re.fullmatch(r'010[0-9]{8}',value):
        raise ValueError('HANDOFF_NUMBER는 본인 휴대폰 010 번호여야 합니다.')
    return value

@dataclass(frozen=True)
class Settings:
    enabled: bool=False
    number: str=''

    @classmethod
    def from_env(cls, env):
        flag=env.get('HANDOFF_ENABLED','0')
        if flag not in ('0','1'): raise ValueError('HANDOFF_ENABLED는 0 또는 1')
        value=env.get('HANDOFF_NUMBER','').strip()
        target=mobile(value) if value else ''
        if flag=='1' and not target: raise ValueError('전환 활성화에는 HANDOFF_NUMBER가 필요합니다.')
        return cls(flag=='1',target)


def decision(text, result):
    compact=re.sub(r'\s+','',text)
    if re.search(r'(연결|전환|통화|전화돌리기).{0,5}(하지마|하지말|필요없|안해도)|접수만|기록만|메모만|나중에.{0,5}(연락|전화)',compact):
        return 'record'
    connection=re.search(r'(담당자|상담원|사람|직원).{0,8}(연결|바꿔|통화)',compact)
    if connection and re.search(r'해주|해줘|부탁|바꿔|원해|원합|싶|연결$',compact):
        return 'explicit'
    # 호칭 오인식은 정규화 요청을 참고하되 원문 명령과 일반문의 판단이 모두 있어야 한다.
    request=re.sub(r'\s+','',result.get('request',''))
    if (result.get('category')=='일반문의' and re.search(r'(연결|통화).{0,6}(주세|해줘|부탁)',compact)
        and re.search(r'담당자|상담원|사람|직원',request)
        and not re.search(r'인터넷|와이파이|서버|블루투스|기기',compact)):
        return 'explicit'
    if result.get('intent')=='질문' and result.get('faq_id') not in (None,'','없음'):
        return 'answer'
    if connection:
        return 'explicit'
    if result.get('intent')=='질문' and result.get('faq_id')=='없음':
        return 'unknown_faq'
    if result.get('missing'):
        return 'collect'
    if result.get('intent')=='업무요청':
        return 'action_required'
    return 'collect'


def spoken(result, action):
    if action=='record' or (result.get('intent')=='업무요청' and not result.get('missing')):
        return '요청 내용을 기록했습니다. 실제 업무 처리는 아직 하지 않았습니다. 추가로 남기실 내용이 있으면 말씀해 주세요.'
    return result['reply']
