@echo off
REM Archipelago Web Dashboard - one-command launcher (Windows).
REM
REM   1. Edit config.toml
REM   2. Drop your generated *.archipelago into .\multiworld\
REM   3. Double-click run.bat  (or run it from a terminal)
REM
REM Creates a local Python virtualenv on first run, installs dependencies, then
REM serves the (prebuilt) dashboard on the port from config.toml.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo !! Python 3.11+ is required but was not found on PATH.
    echo    Install it from https://www.python.org/downloads/ and re-run.
    pause
    exit /b 1
)

REM config.toml is optional, but if it exists it must be valid TOML — a syntax
REM error (e.g. a duplicate key) makes the whole file silently fall back to
REM built-in defaults, which is confusing unless we call it out loudly here.
if exist config.toml (
    python -c "import tomllib; tomllib.load(open('config.toml','rb'))" >nul 2>nul
    if errorlevel 1 (
        echo !!
        echo !! WARNING: config.toml has invalid TOML syntax and is being IGNORED.
        echo !!          The dashboard will start with built-in defaults instead of
        echo !!          your settings. Fix config.toml and restart to apply them.
        echo !!
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo ==^> Creating virtual environment ^(.venv^)...
    python -m venv .venv
)

echo ==^> Installing dependencies...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r server\requirements.txt

echo ==^> Starting dashboard ^(close this window to stop^)...
".venv\Scripts\python.exe" -m server

pause
