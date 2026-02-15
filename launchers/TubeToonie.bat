@echo off
setlocal

REM Double-click launcher for Windows.
REM Starts the Streamlit UI using the repo's easy runner.

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..\

cd /d "%PROJECT_DIR%"

REM Prefer Git Bash if available (so we can run the existing .sh scripts)
where bash >nul 2>nul
if %ERRORLEVEL%==0 (
  bash -lc "chmod +x run-ui-easy.sh && ./run-ui-easy.sh"
  exit /b %ERRORLEVEL%
)

echo ERROR: 'bash' not found.
echo Install Git for Windows (includes Git Bash) from: https://git-scm.com/download/win
echo Then re-run this launcher.
pause
exit /b 1
