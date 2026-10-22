import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const cases=[{label:'정산',text:'지난달 정산서 금액이 잘못됐어요. 수정한 정산서를 오늘 오후 5시까지 보내 주세요. 처리 후에는 다시 연락해 주세요.',category:'정산·결제',deadline:'오늘 오후 5시까지'}, {label:'장애',text:'로그인하면 오류가 나서 접속이 안 됩니다. 내일 오전까지 해결 방법을 알려주시고 전화로 회신해 주세요.',category:'기술·장애',deadline:'내일 오전'}];
const results=[];
for(const c of cases){const start=Date.now();const r=await fetch('http://127.0.0.1:8765/api/intake',{method:'POST',headers:{'Content-Type':'application/json','X-Intake-Client':'local'},body:JSON.stringify({messages:[{role:'user',content:c.text}],finish:true})});const d=await r.json();assert.equal(r.status,200,JSON.stringify(d));assert.equal(d.category,c.category);assert.equal(d.needs_callback,'필요');assert.notEqual(d.summary,'미확인');assert.equal(d.deadline.replace(/까지$/,''),c.deadline.replace(/까지$/,''));assert.equal(d.contact,'발신번호 미연동 (PC 테스트)');assert.match(d.reply,/업무 처리는 하지 않았습니다/);results.push({case:c.label,milliseconds:Date.now()-start,result:d});}
await writeFile(new URL('./verification.json',import.meta.url),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
