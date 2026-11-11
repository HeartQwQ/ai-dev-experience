$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = $env:DEV_SPEC_PYTHON
$taskPythonFile = Join-Path $PSScriptRoot '.dev-spec/local/python-executable.txt'
if (-not $taskPython -and (Test-Path -LiteralPath $taskPythonFile)) {
    $taskPython = (Get-Content -LiteralPath $taskPythonFile -Raw -Encoding UTF8).Trim()
}
if (-not $taskPython -or -not (Test-Path -LiteralPath $taskPython)) {
    $uvCmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCmd) {
        $uvPy = (& uv python find 2>$null)
        if ($LASTEXITCODE -eq 0 -and $uvPy -and (Test-Path -LiteralPath $uvPy.Trim())) {
            $taskPython = $uvPy.Trim()
        }
    }
}
if (-not $taskPython -or -not (Test-Path -LiteralPath $taskPython)) { $taskPython = 'python' }
& $taskPython (Join-Path $PSScriptRoot 'tools/dev-spec/dev.py') --root $PSScriptRoot @args
exit $LASTEXITCODE
