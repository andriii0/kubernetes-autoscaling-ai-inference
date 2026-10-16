param([Parameter(Mandatory=$true)][string]$BaseUrl)
$ErrorActionPreference='Stop'
$taskRun='results\observation-check-2026-10-16-verified'
New-Item -ItemType Directory -Path $taskRun -ErrorAction Stop | Out-Null
& kubectl --context ai-lab --request-timeout=5s -n inference get deployments,pods,services,hpa -o json | Set-Content -LiteralPath (Join-Path $taskRun 'cluster-before.json') -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Cannot save initial cluster snapshot'}
$taskRequest=@{
    model='qwen2.5:0.5b'; prompt='Explain what a container is in three short sentences.'
    stream=$false; keep_alive=-1
    options=@{num_predict=64; num_ctx=1024; num_thread=2; temperature=0; seed=42}
}
$taskMetadata=@{
    purpose='Observer and resource-source verification, not capacity measurement'
    run_id='observation-check-2026-10-16-verified'; base_url=$BaseUrl
    created_at_utc=[DateTime]::UtcNow.ToString('o'); rate=2; time_unit='10s'; duration='1m'
    request=$taskRequest; warmup_included=$false; observer_interval_seconds=5
    observer_duration_seconds=150; idle_observation_seconds=60
    resource_source='kubelet /metrics/resource via Kubernetes node proxy'
    metrics_server_role='Scaling-signal observation only'
    observer_sha256=(Get-FileHash -LiteralPath bench\observe.py -Algorithm SHA256).Hash
    load_script_sha256=(Get-FileHash -LiteralPath bench\inference.js -Algorithm SHA256).Hash
    python_version=(& python --version); k6_version=(& k6 version)
    kubectl_version=((& kubectl version --client -o json) -join "`n" | ConvertFrom-Json)
}
$taskWarmup=Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/generate" -ContentType 'application/json' -Body ($taskRequest | ConvertTo-Json -Depth 5) -TimeoutSec 60
if(-not $taskWarmup.done -or [string]::IsNullOrWhiteSpace($taskWarmup.response)){throw 'Warmup response is invalid'}
$taskWarmup | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $taskRun 'warmup.json') -Encoding utf8
$taskMetadata.baseline_started_at_utc=[DateTime]::UtcNow.ToString('o')
& k6 run --no-usage-report -e "BASE_URL=$BaseUrl" -e RATE=2 -e DURATION=1m --out "json=$taskRun\baseline-requests.json" --summary-export "$taskRun\baseline-summary.json" .\bench\inference.js *> (Join-Path $taskRun 'baseline-console.txt')
$taskMetadata.baseline_exit_code=$LASTEXITCODE
$taskMetadata.baseline_finished_at_utc=[DateTime]::UtcNow.ToString('o')
if($LASTEXITCODE -ne 0){throw 'Baseline check failed; inspect the saved console output'}
$taskObserver=Start-Process -FilePath (Get-Command python).Source -ArgumentList @('.\bench\observe.py', "$taskRun\cluster.jsonl", '--duration', '150') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'observer-console.txt') -RedirectStandardError (Join-Path $taskRun 'observer-errors.txt')
$taskMetadata.observer_pid=$taskObserver.Id
$taskMetadata.observer_started_at_utc=[DateTime]::UtcNow.ToString('o')
Start-Sleep -Seconds 60
if($taskObserver.HasExited){throw 'Observer exited before the load check'}
$taskMetadata.load_started_at_utc=[DateTime]::UtcNow.ToString('o')
& k6 run --no-usage-report -e "BASE_URL=$BaseUrl" -e RATE=2 -e DURATION=1m --out "json=$taskRun\requests.json" --summary-export "$taskRun\summary.json" .\bench\inference.js *> (Join-Path $taskRun 'console.txt')
$taskMetadata.load_exit_code=$LASTEXITCODE
$taskMetadata.load_finished_at_utc=[DateTime]::UtcNow.ToString('o')
if(-not $taskObserver.WaitForExit(60000)){throw 'Observer did not stop at its bounded duration'}
$taskMetadata.observer_exit_code=$taskObserver.ExitCode
$taskMetadata.finished_at_utc=[DateTime]::UtcNow.ToString('o')
& kubectl --context ai-lab --request-timeout=5s -n inference get deployments,pods,services,hpa -o json | Set-Content -LiteralPath (Join-Path $taskRun 'cluster-after.json') -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Cannot save final cluster snapshot'}
$taskMetadata | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $taskRun 'metadata.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $taskRun 'observer-console.txt')
$taskMetadata | Select-Object baseline_exit_code,load_exit_code,observer_exit_code | ConvertTo-Json
if($taskMetadata.load_exit_code -ne 0 -or $taskMetadata.observer_exit_code -ne 0){exit 1}
