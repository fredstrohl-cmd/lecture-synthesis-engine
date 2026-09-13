$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$result = Join-Path $PSScriptRoot 'cage-test-result.txt'
'cage test log' | Out-File $result -Encoding utf8
function Log($m) { $m | Out-File $result -Append -Encoding utf8; Write-Host $m }

Log "started $(Get-Date -Format o)"
$mm = [regex]::Match((Get-Content "$env:LOCALAPPDATA\hermes\.env" -Raw), '(?i)AIza[a-z0-9_\-]{20,}')
$env:GEMINI_API_KEY = $mm.Value
$env:PYTHONIOENCODING = 'utf-8'
Log "keylen=$($env:GEMINI_API_KEY.Length)"
if (-not $env:GEMINI_API_KEY) { Log 'CAGE TEST: FAIL (no gemini key found)'; exit 1 }

Log '--- run 1: sabotaged lecture, expect HALT ---'
$out1 = ('A' | python engine.py sabotaged-lecture.txt --prompt adversarial-auditor-prompt-v1.1.md --out output 2>&1 | Out-String)
Log $out1
$md1 = Join-Path $PSScriptRoot 'output\sabotaged-lecture.md'
$c1 = if (Test-Path $md1) { Get-Content $md1 -Raw } else { '' }
Log "run1 halt banner seen: $($out1 -match 'HALT')"
Log "run1 output md exists: $(Test-Path $md1)"
Log "run1 resolution recorded: $($c1 -match '(?i)resolved')"
Log "run1 scratchpad leaked: $($c1 -match 'audit_scratchpad')"

Log '--- run 2: clean lecture, expect NO halt ---'
$out2 = (python engine.py clean-lecture.txt --prompt adversarial-auditor-prompt-v1.1.md --out output 2>&1 | Out-String)
Log $out2
$md2 = Join-Path $PSScriptRoot 'output\clean-lecture.md'
Log "run2 output md exists: $(Test-Path $md2)"
Log "run2 halt fired (want False): $($out2 -match 'HALT')"

$pass = ($out1 -match 'HALT') -and (Test-Path $md1) -and ($c1 -match '(?i)resolved') -and ($c1 -notmatch 'audit_scratchpad') -and (Test-Path $md2) -and ($out2 -notmatch 'HALT')
if ($pass) { Log 'CAGE TEST: PASS' } else { Log 'CAGE TEST: FAIL' }
Log "finished $(Get-Date -Format o)"
