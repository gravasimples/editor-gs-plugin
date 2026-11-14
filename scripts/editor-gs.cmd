@echo off
rem Porta única do Editor GS no Windows: scripts\editor-gs.cmd instalar | subir | parar | status | abrir | caminhos | checar
setlocal
set "RAIZ=%~dp0.."
set "PYTHONUTF8=1"
if defined EDITOR_GS_VENV (set "PY=%EDITOR_GS_VENV%\Scripts\python.exe") else (set "PY=%USERPROFILE%\.venvs\editor-gs\Scripts\python.exe")
if exist "%PY%" goto :rodar
rem primeira vez: uv + Python 3.14 no perfil do usuário (sem admin)
if not exist "%USERPROFILE%\.local\bin\uv.exe" powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
"%USERPROFILE%\.local\bin\uv.exe" python install 3.14 >nul 2>&1
for /f "delims=" %%i in ('"%USERPROFILE%\.local\bin\uv.exe" python find 3.14 2^>nul') do set "PY=%%i"
if not exist "%PY%" ( echo Nao achei um Python 3.14. Instale o uv ^(https://astral.sh/uv^) e rode de novo. & exit /b 1 )
:rodar
"%PY%" "%RAIZ%\scripts\editor_gs.py" %*
endlocal
