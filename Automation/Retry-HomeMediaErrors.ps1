param(
    [string]$MainLog = "C:\Starlight Manor Command\logs\HomeMedia_to_StarlightVault.log",
    [string]$SourceRoot = "S:\Media\Home Media",
    [string]$DestRoot = "\\192.168.68.158\Media\Home Media",
    [string]$RetryLogsDir = "C:\Starlight Manor Command\logs\HomeMedia_RetryLogs",
    [int]$Retries = 100,
    [int]$WaitSeconds = 30,
    [int]$IPG = 20,
    [switch]$WhatIf,
    [switch]$VerboseMatch
)

if (-not (Test-Path $MainLog)) { throw "Main log not found: $MainLog" }
if (-not (Test-Path $SourceRoot)) { throw "Source root not found: $SourceRoot" }
if (-not (Test-Path $RetryLogsDir)) { New-Item -ItemType Directory -Path $RetryLogsDir | Out-Null }

# Read log
$lines = Get-Content -LiteralPath $MainLog

# Grab any line that looks like an ERROR line referencing "Copying File ..."
$matchLines = $lines | Where-Object { $_ -match 'ERROR\s+\d+.*Copying File' }

Write-Host ""
Write-Host "Log: $MainLog"
Write-Host "ERROR+Copying File lines found: $($matchLines.Count)"
Write-Host ""

if ($VerboseMatch) {
    Write-Host "First 25 matching ERROR lines:"
    $matchLines | Select-Object -First 25 | ForEach-Object { Write-Host $_ }
    Write-Host ""
}

# Extract file paths from those lines
$failedFiles = $matchLines |
    ForEach-Object {
        if ($_ -match 'Copying File\s+(.+)$') { $matches[1].Trim() }
    } |
    Where-Object { $_ } |
    Select-Object -Unique

Write-Host "Failed file paths extracted: $($failedFiles.Count)"
if ($failedFiles.Count -gt 0) {
    Write-Host "First 20 extracted paths:"
    $failedFiles | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
}
Write-Host ""

# Filter to only those under SourceRoot (case-insensitive), but allow either S:\Media\Home Media\ or S:\Media\Home Media
$failedFilesUnderRoot = $failedFiles | Where-Object {
    $_.StartsWith($SourceRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

Write-Host "Failed files under SourceRoot '$SourceRoot': $($failedFilesUnderRoot.Count)"
if ($failedFilesUnderRoot.Count -eq 0) {
    Write-Warning "No failed files under SourceRoot. This usually means either:"
    Write-Warning "1) The SourceRoot is different than what appears in the log, or"
    Write-Warning "2) You're pointing at a different robocopy log than the one with the errors."
    Write-Warning "Tip: run with -VerboseMatch to print the first 25 error lines."
    exit 0
}

# Group by directory so we retry only the affected folders
$failedDirs = $failedFilesUnderRoot |
    ForEach-Object { Split-Path -Path $_ -Parent } |
    Select-Object -Unique |
    Sort-Object

Write-Host ""
Write-Host "Folders to retry: $($failedDirs.Count)"
Write-Host "Retry logs dir: $RetryLogsDir"
Write-Host ""

function New-SafeName([string]$text) {
    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    foreach ($c in $invalid) { $text = $text.Replace($c, '_') }
    if ($text.Length -gt 120) { $text = $text.Substring(0, 120) }
    return $text
}

foreach ($dir in $failedDirs) {
    $rel = $dir.Substring($SourceRoot.Length).TrimStart('\')
    $destDir = Join-Path -Path $DestRoot -ChildPath $rel

    $safeRel = New-SafeName($rel)
    if ([string]::IsNullOrWhiteSpace($safeRel)) { $safeRel = "ROOT" }

    $retryLog = Join-Path -Path $RetryLogsDir -ChildPath ("Retry_" + $safeRel + ".log")

    Write-Host "Retrying folder:"
    Write-Host "  Source: $dir"
    Write-Host "  Dest:   $destDir"
    Write-Host "  Log:    $retryLog"

    $args = @(
        "`"$dir`"",
        "`"$destDir`"",
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/Z",
        "/J",
        "/R:$Retries",
        "/W:$WaitSeconds",
        "/IPG:$IPG",
        "/FFT",
        "/TEE",
        "/LOG+:`"$retryLog`""
    )

    if ($WhatIf) {
        Write-Host "  WHATIF: robocopy $($args -join ' ')"
        Write-Host ""
        continue
    }

    Write-Host ""
    $proc = Start-Process -FilePath "robocopy.exe" -ArgumentList $args -NoNewWindow -PassThru -Wait
    if ($proc.ExitCode -ge 8) {
        Write-Warning "Robocopy reported a failure (ExitCode=$($proc.ExitCode)) for folder: $dir"
    }
    Write-Host ""
}

Write-Host "Done. Review retry logs in: $RetryLogsDir"
