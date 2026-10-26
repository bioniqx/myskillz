# Install viral-video-studio for ZCode (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File .\install.ps1              -> user-level (%USERPROFILE%\.zcode\skills)
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 C:\path\repo -> project-level (<repo>\.zcode\skills)
param([string]$Project = "")
$ErrorActionPreference = "Stop"
$Src = Join-Path $PSScriptRoot "viral-video-studio"
if ($Project) { $Dest = Join-Path $Project ".zcode\skills" } else { $Dest = Join-Path $env:USERPROFILE ".zcode\skills" }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Target = Join-Path $Dest "viral-video-studio"
if (Test-Path $Target) {
  $Bak = "$Target.bak-" + (Get-Date -Format "yyyyMMddHHmmss")
  Move-Item $Target $Bak
  Write-Host "Previous version moved to $Bak (delete it yourself when no longer needed)."
}
Copy-Item -Recurse $Src $Dest
Write-Host "Installed to $Target"
$py = $null
foreach ($c in @("python", "py", "python3")) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if ($py) { & $py (Join-Path $Target "scripts\setup_check.py") } else { Write-Host "Python not found. Install it: winget install Python.Python.3.12" }
Write-Host ""
Write-Host "Next: open ZCode -> Settings -> Skills -> click Refresh, make sure 'viral-video-studio' is enabled."
Write-Host "Then type `$viral-video-studio in chat."
