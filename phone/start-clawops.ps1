param([switch]$Live)
$ErrorActionPreference='Stop'
$taskEnv=Join-Path $PSScriptRoot '.env.clawops'
if(-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker Desktop Linux 엔진이 필요합니다.' }
# 최초 실행만 예제를 복사합니다. 기존 API 키·번호 설정은 덮어쓰지 않습니다.
if(-not (Test-Path -LiteralPath $taskEnv)) {
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot '.env.clawops.example') -Destination $taskEnv
}
$taskCompose=Join-Path $PSScriptRoot 'clawops.compose.yaml'
& docker compose --env-file $taskEnv -f $taskCompose build clawops
if($LASTEXITCODE -ne 0) { throw 'ClawOps 이미지 빌드 실패' }
if($Live) {
 # 번호 발급 후 .env.clawops의 CLAWOPS_LIVE=1까지 설정해야 실제 계정에 연결됩니다.
 & docker compose --env-file $taskEnv -f $taskCompose run --rm --no-deps clawops python -c "import os,sys;sys.path.insert(0,'/app/phone');from clawops_main import live_config;live_config(os.environ);print('실설정 형식 확인 완료')"
 if($LASTEXITCODE -ne 0) { throw '실계정 설정이 준비되지 않았습니다. .env.clawops를 확인하세요.' }
 & docker compose --env-file $taskEnv -f $taskCompose up -d clawops
} else {
 # 기본 실행은 loopback 모의 서버만 사용합니다. 전화번호·API 키가 필요 없으며 발신하지 않습니다.
 & docker compose --env-file $taskEnv -f $taskCompose run --rm --no-deps clawops python phone/check_clawops.py
}
if($LASTEXITCODE -ne 0) { throw 'ClawOps 실행 또는 모의 검증 실패' }
