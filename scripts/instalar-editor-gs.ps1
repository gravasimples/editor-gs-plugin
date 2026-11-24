# Instalador único do Editor GS para Windows 10/11 (sem WSL). Uma linha, tudo no perfil do usuário, sem administrador.
# Uso (PowerShell): powershell -ExecutionPolicy Bypass -File .\instalar-editor-gs.ps1 -Chave GS1-...
# O que faz, em ordem: Git for Windows → Claude Code → login no Claude (navegador) → plugin editor-gs (repositório público)
# → instalação do motor (3 a 8 min com o pacote pré-montado da release; 10 a 30 min sem) → chave do produto → sobe o app em http://localhost:3200. Pode rodar de novo: cada passo só faz o que falta.
param([string]$Chave = "", [switch]$SemSubir, [switch]$IgnorarSmartAppControl)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Marketplace = "gravasimples/editor-gs-plugin"
# Rodando pelo "Instalar Editor GS.cmd" (arquivo único): tira a marca de "baixado da internet" para o aviso não voltar na próxima vez.
if ($env:GS_SELF -and (Test-Path -LiteralPath $env:GS_SELF)) { Unblock-File -LiteralPath $env:GS_SELF -ErrorAction SilentlyContinue }

# Só programas de verdade (.exe/.cmd): nomes de função no PowerShell não diferenciam maiúsculas, e uma função "Winget" já escondeu o winget.exe
# e entrou em loop infinito (CallDepthOverflow no PC do Thiago, 13/11/2026). Por isso nenhuma função aqui tem nome de programa.
function Tem($nome) { [bool](Get-Command $nome -CommandType Application -ErrorAction SilentlyContinue) }
function RecarregarPath {
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + "$env:USERPROFILE\.local\bin"
}
function Passo($n, $txt) { Write-Host ""; Write-Host "== $n $txt" -ForegroundColor Cyan }
# Roda um programa externo sem que avisos no stderr derrubem o script: no PowerShell 5.1, "2>&1" com ErrorActionPreference=Stop vira erro fatal.
function Rodar([scriptblock]$bloco) {
    $antes = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { (& $bloco 2>&1 | ForEach-Object { "$_" }) -join "`n" } finally { $ErrorActionPreference = $antes }
}
function AcharGitBash {
    foreach ($c in @("$env:ProgramFiles\Git\bin\bash.exe", "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe")) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}
function InstalarGitPeloWinget {
    if (-not (Tem winget.exe)) { Write-Host "  winget não disponível; baixando direto do site do Git…"; return }
    Rodar { winget.exe install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent } | Out-Null
    RecarregarPath
}
# Plano B: instalador oficial do GitHub, só para o usuário (/CURRENTUSER, sem administrador), em %LOCALAPPDATA%\Programs\Git.
function InstalarGitDireto {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $rel = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest" -Headers @{ "User-Agent" = "editor-gs-instalador" }
    $arq = if ([Environment]::Is64BitOperatingSystem) { "64-bit.exe" } else { "32-bit.exe" }
    $asset = $rel.assets | Where-Object { $_.name -like "Git-*-$arq" } | Select-Object -First 1
    if (-not $asset) { throw "não achei o instalador do Git na página de downloads" }
    $exe = Join-Path $env:TEMP $asset.name
    Invoke-WebRequest $asset.browser_download_url -OutFile $exe -UseBasicParsing
    Start-Process $exe -ArgumentList "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/SP-" -Wait
    Remove-Item $exe -ErrorAction SilentlyContinue
    RecarregarPath
}

Write-Host "Editor GS — instalador para Windows ($(Get-Date -Format 'dd/MM/yyyy HH:mm'))" -ForegroundColor Green

Passo "0/6" "Smart App Control"
try {
    $sac = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy" -ErrorAction Stop).VerifiedAndReputablePolicyState
    if ($sac -eq 1 -and -not $IgnorarSmartAppControl) {
        Write-Host "  O Smart App Control do Windows está LIGADO. Ele bloqueia o motor de transcrição do Editor GS." -ForegroundColor Yellow
        Write-Host "  Para continuar, desligue (leva 1 minuto):" -ForegroundColor Yellow
        Write-Host "    1. Abra o menu Iniciar e digite: Smart App Control" -ForegroundColor Yellow
        Write-Host "    2. Clique em 'Configurações do Smart App Control'" -ForegroundColor Yellow
        Write-Host "    3. Marque 'Desativado' e confirme (o Windows não deixa religar depois)" -ForegroundColor Yellow
        Write-Host "    4. Dê dois cliques no instalador de novo" -ForegroundColor Yellow
        Write-Host "  Nada foi baixado ainda." -ForegroundColor Yellow
        throw "Smart App Control ligado: instalação parada antes de baixar."
    } elseif ($sac -eq 1) {
        Write-Host "  AVISO: Smart App Control LIGADO; seguindo por pedido (-IgnorarSmartAppControl). A transcrição não vai funcionar até desligar." -ForegroundColor Yellow
    } elseif ($sac -eq 2) {
        Write-Host "  AVISO: o Smart App Control está em avaliação. Se o Windows ligar ele depois, a transcrição para; nesse caso desligue e rode de novo." -ForegroundColor Yellow
    } else { Write-Host "  ok (desligado)" }
} catch {
    if ($_.Exception.Message -like "Smart App Control ligado*") { throw }
    Write-Host "  não consegui ler (segue)"
}

if (-not $Chave) {
    try {
        $Chave = (Read-Host "  Cole aqui a chave que a Grava Simples mandou (começa com GS1-) e aperte Enter. Sem chave, só Enter").Trim()
    } catch { $Chave = "" }
}

Passo "1/6" "Git for Windows (o Claude Code usa para baixar o plugin e rodar comandos)"
$gitBash = AcharGitBash
if (-not $gitBash) {
    Write-Host "  instalando… (se o Windows pedir permissão, clique em Sim)"
    try { InstalarGitPeloWinget } catch { Write-Host "  winget falhou ($($_.Exception.Message)); tentando o download direto…" }
    $gitBash = AcharGitBash
    if (-not $gitBash) {
        try { InstalarGitDireto } catch { Write-Host "  download direto falhou: $($_.Exception.Message)" -ForegroundColor Yellow }
        $gitBash = AcharGitBash
    }
}
if (-not $gitBash) { throw "Git for Windows não foi instalado. Instale em https://git-scm.com/download/win (Next em tudo) e dê dois cliques no instalador de novo." }
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
function EstaLogado {
    $st = Rodar { claude auth status }
    try { return [bool](($st | ConvertFrom-Json).loggedIn) } catch { return ($st -match '"loggedIn":\s*true') }
}
if (-not (EstaLogado)) {
    $antes = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    try { & claude auth login } finally { $ErrorActionPreference = $antes }
    if (-not (EstaLogado)) { throw "O login no Claude não foi concluído. Dê dois cliques no instalador de novo e entre na sua conta quando o navegador abrir." }
}
Write-Host "  ok"

Passo "4/6" "Plugin editor-gs"
Rodar { claude plugin marketplace add $Marketplace } | Out-Null
Rodar { claude plugin marketplace update editor-gs } | Out-Null
Rodar { claude plugin install editor-gs@editor-gs } | Out-Null
$lista = Rodar { claude plugin list }
$raiz = ""
if ($lista -match "editor-gs@editor-gs[\s\S]*?Path:\s*(\S+)") { $raiz = $Matches[1] }
if (-not $raiz -or -not (Test-Path "$raiz\scripts\editor-gs.cmd")) {
    $cand = Get-ChildItem "$env:USERPROFILE\.claude\plugins" -Recurse -Depth 5 -Filter "editor-gs.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cand) { $raiz = $cand.Directory.Parent.FullName }
}
if (-not $raiz) { throw "O plugin não foi instalado. Confira a internet e rode de novo; se persistir, mande o print para a Grava Simples." }
Write-Host "  ok: $raiz"

Passo "5/6" "Motor de edição (3 a 8 min com o pacote pronto; 10 a 30 min pela rede: Python, Node, ffmpeg, Remotion, app)"
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
