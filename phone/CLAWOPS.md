# ClawOps WebSocket + 로컬 AI

## 구성과 범위

고객 → ClawOps 070 → 공식 Python SDK의 제어·음성 WebSocket → Whisper small CPU → 기존 server.mjs FAQ·접수 → Pocket TTS Korean 100M → 고객.

이 경로는 자체 Session 구현을 ClawOpsAgent에 등록합니다. OpenAI·외부 STT/TTS 키, SIP 직접연결 옵션, 공인 SIP 포트, 로컬 Asterisk가 필요하지 않습니다. 음성·제어 연결은 PC에서 ClawOps로 나가는 연결입니다. 전화망과 ClawOps 자체 음성 전송까지 오프라인인 것은 아닙니다. PC·Docker·Ollama·인터넷은 통화 동안 켜져 있어야 합니다.

기존 SIP 서비스와 브라우저 버전은 변경하지 않습니다. 전화용 모델·FAQ·Node 접수 함수를 재사용합니다. 공식 SDK 0.69.0을 고정하고, SDK에 공개된 Session/CallSession 인터페이스만 사용합니다. VoiceML Stream 방식은 사용하지 않습니다. 공식 문서에 따르면 해당 방식의 통화는 같은 전환 API를 사용할 수 없습니다.

## 대화와 전환 규칙

- 등록 FAQ: 답변 후 다음 말을 기다립니다. 기한·연락처를 묻거나 자동 전환하지 않습니다.
- 업무 요청: 기존 로직으로 빠진 필수 정보를 하나씩 묻습니다. 정보가 모이면 실제 업무 처리가 필요하므로 담당자 연결 대상으로 판단합니다.
- 미등록 질문 또는 명시적인 담당자 연결 요청: 전환 대상으로 판단합니다.
- 접수만·기록만·나중에 회신 요청: 기록하고 연결하지 않습니다. 이 선호는 통화 중 유지되며 명시적으로 담당자 연결을 요청하면 해제됩니다.
- 전환은 HANDOFF_NUMBER 하나로만 합니다. 고객·모델이 말한 다른 번호는 사용하지 않습니다. 표시된 발신번호가 본인 대상 번호와 같으면 순환 발신을 막기 위해 기록만 남깁니다.
- 전환 전 고객에게 안내하고 warm 전환을 요청합니다. 담당자에게 요청 요지를 먼저 들려줍니다. 이 안내 음성은 ClawOps가 처리하므로 요금 조건을 확인하세요.
- 부재중·통화중·거절은 요청/발신번호를 보존하고 연결 실패를 안내한 뒤 종료합니다. 전환 결과가 불명확하면 unknown으로 남기며 재발신하지 않습니다.
- 통화당 전환은 최대 1회, 동시 수신 1개입니다. 자동 일반 발신·임의 번호 연결·문자 발송은 없습니다.
- 기존처럼 말이 끝난 뒤 처리하고 AI가 말하는 중에는 입력을 받지 않습니다. # 또는 '통화 종료'로 종료할 수 있습니다. AI 응대는 15턴·약 5분, 입력 무음 45초 제한입니다. 전환된 사람 간 통화에 이 5분 제한을 적용하지 않습니다.

현재 예제 FAQ에는 'PC 테스트/실제 연결 불가' 안내가 들어 있습니다. 번호 발급 후 실제 사용할 업무 FAQ로 수정해야 합니다. 존재하지 않는 영업시간·가격·업무 완료를 모델이 임의로 안내하도록 설정하지 마세요.

## 번호 없이 검증

저장소 루트의 PowerShell에서 실행합니다. Docker Desktop Linux 엔진이 필요합니다. 공식 SDK와 Python 표준 unittest를 사용합니다.

~~~powershell
# ClawOps 전용 이미지를 빌드하고 로컬 모의 통화를 검사합니다.
# 최초에만 phone/.env.clawops를 생성하며 기존 설정을 덮어쓰지 않습니다. 외부 전화망에 연결하지 않습니다.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\phone\start-clawops.ps1
# 입력 검증·FAQ·업무 추가 질문·전환·부재중·중단 보존을 검사합니다. --rm은 임시 검사 컨테이너만 제거합니다.
docker compose --env-file .\phone\.env.clawops -f .\phone\clawops.compose.yaml run --rm --no-deps clawops python phone/test_clawops.py
# 루트 시작.cmd로 Ollama를 켠 뒤 실제 Whisper·Ollama·Pocket 음성을 모의 WebSocket 경로로 검사합니다.
# 모델 최초 다운로드가 있을 수 있지만 실제 ClawOps 전화망/API는 사용하지 않습니다.
docker compose --env-file .\phone\.env.clawops -f .\phone\clawops.compose.yaml run --rm --no-deps clawops python phone/check_clawops.py --real-audio
~~~

모의 검증은 공식 SDK의 제어·음성 WebSocket을 127.0.0.1의 모의 서버에 연결합니다. 번호·API 키가 필요 없습니다. 모의 전환 성공은 실제 휴대폰 연결 성공이 아닙니다. 결과는 runtime/phone/clawops/mock-verification.json, 실제 로컬 음성 검사는 mock-verification-real-audio.json에 따로 저장합니다. 검증용 가짜 번호는 어떤 통신망에도 발신하지 않습니다.

## 번호 발급 후 설정

phone/.env.clawops를 수정합니다. 이 파일과 runtime은 Git/Docker 빌드에서 제외됩니다. 실키를 README·채팅·GitHub에 올리지 마세요.

| 항목 | 값/의미 |
|---|---|
| CLAWOPS_API_KEY | 계정 대시보드에서 발급한 API 키 |
| CLAWOPS_ACCOUNT_ID | 같은 계정의 Account ID |
| CLAWOPS_NUMBER | 해당 계정에서 발급받은 070 번호 |
| CLAWOPS_LIVE | 기본 0. 실제 수신 연결을 시작할 때 1 |
| HANDOFF_NUMBER | 전환받을 본인 010 휴대폰 번호. 하이픈/+82 입력 가능 |
| HANDOFF_ENABLED | 기본 0: 전환 예정 기록만. 실제 전환과 과금 조건 확인 후 1 |
| PHONE_OLLAMA_URL | Docker Desktop 기본 http://host.docker.internal:11434 |
| WHISPER_MODEL | 현재 small. 이번 작업에서는 변경하지 않음 |

### 먼저 확인할 서비스 조건

가입 전에 hello@claw-ops.com으로 아래를 문의할 수 있습니다. 문의를 자동 발송하지 않았습니다.

1. Individual에서 자체 Session + Agent Media WebSocket을 쓰며 로컬 STT/LLM/TTS만 사용해도 되는지, 별도 에이전트·스트리밍·SIP 옵션 요금이 있는지.
2. 동시통화 1개 플랜에서 수신 통화를 유지한 채 010으로 warm 전환 가능한지, 수신/발신 시간 차감·담당자 whisper 안내 비용이 어떻게 되는지.
3. 발급한 번호를 관리형 에이전트·VoiceML 대신 SDK 역방향 수신에 연결하는 계정별 설정·권한이 있는지.

### 실제 수신 순서

1. 대시보드에서 070을 발급하고 API 키/Account ID를 확인합니다. SDK 수신 경로를 사용합니다. 관리형 AI나 SIP 직접연결 옵션을 임의로 활성화하지 않습니다.
2. 우선 CLAWOPS_LIVE=1, HANDOFF_ENABLED=0으로 수신만 켭니다. 이 단계에서도 업체의 수신 요금이 발생할 수 있습니다.
3. 다른 휴대폰에서 070으로 걸어 FAQ 응답·업무 추가 질문·전사/요약·음성 재생을 확인합니다. 전환은 dry_run으로 기록되고 실제로 울리지 않습니다.
4. 요금·기능 조건을 확인한 뒤 HANDOFF_NUMBER와 HANDOFF_ENABLED=1을 설정하고 컨테이너를 재생성합니다.
5. 대상 휴대폰과 다른 번호에서 전환을 시험합니다. FAQ는 전환 안 함, 미등록 질문/정보가 모인 업무만 전환, 부재중 안내와 기록, 중단 시 기록 보존을 확인합니다.
6. 이 검증 전에는 기존 SKT 번호를 새 070으로 착신전환하지 않습니다. SKT 착신전환은 별도 상품/비용입니다.

~~~powershell
# .env.clawops에 실설정을 넣은 뒤 ClawOps 수신 서비스만 시작합니다. -Live와 CLAWOPS_LIVE=1이 모두 필요합니다.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\phone\start-clawops.ps1 -Live
# 연결 상태·오류를 확인합니다. API 키를 출력하는 config 명령은 사용하지 않습니다.
docker compose --env-file .\phone\.env.clawops -f .\phone\clawops.compose.yaml logs --tail 30 clawops
# 변경한 번호·전환 설정으로 재생성합니다. 진행 중 통화는 끊기므로 통화가 없을 때 실행하세요.
docker compose --env-file .\phone\.env.clawops -f .\phone\clawops.compose.yaml up -d --force-recreate clawops
# ClawOps 연결만 종료합니다. 진행 중 통화는 종료되며 모델·접수 기록은 삭제하지 않습니다.
docker compose --env-file .\phone\.env.clawops -f .\phone\clawops.compose.yaml down
~~~

## 기록과 한계

실제 통화의 전사·발신번호·요약·전환 사유/결과는 runtime/phone/clawops/calls/UUID.json에 원자적으로 저장합니다. 원음은 저장하지 않고 업체 녹음 옵션도 요청하지 않습니다. 번호 표시제한은 파일에도 원번호를 저장하지 않습니다. 발신번호는 네트워크 제시값으로 진위를 보증하지 않습니다. 통화 종료 시 원문을 보존하지만 전화망이 전사 전에 끊긴 음성은 복구할 수 없습니다. 보관·삭제는 사용자 책임입니다.

ClawOps 실제 서버·요금제·070·본인 휴대폰·실회선 재생 지연은 아직 미검증입니다. 공식 SDK의 고정 버전을 사용하므로 서버/SDK 변경 시 재검증이 필요합니다. 현재 출력은 20ms로 송신하고 고정 여유 시간을 둡니다. 실제 통화에서 재생 큐가 밀리면 수신을 너무 빨리 재개할 수 있으므로 mark 기반 재생 완료 연동을 검토해야 합니다.

공식 근거: [SDK](https://github.com/clawopshq/sdk-python), [음성 프로토콜](https://platform.claw-ops.com/docs/voiceml-stream-protocol), [전환과 부재중](https://platform.claw-ops.com/docs/call-transfers), [요금](https://claw-ops.com/pricing).

실제 합성 음성을 사용한 검사에서 FAQ가 전환 대상으로 처리된 사례가 1회 있었습니다. 상세 진단을 추가한 재검사에서는 FAQ 응답과 명시적 연결 요청이 통과했으나 최초 실패의 정확한 전사/분류 원인은 확정하지 못했습니다. 테스트 통과를 한국어 인식률 보장으로 해석하지 않습니다. 숫자·이름·실제 전화 음성의 추가 검증이 필요합니다.

고정 난수 실제 음성 검사에서 담당자 → 담반자 전사로 전환을 놓치는 문제가 재현됐습니다. 원문에 연결 명령이 있고 카테고리가 일반문의이며 AI 정규화 요청이 담당자 연결인 경우를 인식하도록 보강했습니다. 인터넷·서버 연결 같은 기술 요청과 명시적 연결 거절은 이 보강 경로에서 제외하며 회귀 검사합니다. STT 자체 모델은 변경하지 않았습니다.
