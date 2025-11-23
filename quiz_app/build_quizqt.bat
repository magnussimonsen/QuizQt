@echo off
setlocal enabledelayedexpansion

REM Convenience wrapper to build the QuizQt executable with PyInstaller on Windows (Cmd).
REM Usage: from the repo root, run `quiz_app\build_quizqt.bat`

set "SCRIPT_DIR=%~dp0"
set "PUSHED=0"
pushd "%SCRIPT_DIR%" >nul || goto :error
set "PUSHED=1"

set "PYTHON_CMD="
if exist ..\.venv\Scripts\python.exe set "PYTHON_CMD=..\.venv\Scripts\python.exe"
if "%PYTHON_CMD%"=="" if exist .\.venv\Scripts\python.exe set "PYTHON_CMD=.\.venv\Scripts\python.exe"
if "%PYTHON_CMD%"=="" (
    where py >nul 2>&1 && set "PYTHON_CMD=py"
)
if "%PYTHON_CMD%"=="" (
    where python >nul 2>&1 && set "PYTHON_CMD=python"
)

if "%PYTHON_CMD%"=="" (
    echo ERROR: Unable to locate Python. Activate your virtual environment or add python to PATH.
    goto :error
)

echo Using Python: %PYTHON_CMD%
"%PYTHON_CMD%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing into the active environment...
    "%PYTHON_CMD%" -m pip install --upgrade pip || goto :error
    "%PYTHON_CMD%" -m pip install pyinstaller || goto :error
)

echo Building executable with PyInstaller (QuizQt.spec)...
"%PYTHON_CMD%" -m PyInstaller QuizQt.spec || goto :error

if exist dist\QuizQt\QuizQt.exe (
    echo Build complete: dist\QuizQt\QuizQt.exe
    goto :success
) else (
    echo ERROR: Build finished, but dist\QuizQt\QuizQt.exe was not created.
    goto :error
)


:success
if "%PUSHED%"=="1" popd >nul
endlocal
exit /b 0

:error
if "%PUSHED%"=="1" popd >nul
endlocal
exit /b 1
