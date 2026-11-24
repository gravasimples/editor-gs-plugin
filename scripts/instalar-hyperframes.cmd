@echo off
rem Instala o HyperFrames (teste integrado, 10/11/2026) só na pasta hyperframes\ do repo: nada global, não entra no instalador padrão.
rem Usa o Node portátil de ~\EditorGS\bin\node (ou EDITOR_GS_NODE_BIN). Depois: python testes\teste_hyperframes.py
setlocal
set "RAIZ=%~dp0.."
if defined EDITOR_GS_NODE_BIN (set "NODE_BIN=%EDITOR_GS_NODE_BIN%") else (set "NODE_BIN=%USERPROFILE%\EditorGS\bin\node")
if not exist "%NODE_BIN%\npm.cmd" ( echo Nao achei o Node portatil em "%NODE_BIN%". Rode scripts\editor-gs.cmd instalar antes. & exit /b 1 )
set "PATH=%NODE_BIN%;%USERPROFILE%\EditorGS\bin\ffmpeg\bin;%PATH%"
cd /d "%RAIZ%\hyperframes"
echo == npm install em %CD% (hyperframes 0.9.30 + gsap, ~100 MB; usa o Chrome do sistema, nao baixa Chromium)
call "%NODE_BIN%\npm.cmd" install --no-audit --no-fund
if errorlevel 1 ( echo npm install falhou. & exit /b 1 )
call "%CD%\node_modules\.bin\hyperframes.cmd" --version
echo == pronto. Conferir: "%CD%\node_modules\.bin\hyperframes.cmd" doctor
endlocal
