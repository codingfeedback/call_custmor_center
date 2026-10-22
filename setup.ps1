$ErrorActionPreference='Stop'
# 저장소 안에만 공식 Ollama 실행 파일을 설치합니다. 기존 실행 파일이 있으면 재사용합니다.
$taskRuntime=Join-Path $PSScriptRoot 'runtime'
$taskExe=Join-Path $taskRuntime 'ollama\ollama.exe'
if(Test-Path -LiteralPath $taskExe) { return }
New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
$taskZip=Join-Path $taskRuntime 'ollama.zip'
Write-Host '공식 Ollama Windows 배포본을 다운로드합니다. 수 GB의 여유 공간과 인터넷이 필요합니다.'
# 공식 배포본만 내려받으며 runtime 안의 설치 파일만 생성·덮어씁니다.
Invoke-WebRequest 'https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip' -OutFile $taskZip
Expand-Archive -LiteralPath $taskZip -DestinationPath (Join-Path $taskRuntime 'ollama') -Force
if(-not (Test-Path -LiteralPath $taskExe)) { throw 'Ollama 설치 파일을 찾을 수 없습니다.' }
