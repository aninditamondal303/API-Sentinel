<#
API Sentinel - Windows development environment setup.

Safe to re-run: every step checks what is already present and skips it.
Installs only from official sources (winget community repository entries
published by the vendors, and Maven Central for the Maven Wrapper).
Never uninstalls or modifies existing Python installations.

Run (normal, non-admin PowerShell):
  powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\Documents\API-Sentinel\scripts\setup-dev.ps1"

Windows will show UAC prompts for the JDK and Docker Desktop installers (and WSL if
missing). Approve them. A restart may be required after WSL/Docker installation;
the script tells you if so - just run it again afterwards.
#>
param([switch]$SkipDocker)

# Continue: native tools (java, uv, winget) write normal output to stderr, which
# Windows PowerShell 5.1 would otherwise turn into terminating errors. Failures are checked explicitly.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$Transcript = Join-Path $Logs "setup.txt"
Start-Transcript -Path $Transcript -Force | Out-Null

$MavenVersion = "3.9.16"
$WrapperVersion = "3.3.4"
$Central = "https://repo.maven.apache.org/maven2"
$Results = [ordered]@{}
$ActionsForUser = New-Object System.Collections.Generic.List[string]
$WslRestartPending = $false

function Step([string]$text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok([string]$key, [string]$text) { $Results[$key] = "OK      $text"; Write-Host "    OK: $text" -ForegroundColor Green }
function Todo([string]$key, [string]$text) { $Results[$key] = "PENDING $text"; Write-Host "    PENDING: $text" -ForegroundColor Yellow }
function Fail([string]$key, [string]$text) { $Results[$key] = "FAILED  $text"; Write-Host "    FAILED: $text" -ForegroundColor Red }

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
    $jh = [Environment]::GetEnvironmentVariable("JAVA_HOME", "User")
    if (-not $jh) { $jh = [Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine") }
    if ($jh) { $env:JAVA_HOME = $jh }
}

function Test-WingetInstalled([string]$id) {
    $out = winget list --id $id --exact --accept-source-agreements 2>$null | Out-String
    return ($LASTEXITCODE -eq 0 -and $out -match [regex]::Escape($id))
}

function Install-Winget([string]$id) {
    if (Test-WingetInstalled $id) { Write-Host "    $id is already installed."; return $true }
    Write-Host "    Installing $id with winget (approve the Windows prompt if one appears)..."
    # Out-Host keeps winget output out of the function's return value.
    winget install --id $id --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Host
    # 0 = success; -1978335189 = already installed / no applicable upgrade
    if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) { return $true }
    Write-Host "    winget exited with code $LASTEXITCODE" -ForegroundColor Red
    return $false
}

function Get-Text([string]$url) {
    $content = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 60 -ErrorAction Stop).Content
    if ($content -is [byte[]]) { $content = [System.Text.Encoding]::ASCII.GetString($content) }
    return $content
}

# ---------------------------------------------------------------- system facts
Step "System"
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem
Write-Host ("    {0} (build {1}), RAM {2:N1} GB" -f $os.Caption, $os.BuildNumber, ($cs.TotalPhysicalMemory / 1GB))
Write-Host ("    Virtualization enabled in firmware: {0}; hypervisor present: {1}" -f $cpu.VirtualizationFirmwareEnabled, $cs.HypervisorPresent)

# ---------------------------------------------------------------------- JDK 21
Step "JDK 21 (Eclipse Temurin)"
if (Install-Winget "EclipseAdoptium.Temurin.21.JDK") {
    $base = Join-Path $env:ProgramFiles "Eclipse Adoptium"
    $jdk = Get-ChildItem -Path $base -Directory -Filter "jdk-21*" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $jdk) {
        Fail "jdk" "Temurin 21 not found under $base after installation."
    } else {
        $current = [Environment]::GetEnvironmentVariable("JAVA_HOME", "User")
        if ($current -ne $jdk.FullName) {
            if ($current) { Write-Host "    Replacing user JAVA_HOME (was: $current)" }
            [Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk.FullName, "User")
        }
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if (-not $userPath) { $userPath = "" }
        if ($userPath -notmatch [regex]::Escape("%JAVA_HOME%\bin") -and $userPath -notmatch [regex]::Escape("$($jdk.FullName)\bin")) {
            # Prepend so this JDK wins over other Java installations for this user.
            [Environment]::SetEnvironmentVariable("Path", "$($jdk.FullName)\bin;$userPath", "User")
        }
        Refresh-Path
        $env:Path = "$($jdk.FullName)\bin;$env:Path"
        $javaVersion = (& "$($jdk.FullName)\bin\java.exe" -version 2>&1 | Select-Object -First 1).ToString()
        $javacVersion = (& "$($jdk.FullName)\bin\javac.exe" -version 2>&1 | Select-Object -First 1).ToString()
        if ($javaVersion -match '"21\.' -and $javacVersion -match "javac 21\.") {
            Ok "jdk" "$javaVersion / $javacVersion / JAVA_HOME=$($jdk.FullName)"
        } else {
            Fail "jdk" "Unexpected versions: $javaVersion / $javacVersion"
        }
    }
} else {
    Fail "jdk" "winget could not install EclipseAdoptium.Temurin.21.JDK"
}

# ------------------------------------------------------------- Maven Wrapper
Step "Maven Wrapper (backend\mvnw.cmd, Maven $MavenVersion) - no global Maven needed"
$Backend = Join-Path $Root "backend"
$WrapperDir = Join-Path $Backend ".mvn\wrapper"
New-Item -ItemType Directory -Force -Path $WrapperDir | Out-Null
try {
    if (-not (Test-Path (Join-Path $Backend "mvnw.cmd"))) {
        $zipName = "maven-wrapper-distribution-$WrapperVersion-only-script.zip"
        $zipUrl = "$Central/org/apache/maven/wrapper/maven-wrapper-distribution/$WrapperVersion/$zipName"
        $zip = Join-Path $env:TEMP $zipName
        Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing -TimeoutSec 120 -ErrorAction Stop
        $expected = (Get-Text "$zipUrl.sha1").Trim().Split(" ")[0].ToLower()
        $actual = (Get-FileHash -Algorithm SHA1 $zip).Hash.ToLower()
        if ($expected -ne $actual) { throw "Checksum mismatch for $zipName" }
        $tmp = Join-Path $env:TEMP "mvnw-$WrapperVersion"
        if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
        Expand-Archive -Path $zip -DestinationPath $tmp -ErrorAction Stop
        foreach ($f in @("mvnw", "mvnw.cmd")) {
            $src = Get-ChildItem -Path $tmp -Recurse -File -Filter $f | Select-Object -First 1
            if (-not $src) { throw "$f missing from $zipName" }
            Copy-Item $src.FullName (Join-Path $Backend $f) -ErrorAction Stop
        }
        Write-Host "    Wrapper scripts $WrapperVersion installed (SHA-1 verified against Maven Central)."
    } else {
        Write-Host "    backend\mvnw.cmd already present; not overwritten."
    }

    $props = Join-Path $WrapperDir "maven-wrapper.properties"
    if (-not (Test-Path $props)) {
        $distUrl = "$Central/org/apache/maven/apache-maven/$MavenVersion/apache-maven-$MavenVersion-bin.zip"
        $dist = Join-Path $env:TEMP "apache-maven-$MavenVersion-bin.zip"
        Invoke-WebRequest -Uri $distUrl -OutFile $dist -UseBasicParsing -TimeoutSec 300 -ErrorAction Stop
        try {
            $published = (Get-Text "$distUrl.sha512").Trim().Split(" ")[0].ToLower(); $algo = "SHA512"
        } catch {
            $published = (Get-Text "$distUrl.sha1").Trim().Split(" ")[0].ToLower(); $algo = "SHA1"
        }
        if ((Get-FileHash -Algorithm $algo $dist).Hash.ToLower() -ne $published) { throw "Checksum mismatch for Maven $MavenVersion" }
        Write-Host "    Maven $MavenVersion distribution verified ($algo from Maven Central)."
        $sha256 = (Get-FileHash -Algorithm SHA256 $dist).Hash.ToLower()
        @(
            "# Maven Wrapper: pins the Maven version used to build the backend.",
            "wrapperVersion=$WrapperVersion",
            "distributionType=only-script",
            "distributionUrl=$distUrl",
            "# SHA-256 of the distribution, computed after verifying Maven Central's published checksum.",
            "distributionSha256Sum=$sha256"
        ) | Set-Content -Path $props -Encoding ascii
        Write-Host "    maven-wrapper.properties written (Maven $MavenVersion, checksum pinned)."
    } else {
        Write-Host "    maven-wrapper.properties already present; not overwritten."
    }

    if ($env:JAVA_HOME) {
        Push-Location $Backend
        $mvnOut = (& .\mvnw.cmd -v 2>&1 | Out-String)
        Pop-Location
        if ($mvnOut -match "Apache Maven $([regex]::Escape($MavenVersion))") {
            Ok "maven" ("Maven Wrapper works: " + (($mvnOut -split "`n")[0].Trim()))
        } else {
            Fail "maven" "mvnw.cmd -v did not report Maven $MavenVersion. Output: $mvnOut"
        }
    } else {
        Todo "maven" "Wrapper installed; verification needs JAVA_HOME (JDK step)."
    }
} catch {
    Fail "maven" "Maven Wrapper setup failed: $($_.Exception.Message)"
}

# ---------------------------------------------------------------------- uv
Step "uv (Python project manager)"
Refresh-Path
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (Install-Winget "astral-sh.uv") { Refresh-Path }
}
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) {
    $uvVersion = (& uv --version 2>&1 | Out-String).Trim()
    Ok "uv" $uvVersion
} else {
    Fail "uv" "uv is not on PATH after installation. Open a new PowerShell window and re-run this script."
}

# ------------------------------------------------- analyzer verification
# Runs after Docker (see the end of the script): on Windows with Smart App Control,
# native Python extensions in a local venv are blocked, so the suite runs in a container.
function Test-Analyzer {
    Step "Analyzer: full test suite"
    $nativeOk = $false
    if ($uvCmd) {
        Push-Location (Join-Path $Root "analyzer")
        try {
            & uv sync --python 3.14 --locked 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "    $_" }
            # Decide by exit code: on failure PowerShell's error text echoes this command line,
            # so matching the printed output would give a false positive.
            $probe = (& uv run python -c "import pydantic_core, yaml, hypothesis" 2>&1 | Out-String)
            $nativeOk = ($LASTEXITCODE -eq 0)
            if (-not $nativeOk -and $probe -match "Application Control") {
                Write-Host "    Windows Smart App Control blocks native Python extensions in the local venv; using Docker instead."
            }
        } finally { Pop-Location }
    }
    if ($nativeOk) {
        Push-Location (Join-Path $Root "analyzer")
        try {
            $testLog = Join-Path $Logs "analyzer-tests.txt"
            & uv run python -m pytest -q -p no:cacheprovider 2>&1 | Out-File -FilePath $testLog -Encoding utf8
            $summary = (Get-Content $testLog | Select-Object -Last 1)
            if ($LASTEXITCODE -eq 0) { Ok "analyzer" "native: $summary" } else { Fail "analyzer" "native: $summary (logs\analyzer-tests.txt)" }
        } finally { Pop-Location }
        return
    }
    $server = (& docker version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
    if (-not $server) { Todo "analyzer" "Runs in Docker; waiting for the Docker engine."; return }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "test-analyzer.ps1") | Out-Host
    $summary = (Get-Content (Join-Path $Logs "analyzer-tests.txt") | Where-Object { $_ -match "passed|failed|error" } | Select-Object -Last 1)
    if ($LASTEXITCODE -eq 0) { Ok "analyzer" "in Docker: $summary" } else { Fail "analyzer" "in Docker: $summary (logs\analyzer-tests.txt)" }
}

# ---------------------------------------------------- WSL 2 + Docker Desktop
if ($SkipDocker) {
    Todo "wsl" "Skipped (-SkipDocker)."; Todo "docker" "Skipped (-SkipDocker)."
} else {
    Step "WSL 2 (required by Docker Desktop: WSL 2.1.5 or later)"
    $wslRaw = (& wsl.exe --version 2>&1 | Out-String) -replace "`0", ""
    $wslMatch = [regex]::Match($wslRaw, "WSL[^:\r\n]*:\s*([0-9]+(\.[0-9]+)+)")
    if ($LASTEXITCODE -eq 0 -and $wslMatch.Success) {
        $wslVersion = [version]$wslMatch.Groups[1].Value
        if ($wslVersion -ge [version]"2.1.5") { Ok "wsl" "WSL $wslVersion" }
        else {
            Write-Host "    WSL $wslVersion is older than 2.1.5; updating (approve the prompt)..."
            & wsl.exe --update
            Todo "wsl" "WSL updated from $wslVersion; re-run this script to verify."
        }
    } else {
        Write-Host "    WSL is not installed. Installing the WSL platform (no Linux distribution needed; approve the prompt)..."
        Start-Process -FilePath "wsl.exe" -ArgumentList "--install", "--no-distribution" -Verb RunAs -Wait
        Todo "wsl" "WSL installed. Restart Windows, then run this script again."
        $ActionsForUser.Add("Restart Windows to finish installing WSL, then run this script again.")
        $WslRestartPending = $true
    }

    Step "Docker Desktop (includes Docker Compose)"
    if ($WslRestartPending) {
        # Docker Desktop depends on WSL; installing it before the WSL restart is unreliable.
        Todo "docker" "Deferred until after the Windows restart that completes the WSL installation."
    } elseif (Install-Winget "Docker.DockerDesktop") {
        Refresh-Path
        $dockerBin = Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"
        if ((-not (Get-Command docker -ErrorAction SilentlyContinue)) -and (Test-Path $dockerBin)) { $env:Path = "$dockerBin;$env:Path" }
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            $client = (& docker version --format "{{.Client.Version}}" 2>$null | Out-String).Trim()
            $server = (& docker version --format "{{.Server.Version}}" 2>$null | Out-String).Trim()
            $compose = (& docker compose version 2>&1 | Out-String).Trim()
            if ($server) {
                $hello = (& docker run --rm hello-world 2>&1 | Out-String)
                if ($hello -match "Hello from Docker!") { Ok "docker" "Docker client $client / engine $server; $compose; hello-world container ran" }
                else { Fail "docker" "Engine $server is running but hello-world failed: $hello" }
            } else {
                Todo "docker" "Docker CLI $client and $compose installed, but the engine is not running."
                $ActionsForUser.Add("Start 'Docker Desktop' from the Start menu, accept the agreement, wait until it says 'Engine running', then run this script again.")
            }
        } else {
            Todo "docker" "Docker Desktop installed but 'docker' is not on PATH yet."
            $ActionsForUser.Add("Restart Windows (or sign out and in), start Docker Desktop once, then run this script again.")
        }
    } else {
        Fail "docker" "winget could not install Docker.DockerDesktop."
    }
}

# ---------------------------------------------------------- analyzer (needs Docker)
Test-Analyzer

# -------------------------------------------------------------------- summary
Step "Summary"
foreach ($k in $Results.Keys) { Write-Host ("    {0,-9} {1}" -f $k, $Results[$k]) }
if ($ActionsForUser.Count -gt 0) {
    Write-Host ""; Write-Host "What you need to do next:" -ForegroundColor Yellow
    $i = 1; foreach ($a in ($ActionsForUser | Select-Object -Unique)) { Write-Host "    $i. $a"; $i++ }
}
Write-Host ""; Write-Host "Full log: $Transcript"
Stop-Transcript | Out-Null
