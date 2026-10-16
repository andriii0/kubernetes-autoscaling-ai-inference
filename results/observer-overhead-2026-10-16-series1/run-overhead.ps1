param(
    [Parameter(Mandatory=$true)][string]$BaseUrl,
    [Parameter(Mandatory=$true)][string]$RunDirectory,
    [int]$Interval=5
)
$ErrorActionPreference='Stop'
if($Interval -le 0){throw 'Interval must be positive'}
New-Item -ItemType Directory -Path $RunDirectory -ErrorAction Stop | Out-Null
$taskOrder=@('off','on','on','off','on','off','off','on')
$taskRequest=@{
    model='qwen2.5:0.5b'; prompt='Explain what a container is in three short sentences.'
    stream=$false; keep_alive=-1
    options=@{num_predict=64; num_ctx=1024; num_thread=2; temperature=0; seed=42}
}
$taskFrozenObserver=(Get-FileHash -LiteralPath bench\observe.py -Algorithm SHA256).Hash
$taskFrozenLoad=(Get-FileHash -LiteralPath bench\inference.js -Algorithm SHA256).Hash
$taskManifest=@{
    schema_version=1; started_at_utc=[DateTime]::UtcNow.ToString('o'); order=$taskOrder
    rate=2; time_unit='10s'; duration='2m'; observer_interval_seconds=$Interval
    observer_sha256=$taskFrozenObserver; load_script_sha256=$taskFrozenLoad
    request=$taskRequest; base_url=$BaseUrl
    warmup_requests_per_run=3; warmup_pause_seconds=10; between_run_pause_seconds=20
    mean_budget_percent=10; p95_budget_percent=10; maximum_pair_mean_percent=20
    python_version=(& python --version); k6_version=(& k6 version); status='running'
    runs=@()
}
$taskManifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $RunDirectory 'manifest.json') -Encoding utf8

function Save-Snapshot([string]$Path){
    $taskRaw=(& kubectl --context ai-lab --request-timeout=5s -n inference get deployments,pods,services,hpa -o json) -join "`n"
    if($LASTEXITCODE -ne 0){throw 'Cannot read cluster snapshot'}
    $taskRaw | Set-Content -LiteralPath $Path -Encoding utf8
    $taskSnapshot=$taskRaw | ConvertFrom-Json
    $taskDeployments=@($taskSnapshot.items | Where-Object {$_.kind -eq 'Deployment' -and $_.metadata.name -eq 'ollama'})
    $taskPods=@($taskSnapshot.items | Where-Object {$_.kind -eq 'Pod' -and $_.metadata.labels.app -eq 'ollama'})
    $taskHpa=@($taskSnapshot.items | Where-Object {$_.kind -eq 'HorizontalPodAutoscaler'})
    if($taskDeployments.Count -ne 1 -or $taskDeployments[0].spec.replicas -ne 1 -or $taskDeployments[0].status.readyReplicas -ne 1 -or $taskPods.Count -ne 1 -or $taskPods[0].status.phase -ne 'Running' -or $taskHpa.Count -ne 0){throw 'Expected one ready replica and no HPA'}
    if(@($taskPods[0].status.containerStatuses | Where-Object {-not $_.ready}).Count){throw 'Model container is not ready'}
    return (@{
        uid=$taskPods[0].metadata.uid; restarts=$taskPods[0].status.containerStatuses.restartCount
        image=$taskPods[0].status.containerStatuses.imageID; generation=$taskDeployments[0].metadata.generation
        spec=$taskDeployments[0].spec
    } | ConvertTo-Json -Depth 15 -Compress)
}

$taskInitialSignature=$null
try {
    for($taskIndex=0;$taskIndex -lt $taskOrder.Count;$taskIndex++){
        $taskMode=$taskOrder[$taskIndex]
        $taskName=('{0:D2}-{1}' -f ($taskIndex+1),$taskMode)
        $taskRun=Join-Path $RunDirectory $taskName
        New-Item -ItemType Directory -Path $taskRun -ErrorAction Stop | Out-Null
        $taskBefore=Save-Snapshot (Join-Path $taskRun 'cluster-before.json')
        if($null -eq $taskInitialSignature){$taskInitialSignature=$taskBefore}
        if($taskBefore -ne $taskInitialSignature){throw 'Cluster configuration/identity changed'}
        if((Get-FileHash -LiteralPath bench\observe.py).Hash -ne $taskFrozenObserver -or (Get-FileHash -LiteralPath bench\inference.js).Hash -ne $taskFrozenLoad){throw 'Source changed during the series'}
        $taskObservers=@(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {$_.CommandLine -match 'observe\.py'})
        if($taskObservers.Count){throw 'An observer is already running; control interval would be contaminated'}
        $taskWarmups=@()
        for($taskWarmIndex=0;$taskWarmIndex -lt 3;$taskWarmIndex++){
            $taskResponse=Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/generate" -ContentType 'application/json' -Body ($taskRequest | ConvertTo-Json -Depth 5) -TimeoutSec 60
            if(-not $taskResponse.done -or [string]::IsNullOrWhiteSpace($taskResponse.response)){throw 'Invalid warmup response'}
            $taskWarmups += $taskResponse
        }
        $taskWarmups | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $taskRun 'warmup.json') -Encoding utf8
        $taskRecord=@{index=($taskIndex+1); pair=([Math]::Floor($taskIndex/2)+1); mode=$taskMode; directory=$taskName; observer_interval_seconds=$Interval}
        $taskObserver=$null
        if($taskMode -eq 'on'){
            $taskObserver=Start-Process -FilePath (Get-Command python).Source -ArgumentList @('.\bench\observe.py', "$taskRun\cluster.jsonl", '--duration', '150', '--interval', "$Interval") -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'observer-console.txt') -RedirectStandardError (Join-Path $taskRun 'observer-errors.txt')
            $taskRecord.observer_pid=$taskObserver.Id
            $taskRecord.observer_started_at_utc=[DateTime]::UtcNow.ToString('o')
        }
        Start-Sleep -Seconds 10
        if($null -ne $taskObserver -and $taskObserver.HasExited){throw 'Observer stopped before load'}
        $taskRecord.load_started_at_utc=[DateTime]::UtcNow.ToString('o')
        Write-Output ("START {0}/8 {1} at {2}" -f ($taskIndex+1),$taskMode,$taskRecord.load_started_at_utc)
        & k6 run --no-usage-report -e "BASE_URL=$BaseUrl" -e PROFILE=steady -e RATE=2 -e DURATION=2m -e SLO_MS= --out "json=$taskRun\requests.json" --summary-export "$taskRun\summary.json" .\bench\inference.js *> (Join-Path $taskRun 'console.txt')
        $taskRecord.load_exit_code=$LASTEXITCODE
        $taskRecord.load_finished_at_utc=[DateTime]::UtcNow.ToString('o')
        if($null -ne $taskObserver){
            if(-not $taskObserver.WaitForExit(60000)){throw 'Observer did not stop at its bounded duration'}
            $taskRecord.observer_exit_code=$taskObserver.ExitCode
            if($taskObserver.ExitCode -ne 0){throw 'Observer reported collection errors'}
        }
        $taskAfter=Save-Snapshot (Join-Path $taskRun 'cluster-after.json')
        $taskRecord.cluster_unchanged=($taskAfter -eq $taskInitialSignature)
        $taskRecord | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $taskRun 'metadata.json') -Encoding utf8
        $taskManifest.runs += $taskRecord
        $taskManifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $RunDirectory 'manifest.json') -Encoding utf8
        $taskSummary=Get-Content -LiteralPath (Join-Path $taskRun 'summary.json') -Raw | ConvertFrom-Json
        Write-Output ("DONE {0}/8 {1}: n={2}, mean={3:N1} ms, p95={4:N1} ms" -f ($taskIndex+1),$taskMode,$taskSummary.metrics.iterations.count,$taskSummary.metrics.successful_latency_ms.avg,$taskSummary.metrics.successful_latency_ms.'p(95)')
        if($taskRecord.load_exit_code -ne 0 -or -not $taskRecord.cluster_unchanged){throw 'Run validity check failed'}
        Start-Sleep -Seconds 20
    }
    $taskManifest.status='complete'
} catch {
    $taskManifest.status='failed'
    $taskManifest.failure=$_.Exception.Message
    throw
} finally {
    $taskManifest.finished_at_utc=[DateTime]::UtcNow.ToString('o')
    $taskManifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $RunDirectory 'manifest.json') -Encoding utf8
}
