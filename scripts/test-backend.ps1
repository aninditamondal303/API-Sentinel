<#
Compiles the Spring Boot backend and runs its unit and integration tests.

Maven runs inside an eclipse-temurin:21-jdk container (plus unzip; see backend/Dockerfile) so the build is the same on every machine.
Integration tests use Testcontainers through Docker Desktop's socket to start a real PostgreSQL 18
container and the real analyzer image, which this script builds first.

Run:  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\API-Sentinel\scripts\test-backend.ps1"
Output: logs\backend-tests.txt and backend\target\surefire-reports\
#>
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Root "logs\backend-tests.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

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
    "== analyzer runtime image $(Get-Date -Format o)" | Out-File $Log -Encoding utf8
    & docker build -f analyzer/Dockerfile --target runtime -t apisentinel-analyzer:latest . 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { Write-Host "Analyzer image build failed; see $Log" -ForegroundColor Red; exit 1 }

    "`n== backend toolchain image (eclipse-temurin:21-jdk + unzip)" | Out-File $Log -Append -Encoding utf8
    & docker build -f backend/Dockerfile --target toolchain -t apisentinel-backend-toolchain backend 2>&1 |
        Tee-Object -FilePath $Log -Append | Select-Object -Last 2
    if ($LASTEXITCODE -ne 0) { Write-Host "Toolchain image build failed; see $Log" -ForegroundColor Red; exit 1 }

    $repo = (Resolve-Path $Root).Path
    "`n== Maven distribution checksum verification" | Tee-Object -FilePath $Log -Append
    & docker run --rm -v "${repo}:/workspace" -v "apisentinel-m2:/root/.m2" apisentinel-backend-toolchain `
        sh /workspace/scripts/verify-maven-dist.sh 2>&1 | Tee-Object -FilePath $Log -Append
    if ($LASTEXITCODE -ne 0) { Write-Host "Maven distribution verification failed; see $Log" -ForegroundColor Red; exit 1 }

    "`n== mvnw verify" | Out-File $Log -Append -Encoding utf8
    Write-Host "Running the backend build and tests. The first run downloads Maven dependencies (a few minutes)."
    & docker run --rm `
        -v "${repo}:/workspace" `
        -v "apisentinel-m2:/root/.m2" `
        -v "//var/run/docker.sock:/var/run/docker.sock" `
        -e "TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal" `
        -w /workspace/backend `
        apisentinel-backend-toolchain `
        sh ./mvnw -B -ntp verify 2>&1 | Tee-Object -FilePath $Log -Append | Select-String -Pattern "Tests run:|BUILD|ERROR|FAIL" | Select-Object -Last 40
    $mvn = $LASTEXITCODE

    "`n== exit code: maven=$mvn" | Tee-Object -FilePath $Log -Append
    if ($mvn -ne 0) { exit 1 }
} finally { Pop-Location }
