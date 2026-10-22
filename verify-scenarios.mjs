import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
const endpoint='http://127.0.0.1:8765/api/intake';
async function ask(messages){const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-Intake-Client':'local'},body:JSON.stringify({messages})});const d=await r.json();assert.equal(r.status,200,JSON.stringify(d));assert.doesNotMatch(d.reply,/언제까지|회신받을|전화번호|이메일/);return d;}
const cases=[['이 테스트는 유료인가요?','질문','cost'],['담당자에게 전화 연결해 주세요.','업무요청',null],['영업시간이 어떻게 되나요?','질문','없음'],['정산서 금액을 수정해 주세요.','업무요청',null],['내일 오후 3시에 상담 예약해 주세요.','업무요청',null]];
const results=[];
for(const chained of [false,true]){const history=[];for(const [input,intent,id] of cases){const messages=chained?[...history,{role:'user',content:input}]:[{role:'user',content:input}];const d=await ask(messages);assert.equal(d.intent,intent);if(id)assert.equal(d.faq_id,id);if(input.startsWith('정산서'))assert.ok(['요청대상','상세내용'].includes(d.followup),JSON.stringify(d));if(input.startsWith('내일'))assert.doesNotMatch(d.reply,/날짜와 시간|원하시는 조치/);results.push({chained,input,...d});history.push({role:'user',content:input},{role:'assistant',content:d.reply});}}
const feature=JSON.parse(await readFile(new URL('./faq.json',import.meta.url),'utf8')).find(f=>f.id==='features').answer;
for(const input of ['대금지급일이 언제죠?','영업시간이 어떻게 되나요?']){const d=await ask([{role:'user',content:'무슨 기능이 있나요?'},{role:'assistant',content:feature},{role:'user',content:input}]);assert.equal(d.faq_id,'없음');assert.notEqual(d.reply,feature);results.push({input,...d});}
const first=await ask([{role:'user',content:'정산서 금액을 수정해 주세요.'}]);const next=await ask([{role:'user',content:'정산서 금액을 수정해 주세요.'},{role:'assistant',content:first.reply},{role:'user',content:'10월 정산서 합계를 100만 원에서 90만 원으로 바꿔 주세요.'}]);assert.notEqual(next.reply,first.reply);results.push({input:'추가 질문에 상세 답변',...next});
// 임시 FAQ는 테스트 후 원문 그대로 복원하며, 도중 사용자 변경이 있으면 덮어쓰지 않는다.
const path=new URL('./faq.json',import.meta.url);const original=await readFile(path,'utf8');const entry={id:'test_only_office',question:'검증용 접수창구는 몇 시에 열리나요?',answer:'테스트 전용 답변: 오전 9시에 열립니다.'};const patched=JSON.stringify([...JSON.parse(original),entry],null,2);
try{await writeFile(path,patched);const d=await ask([{role:'user',content:entry.question}]);assert.equal(d.reply,entry.answer);results.push({input:entry.question,...d});}finally{if(await readFile(path,'utf8')===patched)await writeFile(path,original);else throw Error('검증 중 FAQ 변경 발견: 사용자 변경을 보존했습니다.');}
await writeFile(new URL('./verification-scenarios.json',import.meta.url),JSON.stringify(results,null,2));console.log('PASS: '+results.length+'개 — 단일·연속 질문, 요청 추가 질문, 이전 FAQ 오염 차단, 상세 답변, FAQ 무재시작 등록');
