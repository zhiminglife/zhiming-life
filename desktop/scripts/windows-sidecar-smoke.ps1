param(
    [Parameter(Mandatory = $true)]
    [string]$Binary,
    [Parameter(Mandatory = $true)]
    [string]$ResourceDir
)

$ErrorActionPreference = "Stop"
$port = 18767
$token = "windows-sidecar-smoke"
$dataDir = Join-Path $env:RUNNER_TEMP "zhiming-life-sidecar-smoke"
$parent = $null
$sidecar = $null

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

try {
    $parent = Start-Process powershell.exe -ArgumentList "-NoProfile", "-Command", "Start-Sleep -Seconds 300" -PassThru -WindowStyle Hidden
    $env:ZHIMING_LIFE_API_PORT = "$port"
    $env:ZHIMING_LIFE_API_TOKEN = $token
    $env:ZHIMING_LIFE_DATA_DIR = $dataDir
    $env:ZHIMING_LIFE_RESOURCE_DIR = $ResourceDir
    $env:ZHIMING_LIFE_PARENT_PID = "$($parent.Id)"
    $sidecar = Start-Process $Binary -PassThru -WindowStyle Hidden

    $health = $null
    foreach ($attempt in 1..60) {
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$port/api/health" -TimeoutSec 2
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($null -eq $health -or $health.status -ne "ok") {
        throw "Frozen sidecar did not become healthy"
    }

    $headers = @{ "X-Zhiming-Token" = $token }
    $libraries = Invoke-RestMethod "http://127.0.0.1:$port/api/libraries" -Headers $headers
    if (@($libraries).Count -ne 2) {
        throw "Expected two physical RAG libraries, got $(@($libraries).Count)"
    }
    foreach ($kind in @("knowledge", "cases")) {
        $library = $libraries | Where-Object { $_.kind -eq $kind }
        if ($null -eq $library -or $library.vector_backend -ne "sqlite-vec" -or $library.source_count -lt 1) {
            throw "$kind library is not ready with sqlite-vec and bundled sources"
        }
        $hits = Invoke-RestMethod "http://127.0.0.1:$port/api/libraries/$kind/search?q=%E4%BA%8B%E4%B8%9A&limit=2" -Headers $headers -TimeoutSec 120
        if (@($hits).Count -lt 1) {
            throw "$kind library returned no offline search results"
        }
    }

    $corsHeaders = @{
        Origin = "tauri://localhost"
        "Access-Control-Request-Method" = "GET"
        "Access-Control-Request-Headers" = "x-zhiming-token"
    }
    $cors = Invoke-WebRequest "http://127.0.0.1:$port/api/libraries" -Method Options -Headers $corsHeaders
    if ($cors.StatusCode -ne 200 -or $cors.Headers["Access-Control-Allow-Origin"] -ne "tauri://localhost") {
        throw "Packaged sidecar CORS preflight failed"
    }

    Stop-Process -Id $parent.Id
    $parent = $null
    foreach ($attempt in 1..15) {
        $sidecar.Refresh()
        if ($sidecar.HasExited) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $sidecar.HasExited) {
        throw "Sidecar remained alive after its parent exited"
    }
} finally {
    if ($null -ne $parent -and -not $parent.HasExited) {
        Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $sidecar) {
        $sidecar.Refresh()
        if (-not $sidecar.HasExited) {
            & taskkill.exe /PID $sidecar.Id /T /F | Out-Null
        }
    }
}
