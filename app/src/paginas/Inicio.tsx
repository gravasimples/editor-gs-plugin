import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, type Campanha, type Estilo, type Fluxo, type Recebido, type Referencia } from '../api'
import { useMicrofone } from '../microfone'
import { SeletorPasta } from '../Pastas'
import { BotaoAnexar, ChipsDrive } from '../DriveSeletor'
import type { DriveItem, EstiloCfg } from '../api'
import { PainelEstilo } from '../PainelEstilo'

const FICHA_MARCA = 'Siga a ficha de marca: `marca/manual.md` (voz, visual, claims), `marca/voz.md` e `marca/produtos.md`. Não cite preço, oferta nem número de alunos.'
const FLUXOS_COM_VOZ = ['video-locucao', 'dublagem']
const FLUXOS_COM_PLANO = ['video-locucao']
const AUTOMATICO = 'Modo automático: poste o plano de cenas, mas monte direto, sem esperar minha aprovação.'
const VOZ_THIAGO = 'Narre com a voz clonada do Thiago (voz_nome="thiago" em narrar/montar_locucao/dublar; motor Qwen3-TTS: ~1–2 min de carga na primeira vez e ~7 s de processamento por segundo de fala, avise o tempo se o texto passar de 1 min). Na entrega, diga que é voz sintética clonada do Thiago, nunca gravação dele.'
const MODOS_COM_MARCA = ['carrossel', 'roteiro', 'locucao', 'apostila', 'gravo', 'aula']
// fluxos sem edição de vídeo: o painel Estilo do criativo não aparece (nem vai no pedido)
const FLUXOS_SEM_ESTILO = ['carrossel', 'roteiro', 'roteiro-aula', 'apostila', 'analise-resultados', 'respostas-comentarios', 'depoimentos-semanais', 'traduzir-legenda', 'dublagem', 'stories-serie', 'referencia-analise']
// especialistas da tela inicial (fase D, como no Máquina): atalhos para os dois pedidos mais comuns
const ESPECIALISTAS = [
  { id: 'aula', icone: '🎓', titulo: 'Roteiro de aula', desc: 'Tema ou ementa vira aula gravável: plano por blocos, texto para o teleprompter, o que mostrar no OBS, exercício e material de apoio.', fluxo: 'roteiro-aula', texto: 'Monte o roteiro de uma aula (fluxo roteiro-aula) sobre: [tema]. Para iniciante que ensina online, aula gravada horizontal de 10 a 12 min, com demonstração no OBS.' },
  { id: 'editar', icone: '🎬', titulo: 'Editar um vídeo', desc: 'Anexe o bruto: corte do tempo morto, grafismos guiados pela fala, legenda e acabamento no nível profissional.', fluxo: 'reels-padrao', estilo: 'profissional', texto: 'Edite este vídeo no nível profissional: corte o tempo morto e as repetições de take, grafismos guiados pela fala, legenda embaixo e tela final.' },
]

const modos = [
  { id: 'editar', titulo: 'Editar um vídeo que já tenho', desc: 'Cortes, legenda karaokê e entrega em vertical e 16:9.', fluxo: 'reels-padrao', texto: 'Edite este vídeo com corte dinâmico, legenda no estilo padrão e entrega em 9:16 e 16:9.' },
  { id: 'cortes', titulo: 'Cortes de um vídeo longo', desc: 'Live, aula, YouTube ou call em vários vídeos curtos (abre o Clipador).', fluxo: '', texto: '', rota: '/clipador' },
  { id: 'kit', titulo: 'Kit de derivação', desc: 'Uma live, aula ou vídeo do YouTube vira um pacote: Reels prontos, carrossel, Stories e capítulos do YouTube, num pedido só.', fluxo: '', texto: '', rota: '/clipador?kit=1' },
  { id: 'carrossel', titulo: 'Carrossel ou post de imagem', desc: 'Slides 1080×1350 no manual da marca, com fotos reais se você anexar.', fluxo: 'carrossel', texto: 'Crie um carrossel para o Instagram sobre este tema, no manual da Grava Simples (modelo tipográfico; use as fotos anexadas se houver). Tema: ' },
  { id: 'depoimentos', titulo: 'Depoimentos da semana', desc: 'Prints de alunos no molde do post semanal: três por tela em cartões 3D e tela final com o CTA.', fluxo: 'depoimentos-semanais', texto: 'Monte o carrossel semanal de depoimentos com os prints anexados, no fluxo depoimentos-semanais (molde fixo). Prints novos primeiro; se faltar para fechar a tela, use os antigos e avise no relatório. Deixe de fora print que cita concorrente ou que não seja depoimento de aluno.' },
  { id: 'gravo', titulo: 'Gravo eu mesmo', desc: 'O Editor escreve o texto pronto para o teleprompter e o guia de gravação; você grava pelo app com a voz do Thiago, anexa o take aqui e ele edita.', fluxo: 'gravo-eu-mesmo', texto: 'Quero gravar eu mesmo (fluxo gravo-eu-mesmo): escreva o texto para o teleprompter, o guia de gravação e a legenda do post sobre: [tema]. Formato: Reels de 30 a 60 s.' },
  { id: 'roteiro', titulo: 'Só roteiro e estratégia', desc: 'Gancho, roteiro falado, o que mostrar na tela e legenda do post. Sem produzir ainda.', fluxo: 'roteiro', texto: 'Quero só o roteiro e a estratégia (fluxo roteiro), sem produzir: gancho, roteiro falado na voz do Thiago, o que mostrar na tela, CTA e legenda do post. Tema: ' },
  { id: 'traduzir', titulo: 'Traduzir a legenda', desc: 'Legenda em inglês ou espanhol no estilo da marca, queimada no vídeo e em SRT separado. Sem cortar nada.', fluxo: 'traduzir-legenda', texto: 'Traduza a legenda deste vídeo para o inglês (fluxo traduzir-legenda): sem cortar nada, legenda queimada em 9:16 no estilo padrão e o SRT traduzido separado. Idioma: inglês.' },
  { id: 'locucao', titulo: 'Vídeo do zero com locução', desc: 'Você dá o tema ou o roteiro; o Editor escreve as cenas, narra com voz sintética (não é a do Thiago), monta com prints e slides da marca e legenda.', fluxo: 'video-locucao', texto: 'Faça um vídeo do zero com locução (fluxo video-locucao) sobre: [tema]. Formato 9:16, até 45 s, voz antonio, legenda no estilo padrão. Use prints do OBS, fotos reais ou cenas `slide` animadas da marca; se eu anexei imagens ou vídeos, use-os.' },
  { id: 'dublar', titulo: 'Dublar o vídeo', desc: 'Voz sintética em inglês ou espanhol no lugar da fala, com legenda no idioma novo. Sem cortar nada.', fluxo: 'dublagem', texto: 'Dube este vídeo para o inglês (fluxo dublagem): traduza a fala, narre com voz sintética no lugar da original, legenda karaokê em inglês no estilo padrão, 9:16. Idioma: inglês.' },
  { id: 'apostila', titulo: 'Apostila ou slides em PDF', desc: 'Material de apoio da aula ou da live, diagramado na marca: A4 corrido ou slides 16:9.', fluxo: 'apostila', texto: 'Faça uma apostila em PDF (fluxo apostila) sobre: [tema]. Para iniciante que ensina online, com passo a passo e dicas; use os prints que eu anexar. Formato: apostila (A4).' },
  { id: 'legenda', titulo: 'Só legendar', desc: 'Transcrição e legenda karaokê sem cortar nada.', fluxo: '', texto: 'Transcreva e legende este vídeo no estilo padrão, sem cortar nada. Entregue 9:16 com legenda queimada e o SRT separado.' },
  { id: 'relatorio', titulo: 'Me diga o que tem no vídeo', desc: 'Duração, resumo, pausas longas e frases repetidas.', fluxo: '', texto: 'Leia este vídeo e devolva um relatório: duração, resumo do que é dito, pausas longas e frases repetidas. Sem cortar nada.' },
]

// mesmo texto de servico/campanhas.texto_pedido: o Editor sabe de que campanha é a peça
const campanhaTexto = (c: Campanha) => [`Peça da campanha "${c.nome}"`, c.objetivo && `objetivo: ${c.objetivo}`, c.mensagem && `mensagem-chave: ${c.mensagem}`, (c.inicio || c.fim) && `período ${c.inicio || '?'} a ${c.fim || '?'}`].filter(Boolean).join('; ') + '. Peça orgânica: sem preço, oferta, número de alunos ou falsa escassez.'

export default function Inicio() {
  const nav = useNavigate()
  const loc = useLocation()
  const query = new URLSearchParams(loc.search)
  const [pedido, setPedido] = useState<string>((loc.state as any)?.pedido || query.get('text') || query.get('title') || '')
  const [recebido, setRecebido] = useState<Recebido | null>(null)
  const [recebidoErro, setRecebidoErro] = useState('')
  const [referencia, setReferencia] = useState<Referencia | null>(null)
  const [fluxo, setFluxo] = useState<string>((loc.state as any)?.fluxo || '')
  const [estilo, setEstilo] = useState<string>((loc.state as any)?.estilo || query.get('estilo') || 'padrao')
  const [pasta, setPasta] = useState<string>((loc.state as any)?.pasta || query.get('pasta') || '')
  const [marca, setMarca] = useState(false)
  const [campanha, setCampanha] = useState<Campanha | null>(null)  // pedido aberto "para a campanha" (/novo?campanha=<id>)
  const [vozThiago, setVozThiago] = useState(false)
  const [estiloCfg, setEstiloCfg] = useState<EstiloCfg | null>(null)  // painel Estilo do criativo (vem com o padrão salvo)
  const [automatico, setAutomatico] = useState(false)  // chip: pula a aprovação do plano de cenas (vídeo do zero)  // chip: manda narrar com a voz clonada (sintética) do Thiago; vem ligado se a página Voz marcou 'usar por padrão'
  const [vozInfo, setVozInfo] = useState<{ existe: boolean; padrao: boolean } | null>(null)
  const [modelo, setModelo] = useState('padrao')  // agente que responde: padrao (Opus), fable, codex, gemini — só os configurados aparecem
  const [modelos, setModelos] = useState<{ id: string; rotulo: string; disponivel: boolean }[]>([])
  const [fluxos, setFluxos] = useState<Fluxo[]>([])
  const [estilos, setEstilos] = useState<Estilo[]>([])
  const [arquivos, setArquivos] = useState<File[]>([])
  const [drive, setDrive] = useState<DriveItem[]>([])  // escolhidos no Google Drive: o gateway baixa e só então põe o pedido na fila
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState<number | null>(null)
  const mic = useMicrofone(t => setPedido(p => (p ? p + ' ' : '') + t))
  useEffect(() => { api.voz().then(r => { const v = r.vozes.find(x => x.nome === 'thiago'); setVozInfo({ existe: !!v && r.disponivel, padrao: !!v?.padrao_locucao }); if (v?.padrao_locucao) setVozThiago(true) }).catch(() => {}) }, [])
  useEffect(() => { api.fluxos().then(setFluxos).catch(() => {}); api.estilos().then(setEstilos).catch(() => {}); api.estado().then(e => setModelos((e?.modelos || []).filter((m: any) => m.disponivel))).catch(() => {}) }, [])
  useEffect(() => {
    const rid = query.get('referencia')
    if (!rid) { setReferencia(null) } else api.referencia(rid).then(r => { setReferencia(r); setFluxo('minha-versao'); if (!pedido) setPedido(`Quero a nossa versão desta referência: ${r.titulo}${r.nota ? ` (o que gostamos: ${r.nota})` : ''}. Primeiro o roteiro na voz do Thiago; se eu anexar vídeo bruto, edite depois do roteiro aprovado.`) }).catch(e => setRecebidoErro(e.message))
    const token = query.get('recebido')
    if (!token) { setRecebido(null); return }
    api.recebido(token).then(r => { setRecebido(r); if (r.texto && !pedido) setPedido(r.texto) }).catch(e => setRecebidoErro(e.message || 'Material não encontrado'))
  }, [loc.search])

  useEffect(() => { const cid = query.get('campanha'); if (!cid) { setCampanha(null); return } api.campanhas().then(r => setCampanha(r.campanhas.find(c => c.id === cid) || null)).catch(() => {}) }, [loc.search])

  async function enviar() {
    setErro(''); setEnviando(true)
    try {
      let texto = marca && pedido.trim() ? `${pedido.trim()}\n\n${FICHA_MARCA}` : pedido
      if (vozThiago && FLUXOS_COM_VOZ.includes(fluxo) && texto.trim()) texto = `${texto.trim()}\n\n${VOZ_THIAGO}`
      if (automatico && FLUXOS_COM_PLANO.includes(fluxo) && texto.trim()) texto = `${texto.trim()}\n\n${AUTOMATICO}`
      if (campanha && texto.trim()) texto = `${texto.trim()}\n\n${campanhaTexto(campanha)}`
      if (marca) { try { await api.marca(true) } catch {} }
      const fd = new FormData(); fd.append('pedido', texto); fd.append('fluxo', fluxo); fd.append('estilo', estilo); fd.append('pasta', pasta); fd.append('modelo', modelo)
      if (comEstilo && estiloCfg) fd.append('estilo_criativo', JSON.stringify(estiloCfg))
      if (campanha) fd.append('campanha', campanha.nome)
      arquivos.forEach(a => fd.append('arquivos', a))
      if (drive.length) fd.append('drive', JSON.stringify(drive.map(d => ({ raiz: d.raiz, caminho: d.caminho }))))
      if (recebido) fd.append('recebido', recebido.token)
      if (referencia) fd.append('referencia', referencia.id)
      if ((loc.state as any)?.notion_page) fd.append('notion_page', (loc.state as any).notion_page)
      setProgresso(0)
      const c = await api.novaConversa(fd, setProgresso); nav(`/c/${c.id}`)
    } catch (e: any) { setErro(e.message || 'Falhou') } finally { setEnviando(false); setProgresso(null) }
  }
  const mb = arquivos.reduce((s, a) => s + a.size, 0) / 1e6
  const comEstilo = !FLUXOS_SEM_ESTILO.includes(fluxo)
  return (
    <div className="max-w-3xl mx-auto px-4 py-8 md:py-14">
      <h1 className="text-3xl md:text-4xl text-center">O que vamos <span className="text-laranja">editar</span> hoje?</h1>
      <p className="text-center text-nevoa mt-3">Descreva o que você precisa e anexe o vídeo bruto (e o áudio do microfone, se for separado).</p>
      <div className="mt-8"><div className="text-sm text-nevoa mb-2">Escolha um especialista</div>
        <div className="grid sm:grid-cols-2 gap-3">{ESPECIALISTAS.map(e => <button key={e.id} onClick={() => { setPedido(e.texto); setFluxo(e.fluxo); if ((e as any).estilo) setEstilo((e as any).estilo); setMarca(MODOS_COM_MARCA.includes(e.id)) }} className={`cartao text-left p-4 border border-laranja/30 hover:bg-card2 transition ${pedido === e.texto ? 'ring-2 ring-laranja' : ''}`}>
          <div className="font-bold">{e.icone} {e.titulo}</div><div className="text-sm text-nevoa mt-1">{e.desc}</div></button>)}</div>
        <div className="text-sm text-nevoa mt-5 mb-2">Ou escolha o tipo de pedido</div></div>
      <div className="grid sm:grid-cols-2 gap-3">
        {modos.map(m => <button key={m.id} onClick={() => { if ((m as any).rota) { nav((m as any).rota); return } setPedido(m.texto); setFluxo(m.fluxo); setMarca(MODOS_COM_MARCA.includes(m.id)) }} className={`cartao text-left p-4 hover:bg-card2 transition ${pedido === m.texto ? 'ring-2 ring-laranja' : ''}`}>
          <div className="font-bold">{m.titulo}</div><div className="text-sm text-nevoa mt-1">{m.desc}</div></button>)}
      </div>
      <div className="cartao p-4 mt-6">
        <textarea value={pedido} onChange={e => setPedido(e.target.value)} rows={4} placeholder="Descreva o que você precisa…" className="w-full bg-transparent outline-none resize-none placeholder:text-nevoa" />
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <BotaoAnexar accept="video/*,audio/*,image/*,application/pdf" ja={drive} onArquivos={n => setArquivos(a => [...a, ...n])} onDrive={d => setDrive(x => [...x, ...d].slice(0, 10))} />
          <select value={fluxo} onChange={e => setFluxo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm">
            <option value="">Sem fluxo</option>{fluxos.map(f => <option key={f.nome} value={f.nome}>Fluxo: {f.titulo}</option>)}
          </select>
          <span className="flex items-center gap-1 text-xs text-nevoa" title="Nível de edição: 1 limpo (cortes + legenda), 2 dinâmico (+ zoom, clarão, tela final), 3 profissional (+ palavras-chave na tela, ritmo de 4 s, barra, efeitos sonoros, b-roll), lista (3 + capítulos numerados)">Nível:
            {([['padrao', '1 limpo'], ['opiniao', '2 dinâmico'], ['profissional', '3 profissional'], ['lista', 'lista']] as [string, string][]).filter(([n]) => estilos.some(s => s.nome === n)).map(([n, r]) => <button key={n} type="button" onClick={() => setEstilo(n)} className={`rounded-full border px-2.5 py-1 ${estilo === n ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>{r}</button>)}
          </span>
          <select value={estilo} onChange={e => setEstilo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm">
            {estilos.map(s => <option key={s.nome} value={s.nome}>Estilo: {s.nome}{s.montagem?.nivel ? ` (nível ${s.montagem.nivel})` : ''}</option>)}
          </select>
          <SeletorPasta valor={pasta} onChange={setPasta} />
          {comEstilo && <PainelEstilo valor={estiloCfg} onChange={setEstiloCfg} />}
          <button onClick={() => setMarca(!marca)} title="Manda o Editor consultar o manual, o tom de voz e os produtos (marca/) antes de produzir" className={`rounded-full border px-3 py-1.5 text-sm ${marca ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>◆ Ficha de marca{marca ? ' ✓' : ''}</button>
          {FLUXOS_COM_PLANO.includes(fluxo) && <button onClick={() => setAutomatico(!automatico)} title="Sem o chip, o Editor mostra o plano de cenas e espera você aprovar antes de montar (como no Máquina). Com o chip, ele monta direto." className={`rounded-full border px-3 py-1.5 text-sm ${automatico ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>{automatico ? '⚡ Automático (sem aprovar o plano)' : '📋 Aprovar plano de cenas antes'}</button>}
          {vozInfo?.existe && FLUXOS_COM_VOZ.includes(fluxo) && <button onClick={() => setVozThiago(!vozThiago)} title="Narra com a voz clonada (sintética) do Thiago em vez da voz padrão. Ouça e decida na página Voz." className={`rounded-full border px-3 py-1.5 text-sm ${vozThiago ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>🎙 Voz do Thiago{vozThiago ? ' (clonada)' : ''}</button>}
          {modelos.length > 1 && <select value={modelo} onChange={e => setModelo(e.target.value)} title="Quem responde este pedido. Padrão: o modelo configurado decide pelo fluxo (tarefas mecânicas vão sozinhas para Codex ou Gemini quando existem). ✦ Fable em esforço alto: edição mais robusta, gasta bem mais da assinatura. Também vale escrever 'usa o Fable' / 'usa o Opus' / 'usa o Codex' / 'usa o Gemini' no pedido." className={`rounded-full border px-3 py-1.5 text-sm bg-transparent ${modelo !== 'padrao' ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15'}`}>
            {modelos.map(m => <option key={m.id} value={m.id} className="bg-cartao">{m.id === 'padrao' ? `Modelo: automático (${m.rotulo})` : `${m.id === 'fable' ? '✦ ' : ''}${m.rotulo}`}</option>)}
          </select>}
          {mic.suportado && <button onClick={mic.alternar} title="Ditar o pedido" className={`rounded-full border px-3 py-1.5 text-sm ${mic.gravando ? 'border-laranja text-laranja animate-pulse' : 'border-white/15 hover:bg-white/5'}`}>🎤{mic.gravando ? ' ouvindo…' : ''}</button>}
          <button onClick={enviar} disabled={enviando || (!pedido.trim() && arquivos.length === 0 && drive.length === 0 && !recebido)} className="btn-laranja ml-auto px-5 py-2">{enviando ? 'Enviando…' : 'Enviar ➤'}</button>
        </div>
        {recebido && <div className="mt-3 text-sm text-nevoa flex flex-wrap items-center gap-2">
          <span className="text-laranja">Recebido do celular:</span>
          {recebido.arquivos.map(a => <span key={a.nome} className="selo">{a.nome} · {a.tamanho_mb.toFixed(0)} MB</span>)}
          {recebido.arquivos.length === 0 && <span>só texto</span>}
          <button onClick={async () => { try { const fd = new FormData(); fd.append('recebido', recebido.token); fd.append('texto', pedido); const r = await api.novaReferencia(fd); nav(`/referencias`, { state: { nova: r.id } }) } catch (e: any) { setErro(e.message) } }} className="rounded-full border border-laranja/60 text-laranja px-3 py-1">Guardar como referência</button>
          <button onClick={() => { setRecebido(null); nav('/novo', { replace: true }) }} className="ml-1">✕</button></div>}
        {campanha && <div className="mt-3 text-sm text-nevoa flex flex-wrap items-center gap-2"><span className="text-laranja">🎯 Campanha:</span><span className="selo">{campanha.nome}</span><span className="text-xs">a peça já nasce com a etiqueta e o Editor recebe o objetivo e a mensagem-chave</span><button onClick={() => { setCampanha(null); nav('/novo', { replace: true }) }} className="ml-1">✕</button></div>}
        {referencia && <div className="mt-3 text-sm text-nevoa flex flex-wrap items-center gap-2"><span className="text-laranja">Referência:</span><span className="selo">{referencia.titulo}</span>{referencia.status !== 'pronto' && <span>({referencia.status})</span>}<button onClick={() => { setReferencia(null); setFluxo(''); nav('/novo', { replace: true }) }} className="ml-1">✕</button></div>}
        {recebidoErro && <div className="mt-3 text-sm text-red-300">{recebidoErro}</div>}
        {(arquivos.length > 0 || drive.length > 0) && <div className="mt-3 text-sm text-nevoa flex flex-wrap gap-2">
          {arquivos.map((a, i) => <span key={i} className="selo">{a.name} · {(a.size / 1e6).toFixed(0)} MB <button onClick={() => setArquivos(arquivos.filter((_, j) => j !== i))} className="ml-1">✕</button></span>)}
          <ChipsDrive itens={drive} onTirar={i => setDrive(d => d.filter((_, j) => j !== i))} />
          {drive.length > 0 && <span className="text-xs w-full">☁ Os arquivos do Drive são baixados pelo app depois de enviar; o Editor começa quando terminarem.</span>}
          {mb > 1500 && <span className="text-laranja">Arquivos acima de 1,5 GB podem demorar para subir.</span>}
        </div>}
        {progresso !== null && <div className="mt-3"><div className="h-2 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-laranja transition-all" style={{ width: `${progresso}%` }} /></div>
          <div className="text-xs text-nevoa mt-1">{progresso < 100 ? `Enviando… ${progresso}%` : 'Criando o pedido…'}</div></div>}
        {erro && <div className="mt-3 text-sm text-red-300">{erro}</div>}
      </div>
      <p className="text-xs text-nevoa mt-4 text-center">O Editor GS roda na assinatura Claude da Grava Simples. Nada é publicado automaticamente.</p>
      <p className="text-sm text-center mt-3"><Link to="/ajuda" className="text-laranja underline">📱 Como mandar um vídeo direto do celular</Link></p>
    </div>
  )
}
