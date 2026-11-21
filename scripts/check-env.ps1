# API Sentinel - read-only environment check.
# Records tool versions and registry reachability to logs\env-check.txt. Installs and changes nothing.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root "logs\env-check.txt"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"API Sentinel environment check - $(Get-Date -Format o)" | Out-File $log -Encoding utf8
"Windows: $([System.Environment]::OSVersion.VersionString)" | Out-File $log -Append -Encoding utf8

function Check($name, [scriptblock]$cmd) {
    "`n== $name" | Out-File $log -Append -Encoding utf8
    try { & $cmd 2>&1 | Select-Object -First 6 | Out-String | Out-File $log -Append -Encoding utf8 }
    catch { "NOT AVAILABLE: $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8 }
}

Check "java"           { java -version }
Check "javac"          { javac -version }
Check "JAVA_HOME"      { if ($env:JAVA_HOME) { $env:JAVA_HOME } else { "not set" } }
Check "mvn"            { mvn -v }
Check "docker"         { docker version --format "client {{.Client.Version}} / server {{.Server.Version}}" }
Check "docker compose" { docker compose version }
Check "python"         { python --version }
Check "py launcher"    { py -0 }
Check "uv"             { uv --version }
Check "git"            { git --version }
Check "node"           { node --version }
Check "npm"            { npm --version }
Check "winget"         { winget --version }

"`n== network" | Out-File $log -Append -Encoding utf8
foreach ($url in @(
    "https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot/maven-metadata.xml",
    "https://registry-1.docker.io/v2/",
    "https://api.adoptium.net/v3/info/available_releases",
    "https://pypi.org/simple/",
    "https://registry.npmjs.org/")) {
    try {
        $r = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 20
        "$url -> $($r.StatusCode)" | Out-File $log -Append -Encoding utf8
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code) { "$url -> HTTP $code (reachable)" | Out-File $log -Append -Encoding utf8 }
        else { "$url -> FAILED: $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8 }
    }
}
"`nDone. Results written to $log"
Get-Content $log
