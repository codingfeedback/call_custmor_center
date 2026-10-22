$ErrorActionPreference='Stop'
# 이 작업 폴더의 PID와 실행 명령이 일치하는 프로세스만 종료합니다. 기존 외부 Ollama는 건드리지 않습니다.
foreach($taskService in @('app','ollama')) {
 $taskPidFile=Join-Path $PSScriptRoot "runtime\$taskService.pid"
 if(Test-Path -LiteralPath $taskPidFile) {
  $taskProcessId=[int](Get-Content -LiteralPath $taskPidFile)
  $taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$taskProcessId"
  $taskOwned=$false
  if($taskProcess -and $taskService -eq 'ollama') { $taskOwned=$taskProcess.ExecutablePath -eq (Join-Path $PSScriptRoot 'runtime\ollama\ollama.exe') }
  if($taskProcess -and $taskService -eq 'app') { $taskOwned=$taskProcess.CommandLine -like '*server.mjs*' -and $taskProcess.CommandLine -like "*$PSScriptRoot*" }
  if($taskOwned) { Stop-Process -Id $taskProcessId }
 }
}
