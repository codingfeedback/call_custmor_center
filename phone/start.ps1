$ErrorActionPreference='Stop'
$taskRepo=Split-Path $PSScriptRoot -Parent
$taskEnv=Join-Path $PSScriptRoot '.env'
if(-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop의 Linux 엔진이 필요합니다.' }
# 기존 설정을 덮어쓰지 않습니다. 최초 실행 때만 로컬 테스트 암호를 생성하고 Git 제외 파일에 저장합니다.
if(-not (Test-Path -LiteralPath $taskEnv)) {
 $taskBytes=New-Object byte[] 24
 $taskRandom=[System.Security.Cryptography.RandomNumberGenerator]::Create()
 $taskRandom.GetBytes($taskBytes)
 $taskRandom.Dispose()
 $taskPassword=([BitConverter]::ToString($taskBytes)).Replace('-','')
 $taskExample=[System.IO.File]::ReadAllText((Join-Path $PSScriptRoot '.env.example'))
 [System.IO.File]::WriteAllText($taskEnv,$taskExample.Replace('CHANGE_ME_TO_A_RANDOM_PASSWORD',$taskPassword))
}
New-Item -ItemType Directory -Path (Join-Path $taskRepo 'runtime\phone') -Force | Out-Null
$taskCompose=Join-Path $PSScriptRoot 'compose.yaml'
# 기존 웹 PoC의 Ollama와 모델을 재사용합니다. 호스트 설정을 외부 공개로 변경하지 않습니다.
try { $taskTags=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 3 } catch { throw '먼저 저장소 루트의 시작.cmd로 로컬 Ollama를 준비하세요.' }
if(-not ($taskTags.models | Where-Object name -eq 'qwen3:1.7b')) { throw '루트 시작.cmd로 qwen3:1.7b를 먼저 준비하세요.' }
# SIP는 기본값에서 127.0.0.1에만 열립니다. 음성 모델 최초 다운로드가 추가로 발생합니다.
& docker compose --env-file $taskEnv -f $taskCompose up -d --build phone
if($LASTEXITCODE -ne 0) { throw '전화 서버 시작 실패' }
Write-Host '시작 요청 완료. phone 문서의 logs 명령으로 AudioSocket ready와 Asterisk 준비 상태를 확인하세요.'
