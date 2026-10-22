$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
# Node.js는 사용자가 설치한 LTS 버전을 사용하며 자동으로 설치하거나 PATH를 바꾸지 않습니다.
if(-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js 22 이상을 설치한 후 다시 실행하세요: https://nodejs.org/' }
$taskNodeMajor=[int]((& node --version).TrimStart('v').Split('.')[0])
if($taskNodeMajor -lt 22) { throw 'Node.js 22 이상이 필요합니다.' }
& (Join-Path $PSScriptRoot 'setup.ps1')
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'runtime') -Force | Out-Null
# 기존 서비스가 있으면 재사용하고, 없으면 작업 폴더의 Ollama를 로컬 전용으로 시작합니다.
try { $null=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 } catch {
 $env:OLLAMA_HOST='127.0.0.1:11434'
 $env:OLLAMA_MODELS=Join-Path $PSScriptRoot 'runtime\models'
 $taskOllama=Start-Process -PassThru -FilePath (Join-Path $PSScriptRoot 'runtime\ollama\ollama.exe') -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'runtime\ollama-out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'runtime\ollama-error.log')
 $taskOllama.Id | Set-Content (Join-Path $PSScriptRoot 'runtime\ollama.pid')
 $taskReady=$false
 for($taskAttempt=0;$taskAttempt -lt 30;$taskAttempt++) { try { $null=Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2; $taskReady=$true; break } catch { Start-Sleep -Seconds 1 } }
 if(-not $taskReady) { throw '로컬 AI 서버를 시작하지 못했습니다.' }
}
# 무료 로컬 모델이 없을 때만 내려받습니다. 모델 파일이 runtime 폴더에 추가됩니다.
$taskTags=Invoke-RestMethod http://127.0.0.1:11434/api/tags
if(-not ($taskTags.models | Where-Object name -eq 'qwen3:1.7b')) {
 & (Join-Path $PSScriptRoot 'runtime\ollama\ollama.exe') pull qwen3:1.7b
 if($LASTEXITCODE -ne 0) { throw '모델 다운로드 실패' }
}
# 이미 실행 중인 앱을 재사용합니다. 새 서버는 로컬 주소에만 열립니다.
try { $null=Invoke-RestMethod http://127.0.0.1:8765/api/health -TimeoutSec 2 } catch {
 $taskApp=Start-Process -PassThru -FilePath 'node' -ArgumentList ('"'+(Join-Path $PSScriptRoot 'server.mjs')+'"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'runtime\app-out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'runtime\app-error.log')
 $taskApp.Id | Set-Content (Join-Path $PSScriptRoot 'runtime\app.pid')
 Start-Sleep -Seconds 2
}
$taskHealth=Invoke-RestMethod http://127.0.0.1:8765/api/health -TimeoutSec 5
if(-not $taskHealth.ready) { throw '앱 또는 모델이 준비되지 않았습니다.' }
Start-Process 'http://127.0.0.1:8765'
