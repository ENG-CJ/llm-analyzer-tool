[CmdletBinding()]
param(
    [ValidateSet('onefile', 'onedir')][string]$Mode = 'onefile',
    [switch]$SkipChecks
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { $PythonExe = (Get-Command python -ErrorAction Stop).Source }

function Invoke-Python {
    param([string[]]$Arguments)
    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE" }
}

Push-Location -LiteralPath $ProjectRoot
try {
    Invoke-Python -Arguments @('-c', 'import platform,struct,sys; assert platform.system()=="Windows" and platform.machine().lower() in ("amd64","x86_64") and struct.calcsize("P")==8; assert sys.version_info >= (3,11), "Python 3.11+ required"')
    if (-not $SkipChecks) {
        Invoke-Python -Arguments @('-m', 'ruff', 'check', '.')
        Invoke-Python -Arguments @('-m', 'mypy', 'src/llm_analyzer')
        Invoke-Python -Arguments @('-m', 'pytest', '-q')
    }
    Invoke-Python -Arguments @('scripts/validate_catalog.py')
    $BuildDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot 'build\pyinstaller'))
    $RequiredPrefix = $ProjectRoot.TrimEnd('\') + '\'
    if (-not $BuildDirectory.StartsWith($RequiredPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean a build directory outside this project'
    }
    if (Test-Path -LiteralPath $BuildDirectory) { Remove-Item -LiteralPath $BuildDirectory -Recurse -Force }
    $PreviousBuildMode = $env:LLM_ANALYZER_BUILD_MODE
    $env:LLM_ANALYZER_BUILD_MODE = $Mode
    try {
        Invoke-Python -Arguments @('-m', 'PyInstaller', '--noconfirm', '--clean', '--workpath', $BuildDirectory, '--distpath', 'dist', 'packaging/windows.spec')
    } finally { $env:LLM_ANALYZER_BUILD_MODE = $PreviousBuildMode }
    $BinaryRelative = if ($Mode -eq 'onefile') { 'dist\llm-analyzer-windows-x64.exe' } else { 'dist\llm-analyzer-windows-x64\llm-analyzer-windows-x64.exe' }
    $Binary = Join-Path $ProjectRoot $BinaryRelative
    if (-not (Test-Path -LiteralPath $Binary -PathType Leaf)) { throw 'PyInstaller did not produce the expected executable' }
    Invoke-Python -Arguments @('scripts/smoke_binary.py', $Binary)
    $Checksum = (Get-FileHash -LiteralPath $Binary -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Checksum  llm-analyzer-windows-x64.exe" | Set-Content -LiteralPath ($Binary + '.sha256') -Encoding ascii
    Write-Host "Built: $Binary"
    Write-Host "SHA-256: $Checksum"
} finally { Pop-Location }
