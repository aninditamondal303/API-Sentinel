<#
Runs the analyzer's lint, type checks and full test suite inside a Linux container.
Needed on Windows with Smart App Control, which blocks the unsigned native Python
extensions (pydantic-core, PyYAML, Hypothesis) in a local virtual environment.

Run:  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\API-Sentinel\scripts\test-analyzer.ps1"
Output is also written to logs\analyzer-tests.txt.
#>
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Root "logs\analyzer-tests.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

# Reload PATH from the registry: a PowerShell window opened before Docker Desktop was
# installed does not see docker.exe yet.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
$dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path $dockerBin)) { $env:Path = "$dockerBin;$env:Path" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    "docker.exe was not found. Is Docker Desktop installed?" | Tee-Object -FilePath $Log
    exit 2
}

$server = (& docker version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
if (-not $server) {
    "Docker engine is not running. Start Docker Desktop and wait for 'Engine running'." | Tee-Object -FilePath $Log
    exit 2
}

Push-Location $Root
try {
    "== docker build (test image) $(Get-Date -Format o)" | Out-File $Log -Encoding utf8
    & docker build -f analyzer/Dockerfile --target test -t apisentinel-analyzer-test . 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-Object -Last 5
    if ($LASTEXITCODE -ne 0) { Write-Host "Image build failed; see $Log" -ForegroundColor Red; exit 1 }

    "`n== ruff + mypy" | Out-File $Log -Append -Encoding utf8
    & docker run --rm apisentinel-analyzer-test sh -c "python -m ruff check src tests && python -m ruff format --check src tests && python -m mypy" 2>&1 |
        Tee-Object -FilePath $Log -Append
    $lint = $LASTEXITCODE

    "`n== pytest" | Out-File $Log -Append -Encoding utf8
    & docker run --rm apisentinel-analyzer-test 2>&1 | Tee-Object -FilePath $Log -Append | Select-Object -Last 3
    $tests = $LASTEXITCODE

    "`n== runtime image" | Out-File $Log -Append -Encoding utf8
    & docker build -f analyzer/Dockerfile --target runtime -t apisentinel-analyzer . 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-Object -Last 2
    $runtime = $LASTEXITCODE

    "`n== exit codes: lint=$lint tests=$tests runtime-build=$runtime" | Tee-Object -FilePath $Log -Append
    if ($lint -ne 0 -or $tests -ne 0 -or $runtime -ne 0) { exit 1 }
} finally { Pop-Location }
