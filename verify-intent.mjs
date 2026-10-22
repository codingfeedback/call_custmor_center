import assert from 'node:assert/strict';
const cases=[
{input:'이 테스트는 유료인가요?',intent:'질문',pattern:/유료 AI API 없이/},
{input:'영업시간이 어떻게 되나요?',intent:'질문',pattern:/등록된 정보에서 답을 찾지 못/},
{input:'정산서 수정해 주세요.',intent:'업무요청',pattern:/어떤 건|어떤 내용/},
{input:'내일 오후 3시로 상담 예약을 잡아 주세요.',intent:'업무요청'},
{input:'로그인하면 비밀번호 오류라고 나오는데 해결해 주세요.',intent:'업무요청'}];
for(const c of cases){const r=await fetch('http://127.0.0.1:8765/api/intake',{method:'POST',headers:{'Content-Type':'application/json','X-Intake-Client':'local'},body:JSON.stringify({messages:[{role:'user',content:c.input}]})});const d=await r.json();assert.equal(r.status,200,JSON.stringify(d));console.log(JSON.stringify({input:c.input,...d}));assert.equal(d.intent,c.intent);if(c.pattern)assert.match(d.reply,c.pattern);assert.doesNotMatch(d.reply,/언제까지|연락처|회신받을|전화번호|이메일/);}
console.log('PASS: 등록 FAQ·미등록 질문·업무 요청 분류·연락처 질문 없음');
