import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const html=await readFile(new URL('./index.html',import.meta.url),'utf8');const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const elements=new Map();function el(){return {value:'',checked:true,disabled:false,textContent:'',children:[],setAttribute(){},append(...a){this.children.push(...a);},replaceChildren(){this.children=[];},scrollHeight:0,scrollTop:0};}
const get=id=>{if(!elements.has(id))elements.set(id,el());return elements.get(id);};
const sessions=[],utterances=[],requests=[];let responseFailure=false,startRespond=true,startTimeout=null;
class Recognition{constructor(){sessions.push(this);}start(){this.started=true;if(startRespond)this.onstart?.();}stop(){this.stopped=true;}abort(){this.aborted=true;this.onend?.();}}
const context=vm.createContext({console,setTimeout:(fn,ms)=>{if(ms===12000)startTimeout=fn;return setTimeout(fn,ms);},clearTimeout,AbortSignal,confirm:()=>true,window:{SpeechRecognition:Recognition,speechSynthesis:{speak:u=>utterances.push(u),cancel(){},},addEventListener(){}},document:{getElementById:get,createElement:el,createTextNode:x=>x},SpeechSynthesisUtterance:class{constructor(text){this.text=text;}},fetch:async(url,options)=>{if(url==='/api/health')return {json:async()=>({ready:true})};requests.push(JSON.parse(options.body));if(responseFailure)throw Error('테스트 연결 오류');return {ok:true,json:async()=>({reply:'언제까지 필요하신가요?',category:'정산·결제',summary:'정산서 수정 요청',request:'정산서 수정',deadline:'미확인',contact:'미확인',needs_callback:'미확인',missing:['기한']})};}});
context.speechSynthesis=context.window.speechSynthesis;vm.runInContext(script,context);
const tick=()=>new Promise(r=>setTimeout(r,10));const restart=()=>new Promise(r=>setTimeout(r,400));await tick();
get('mic').onclick();assert.equal(sessions.length,1);assert.equal(get('mic').disabled,false);
const first=sessions[0];first.onresult({results:[[{transcript:'정산서를 수정해 주세요'}]]});first.onspeechend();assert.equal(first.stopped,true);first.onend();first.onend();await tick();
assert.equal(requests.length,1,'중복 onend는 중복 전송하면 안 됨');assert.equal(utterances.length,1);assert.equal(sessions.length,1,'TTS 중 재청취 금지');
utterances[0].onend();await restart();assert.equal(sessions.length,2,'TTS 완료 후 자동 재청취');
get('mic').onclick();assert.equal(sessions[1].aborted,true);await restart();assert.equal(sessions.length,2,'중지 후 재시작 금지');
get('mic').onclick();const third=sessions.at(-1);third.onerror({error:'not-allowed'});assert.match(get('error').textContent,/권한/);assert.equal(get('mic').disabled,false,'권한 오류 후 다시 시도 가능');
get('mic').onclick();const fourth=sessions.at(-1);fourth.onresult({results:[[{transcript:'오늘까지 필요합니다'}]]});fourth.onend();await tick();get('mic').onclick();await restart();assert.equal(sessions.length,4,'답변 중 중지 시 재청취 금지');
const ending=get('finish').onclick();await tick();utterances.at(-1).onend();await ending;await tick();assert.equal(get('mic').disabled,false);assert.equal(get('mic').textContent,'🎙 새 음성 접수','종료 후 마이크 버튼으로 새 접수 가능');
get('mic').onclick();assert.equal(sessions.length,5);assert.equal(get('chat').children.length,1);
responseFailure=true;sessions.at(-1).onresult({results:[[{transcript:'새 요청입니다'}]]});sessions.at(-1).onend();await tick();assert.match(get('error').textContent,/테스트 연결 오류/);assert.equal(get('mic').textContent,'🎙 음성 대화 시작');
responseFailure=false;get('mic').onclick();const stopped=sessions.at(-1);stopped.onresult({results:[[{transcript:'중지 전에 인식된 요청'}]]});const count=requests.length;get('mic').onclick();await tick();assert.equal(requests.length,count+1,'중지 버튼도 인식된 내용을 기록해야 함');utterances.at(-1).onend();await tick();
startRespond=false;get('mic').onclick();startTimeout();assert.equal(get('mic').textContent,'🎙 음성 대화 시작');assert.match(get('error').textContent,/12초/);assert.match(get('status').textContent,/STT 시작 실패/);
console.log('PASS: 자동 전송, 중복 방지, TTS 대기, 재청취, 중지, 권한 오류, 종료 후 재시작, API 실패');
