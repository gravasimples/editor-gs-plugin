# Instalador único do Editor GS para Windows 10/11 (sem WSL). Uma linha, tudo no perfil do usuário, sem administrador.
# Uso (PowerShell): powershell -ExecutionPolicy Bypass -File .\instalar-editor-gs.ps1 -Chave GS1-...
# O que faz, em ordem: Git for Windows → Claude Code → login no Claude (navegador) → plugin editor-gs (repositório público)
# → instalação do motor (10 a 30 min) → chave do produto → sobe o app em http://localhost:3200. Pode rodar de novo: cada passo só faz o que falta.
param([string]$Chave = "", [switch]$SemSubir)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Marketplace = "gravasimples/editor-gs-plugin"

function Tem($nome) { [bool](Get-Command $nome -ErrorAction SilentlyContinue) }
function RecarregarPath {
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + "$env:USERPROFILE\.local\bin"
}
function Passo($n, $txt) { Write-Host ""; Write-Host "== $n $txt" -ForegroundColor Cyan }
function Winget($id) {
    if (-not (Tem winget)) { throw "winget não encontrado. Instale o 'Instalador de Aplicativo' pela Microsoft Store e rode de novo." }
    winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements --silent | Out-Null
    RecarregarPath
}

Write-Host "Editor GS — instalador para Windows ($(Get-Date -Format 'dd/MM/yyyy HH:mm'))" -ForegroundColor Green

Passo "0/6" "Smart App Control"
try {
    $sac = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy" -ErrorAction Stop).VerifiedAndReputablePolicyState
    if ($sac -eq 1 -or $sac -eq 2) {
        Write-Host "  AVISO: o Smart App Control está $(if ($sac -eq 1) {'LIGADO'} else {'em avaliação'}). Ele bloqueia o motor de transcrição do Editor GS." -ForegroundColor Yellow
        Write-Host "  Desligue em: Segurança do Windows → Controle de aplicativos e navegador → Smart App Control → Desativado (não dá para religar depois)." -ForegroundColor Yellow
        Write-Host "  A instalação continua; a transcrição só funciona depois de desligar." -ForegroundColor Yellow
    } else { Write-Host "  ok (desligado)" }
} catch { Write-Host "  não consegui ler (segue)" }

Passo "1/6" "Git for Windows (o Claude Code usa para baixar o plugin e rodar comandos)"
$gitBash = "$env:ProgramFiles\Git\bin\bash.exe"
if (-not (Test-Path $gitBash)) { $gitBash = "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" }
if (-not (Test-Path $gitBash)) { Write-Host "  instalando…"; Winget "Git.Git"; $gitBash = "$env:ProgramFiles\Git\bin\bash.exe"; if (-not (Test-Path $gitBash)) { $gitBash = "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe" } }
if (-not (Test-Path $gitBash)) { throw "Git for Windows não foi encontrado depois da instalação. Instale em https://git-scm.com/download/win e rode de novo." }
Write-Host "  ok: $gitBash"
if (-not [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")) {
    [Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", $gitBash, "User")
    Write-Host "  CLAUDE_CODE_GIT_BASH_PATH definido para o usuário."
}
$env:CLAUDE_CODE_GIT_BASH_PATH = [Environment]::GetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "User")

Passo "2/6" "Claude Code"
if (-not (Tem claude)) {
    Write-Host "  instalando…"
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    RecarregarPath
}
if (-not (Tem claude)) { throw "claude não encontrado no PATH. Feche e abra o PowerShell e rode de novo." }
Write-Host "  ok: $(claude --version)"

Passo "3/6" "Login no Claude (conta Pro ou Max; o navegador abre)"
$st = (& claude auth status 2>&1 | Out-String)
$logado = $false
try { $logado = [bool](($st | ConvertFrom-Json).loggedIn) } catch { $logado = ($st -match '"loggedIn":\s*true') }
if (-not $logado) { & claude login }
Write-Host "  ok"

Passo "4/6" "Plugin editor-gs"
claude plugin marketplace add $Marketplace 2>&1 | Out-Null
claude plugin marketplace update editor-gs 2>&1 | Out-Null
claude plugin install editor-gs@editor-gs 2>&1 | Out-Null
$lista = (claude plugin list 2>&1 | Out-String)
$raiz = ""
if ($lista -match "editor-gs@editor-gs[\s\S]*?Path:\s*(\S+)") { $raiz = $Matches[1] }
if (-not $raiz -or -not (Test-Path "$raiz\scripts\editor-gs.cmd")) {
    $cand = Get-ChildItem "$env:USERPROFILE\.claude\plugins" -Recurse -Depth 5 -Filter "editor-gs.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cand) { $raiz = $cand.Directory.Parent.FullName }
}
if (-not $raiz) { throw "O plugin não foi instalado. Confira a internet e rode de novo; se persistir, mande o print para a Grava Simples." }
Write-Host "  ok: $raiz"

Passo "5/6" "Motor de edição (10 a 30 min: Python, Node, ffmpeg, Remotion, app)"
& "$raiz\scripts\editor-gs.cmd" instalar
if ($LASTEXITCODE -ne 0) { throw "A instalação do motor falhou. Veja o log em $env:USERPROFILE\EditorGS\logs e rode de novo." }

Passo "6/6" "Chave e app"
if ($Chave) { & "$raiz\scripts\editor-gs.cmd" chave $Chave }
else { Write-Host "  sem chave informada: ative depois com  claude  →  /editor-gs:chave GS1-...  (peça a chave à Grava Simples)" }
if (-not $SemSubir) {
    & "$raiz\scripts\editor-gs.cmd" subir
    Start-Process "http://localhost:3200"
}
Write-Host ""
Write-Host "Pronto. O app abre em http://localhost:3200 (no navegador: 'Instalar como aplicativo' vira ícone)." -ForegroundColor Green
$fim = 'Depois de reiniciar o computador: abra o PowerShell e rode  "{0}\scripts\editor-gs.cmd" subir  ou, no Claude Code, /editor-gs:subir.' -f $raiz
Write-Host $fim
Write-Host "Atualizar o plugin quando a Grava Simples avisar:  claude plugin update editor-gs@editor-gs"
