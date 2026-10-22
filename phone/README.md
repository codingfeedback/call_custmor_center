# 실제 전화 수신 준비 — 번호 발급 전/후

## 구현 범위

070 → 통신사 SIP → Asterisk → AudioSocket PCM16 → faster-whisper → 기존 Node 접수 로직 → Pocket TTS Korean 100M → 전화 음성.

모든 AI 추론과 음성 처리는 로컬입니다. 전화망 요금은 별도입니다. 기본 STT는 multilingual Whisper small(CPU int8), TTS는 seastar105/pocket-tts-korean-100m, Pocket 패키지 4.0.1, CPU 4스레드입니다. 모델과 기본 Alba 음성 상태를 상주시키고 최근 16개 문장의 오디오를 캐시합니다. 합성 음성과 실제 전화의 인식 품질은 다릅니다. 동시 통화 1개, 최대 5분·15턴, 무음 45초에서 종료합니다. 상대가 #을 누르거나 "접수 종료"라고 말하면 종료합니다. 끼어들기와 담당자 전화 연결은 구현하지 않았습니다.

기존 웹 서버는 변경 없이 사용할 수 있습니다. 전화는 브라우저 STT·TTS를 사용하지 않고 별도 컨테이너에서 같은 server.mjs의 processIntake를 호출합니다. 전화용 컨테이너는 Docker Desktop의 host.docker.internal을 통해 기존 PC Ollama를 재사용합니다. 외부 공개 설정은 변경하지 않습니다. Linux 서버에서는 PHONE_OLLAMA_URL에 컨테이너에서 접근 가능한 사설 Ollama 주소를 지정해야 합니다. FAQ는 호스트 faq.json을 읽기 전용으로 연결해 즉시 반영합니다.

## 번호 없이 먼저 실행

Windows x64에서 Docker Desktop Linux 엔진이 실행 중이어야 합니다. 처음에는 이미지·Whisper 모델 다운로드가 발생하며 수 GB의 저장 공간과 인터넷이 필요합니다. 기본은 CPU이므로 GPU 가속 웹 버전보다 응답이 느릴 수 있습니다.

저장소 루트의 시작.cmd로 기존 Ollama를 먼저 실행한 뒤, 저장소 루트의 PowerShell에서 실행합니다.

~~~powershell
# 전화 서버를 시작합니다. 최초 실행만 phone/.env를 생성하며 기존 설정은 덮어쓰지 않습니다.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\phone\start.ps1
# 전화 전용 컨테이너의 시작·모델 다운로드 상태를 확인합니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml logs --tail 50 phone
# 음성 준비 후 Asterisk 모듈과 내선 설정을 확인합니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml exec phone asterisk -rx "core show application AudioSocket"
~~~

AudioSocket ready와 Asterisk 기동 후 SIP 소프트폰을 다음 값으로 등록합니다. 기본 포트는 호스트의 loopback에만 공개되므로 같은 PC에서 시험해야 합니다.

| 소프트폰 설정 | 값 |
|---|---|
| 서버/도메인 | 127.0.0.1:5060 |
| 전송 | UDP |
| 사용자·인증 ID | 1001 |
| 암호 | 로컬 phone/.env의 SIP_TEST_PASSWORD, 공개하지 마세요 |
| 코덱 | PCMU/PCMA(G.711) |
| 호출할 내선 | 1000 |

이 내선에 전화하면 안내 음성이 나오고 접수 대화를 시작합니다. 소프트폰은 별도 설치가 필요합니다. 소프트폰 호출은 유료 전화망을 사용하지 않습니다.

## 번호 발급 후 사용자 설정

가입 전에 통신사에 아래 항목을 확인하세요. 일반 인터넷전화·넘버플러스 번호만으로는 연결되지 않습니다.

| 항목 | 확인/입력할 값 |
|---|---|
| 070 번호 | 프로그램 SIP 주소로 수신을 전달할 수 있는 번호 |
| 목적지 SIP URI | sip:발급번호@수신서버공인IP:5060 |
| 실제 전달 DID 형식 | 070... 또는 +8270... 중 통신사가 보내는 정확한 형식 |
| SIP 발신 IP/CIDR | 통신사가 INVITE를 보내는 서버 목록, PROVIDER_CIDRS |
| RTP 미디어 IP/포트 | 방화벽 허용 범위 확인, SIP IP와 다를 수 있음 |
| 인증 방식 | 이 PoC는 발신 IP 허용 목록 방식. REGISTER/아이디·암호 인증이 필요한 상품은 추가 작업 필요 |
| 코덱·전송 | G.711 PCMU/PCMA, UDP SIP 지원 확인 |
| 발신번호 전달 | CALLERID(num)에 원 발신번호가 전달되는지 확인. 통신망 값도 진위 보증으로 사용하지 않음 |

기존 PC의 Ollama는 저장소 루트 시작.cmd로 먼저 실행해 두세요.

phone/.env에서 INBOUND_DID와 PROVIDER_CIDRS를 입력합니다. 외부 연결에는 PUBLIC_IP를 입력하고 SIP_BIND_IP를 0.0.0.0으로 바꿔야 합니다. 이 변경은 실제 SIP 포트를 외부에 열기 위한 설정이므로 번호 발급 후 수신 서버에서만 적용하세요. 기본값은 외부 전화망 연결을 허용하지 않습니다.

공유기/NAT와 호스트 방화벽에서 UDP 5060 및 UDP 18000–18020을 수신 서버로 연결해야 합니다. SIP는 통신사 IP만, RTP는 통신사가 안내한 미디어 IP만 허용하세요. CGNAT·공인 IP 부재 또는 회사 방화벽 제한이 있으면 공인 IP가 있는 별도 서버가 필요합니다. HTTP 터널만으로 SIP/RTP는 전달되지 않습니다. 이 작업은 자동으로 수행하지 않았습니다. 외부 서버로 이동할 때는 보안을 유지하며 저장소를 복제하고 그 서버에서 모델을 준비하세요.

~~~powershell
# 수정한 번호·IP 설정으로 전화 컨테이너만 재생성합니다. 진행 중인 전화는 끊깁니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml up -d --force-recreate phone
~~~

그 후 SKT 착신전환 없이 휴대폰에서 새 070으로 직접 전화해 검증합니다. 수신→한국어 STT→FAQ/추가 질문→한국어 TTS→발신번호·접수 기록을 순서대로 확인하세요. 안정화 전에는 기존 010을 넘기지 마세요.

## 기록·오류·종료

통화별 발신번호·대화·최신 요약은 runtime/phone/calls/UUID.json에 저장합니다. 원음은 저장하지 않습니다. 발신번호는 네트워크가 제시한 값이며 caller_id_verified=false입니다. 숨김 번호는 미확인으로 처리합니다. 통화 중 끊기거나 AI 오류가 발생해도 이미 받은 텍스트를 유지합니다. 로컬 파일의 보관·삭제는 사용자가 관리하며 Git에서는 제외됩니다. 안내 후 녹취 동의 등 실제 운영 정책은 별도로 정해야 합니다.

~~~powershell
# 전화 전용 컨테이너를 중지합니다. 진행 중 통화는 종료됩니다. 모델·기록 볼륨은 삭제하지 않습니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml down
~~~

## 검증 명령

~~~powershell
# 컨테이너 안에서 음성 프로토콜·VAD·잘못된 SIP 설정 차단을 검사합니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml run --rm --no-deps phone python phone/test_phone.py
# 실제 로컬 한국어 TTS를 생성하고 Whisper로 전사합니다. 다운로드/추론이 발생하며 실전화 품질 검증은 아닙니다.
docker compose --env-file .\phone\.env -f .\phone\compose.yaml run --rm --no-deps phone python phone/check_voice.py
~~~

AudioSocket TCP 9092는 컨테이너 내부에서만 사용하며, 기존 Ollama의 외부 공개 설정은 변경하지 않습니다. Asterisk 관리자 API·외부 발신은 비활성입니다. 통신사 SIP/RTP 연결과 실제 음성·NAT 품질은 번호 발급 후 검증해야 합니다.

참고: [Asterisk AudioSocket](https://docs.asterisk.org/Configuration/Channel-Drivers/AudioSocket/), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Pocket TTS Korean 100M 모델·라이선스](https://huggingface.co/seastar105/pocket-tts-korean-100m).

검증 스크립트 phone/check_sip.py는 로컬 SIP 인증과 RTP 안내 음성을, phone/check_audiosocket.py는 실제 PCM → STT → 접수 → TTS를 검사합니다. 실행 중 컨테이너에서 각각 python phone/스크립트명으로 실행합니다. 합성 한국어 전사만으로 사람의 실제 발화 인식률을 판단할 수 없으므로, 현재 음성 품질은 실사용 승인 수준으로 검증하지 않았습니다.

## Pocket TTS 교체 및 청취

모델 가중치는 seastar105의 한국어 파생 모델(CC BY 4.0)이며 Kyutai Pocket-TTS에 기반합니다. 한국어 설정과 가중치 revision을 고정했습니다. 음성 프롬프트는 Kyutai가 제공한 Alba casual.wav를 사용하며, 기존 골프존 모델·개인 음성 자산은 가져오지 않습니다. 모델 다운로드와 패키지 설치는 최초 한 번 필요하며 통화 중 텍스트는 로컬에서 합성합니다. 기본 음성 파일은 첫 로드에 내려받아 캐시합니다.

현재 구현은 문장 전체를 합성한 뒤 8kHz PCM16으로 변환해 전화에 재생합니다. 실시간 청크 재생은 아직 구현하지 않았습니다. CPU 4스레드 예비 측정에서 약 5.4–5.8초 음성을 약 2.5–3.7초에 생성했으며 첫 로드와 STT·LLM 시간은 제외한 수치입니다. 장문·숫자·영문·이름은 별도 검증해야 합니다.

phone/check_voice.py는 runtime/phone/samples에 24kHz 원본과 전화용 8kHz WAV를 저장하고 runtime/phone/voice-check.json에 실제 합성·전사 시간을 기록합니다. 최종 자연스러움은 직접 청취해 평가하세요. 웹 브라우저의 TTS는 변경하지 않았으며 Pocket은 SIP 전화 경로에 적용됩니다.
