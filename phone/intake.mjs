import {processIntake} from '../server.mjs';
let input='';for await(const chunk of process.stdin){input+=chunk;if(Buffer.byteLength(input)>65536)throw Error('입력이 너무 큽니다.');}
try{console.log(JSON.stringify(await processIntake(JSON.parse(input))));}catch(e){console.error('접수 처리 실패: '+e.message);process.exitCode=1;}
