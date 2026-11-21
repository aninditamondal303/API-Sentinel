<#
Type-checks and tests the React frontend, then builds the production image, all inside Docker
(Node tooling uses native binaries that Smart App Control blocks on Windows).

Run:  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\API-Sentinel\scripts\test-frontend.ps1"
Output: logs\frontend-tests.txt
#>
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Root "logs\frontend-tests.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
$dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path $dockerBin)) { $env:Path = "$dockerBin;$env:Path" }
if (-not (& docker version --format "{{.Server.Version}}" 2>$null)) { "Docker engine is not running." | Tee-Object -FilePath $Log; exit 2 }

Push-Location (Join-Path $Root "frontend")
try {
    "== typecheck + tests (docker build --target test) $(Get-Date -Format o)" | Out-File $Log -Encoding utf8
    & docker build --progress=plain --no-cache-filter test --target test -t apisentinel-frontend-test . 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-String -Pattern "Test Files|Tests |error TS|FAIL|ERROR" | Select-Object -Last 20
    $tests = $LASTEXITCODE
    "`n== production image" | Out-File $Log -Append -Encoding utf8
    & docker build --progress=plain --target runtime -t apisentinel-frontend:latest . 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-Object -Last 3
    $image = $LASTEXITCODE
    "`n== exit codes: tests=$tests image=$image" | Tee-Object -FilePath $Log -Append
    if ($tests -ne 0 -or $image -ne 0) { exit 1 }
} finally { Pop-Location }
