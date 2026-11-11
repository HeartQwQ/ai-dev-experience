@echo off
cd /d "%~dp0"
set "TASK_PYTHON=%DEV_SPEC_PYTHON%"
if not defined TASK_PYTHON if exist "%~dp0.dev-spec\local\python-executable.txt" set /p TASK_PYTHON=<"%~dp0.dev-spec\local\python-executable.txt"
if defined TASK_PYTHON if not exist "%TASK_PYTHON%" set "TASK_PYTHON=python"
if not defined TASK_PYTHON set "TASK_PYTHON=python"
"%TASK_PYTHON%" "%~dp0tools\dev-spec\dev.py" --root "%~dp0." %*
if errorlevel 1 pause
