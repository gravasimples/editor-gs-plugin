import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useParams } from 'react-router-dom'
import { api, STATUS, type CartaoNotion, type Checkpoint, type ConversaDetalhe, type Cortes } from '../api'
import { horas } from '../api'
import Publicar from './Publicar'
import { useMicrofone } from '../microfone'
import { SeletorPasta } from '../Pastas'
import { BotaoAnexar, ChipsDrive } from '../DriveSeletor'
import { MenuConversa } from '../MenuConversa'
import type { DriveItem, EstiloCfg } from '../api'
import { PainelEstilo } from '../PainelEstilo'
import { Md, secoesDe, copiar as copiarTexto, type SecaoTexto } from '../Md'
import { FormEtiquetas } from '../Etiquetas'
import { AvisosMarca } from '../Revisao'
import type { Revisao } from '../api'

const CORES: [string, string][] = [['#F79615', 'laranja (marca)'], ['#FFD400', 'amarelo'], ['#22C55E', 'verde'], ['#38BDF8', 'azul claro'], ['#F472B6', 'rosa'], ['#A78BFA', 'roxo'], ['#FFFFFF', 'branco']]
const GUARDAVEIS = /^(roteiro|descricao|analise|respostas|transcricao|resumo)(-\d+)?$/
/** Mesma regra do gateway (textos.chave_de) só para saber se a seção de uma mensagem antiga é guardável; a chave real vem do gateway. */
function guardavelPorTitulo(t: string): boolean { const n = t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); return /resumo|o que foi feito|roteiro|descri|legenda do post|analise|resposta|transcri/.test(n) && !/hashtag|titulo|gancho|pendencia|arquivo/.test(n) || n === 'legenda' || n === 'copy' }

/** Mensagem do Editor: Markdown; as seções `## ` viram cartões com Copiar e, na entrega mais recente, Guardar como referência. */
function MensagemEditor({ texto, chaves, guardadas, onGuardar, mensagemId, onGuardarAntiga, onNotion }: { texto: string; chaves: Map<string, string> | null; guardadas: Set<string>; onGuardar: ((chave: string, s: SecaoTexto) => void) | null; mensagemId?: string; onGuardarAntiga?: ((mensagemId: string, s: SecaoTexto) => void) | null; onNotion?: ((mensagemId: string, titulo: string) => void) | null }) {
  const { intro, secoes } = secoesDe(texto)
  if (secoes.length === 0) return <Md texto={texto} className="msg text-[15px]" />
  return <div>
    {intro && <Md texto={intro} className="msg text-[15px]" />}
    <div className="grid gap-2 mt-2">{secoes.map(s => { const chave = chaves?.get(s.titulo) || null
      const antiga = !onGuardar && !!onGuardarAntiga && !!mensagemId && guardavelPorTitulo(s.titulo)  // mensagem antiga: o gateway resolve a chave pelo título
      const guardavel = (!!onGuardar && !!chave && GUARDAVEIS.test(chave)) || antiga
      const marca = antiga ? `m:${mensagemId}:${s.titulo}` : chave; const ja = !!marca && guardadas.has(marca)
      return <div key={s.titulo} className="rounded-xl bg-black/30 p-3">
        <div className="flex items-center gap-2 mb-1 flex-wrap"><span className="text-[11px] uppercase tracking-wide text-laranja">{s.titulo}</span>
          <button onClick={() => copiarTexto(s.conteudo)} className="ml-auto text-xs rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">Copiar</button>
          {onNotion && mensagemId && guardavelPorTitulo(s.titulo) && <button onClick={() => onNotion(onGuardar ? 'ultima' : mensagemId, s.titulo)} title="Envia esta seção para o campo Roteiro do pulso de um cartão existente do Notion (só por clique)" className="text-xs rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">Notion</button>}
          {guardavel && <button onClick={() => !ja && (antiga ? onGuardarAntiga!(mensagemId!, s) : onGuardar!(chave!, s))} title={antiga ? 'Versão anterior: grava um .md em referencias/_textos/ com esta seção' : 'Grava um .md em referencias/_textos/ para o Editor usar como exemplo'} className={`text-xs rounded-full border px-2 py-0.5 ${ja ? 'border-green-400/40 text-green-300' : 'border-white/15 hover:bg-white/5'}`}>{ja ? 'Guardado como referência ✓' : antiga ? 'Guardar esta versão como referência' : 'Guardar como referência'}</button>}</div>
        <Md texto={s.conteudo} className="text-sm" /></div> })}</div>
  </div>
}

/** Envio de uma seção para um cartão EXISTENTE do Notion (campo "Roteiro do pulso"): só por clique, nunca cria página. */
function EnviarNotion({ conversaId, secao, mensagemId, cartaoDoPedido, onFechar }: { conversaId: string; secao: string; mensagemId: string; cartaoDoPedido: string | null; onFechar: () => void }) {
  const [q, setQ] = useState(''); const [cartoes, setCartoes] = useState<CartaoNotion[] | null>(null); const [busy, setBusy] = useState(''); const [feito, setFeito] = useState<{ titulo: string | null; url: string | null } | null>(null); const [erro, setErro] = useState('')
  const [modo, setModo] = useState<'acrescentar' | 'substituir'>('acrescentar')
  useEffect(() => { const t = setTimeout(() => { api.notionCartoes(q).then(setCartoes).catch(e => setErro(e.message)) }, 350); return () => clearTimeout(t) }, [q])
  async function enviar(pagina: string) { setBusy(pagina); setErro(''); try { const r = await api.enviarTextoNotion(conversaId, secao, pagina, mensagemId === 'ultima' ? '' : mensagemId, modo); setFeito({ titulo: r.titulo, url: r.url }) } catch (e: any) { setErro(e.message) } finally { setBusy('') } }
  return <div className="mt-2 rounded-xl border border-laranja/40 bg-black/40 p-3 text-sm">
    <div className="flex items-center gap-2 flex-wrap"><span className="font-bold">Enviar "{secao}" para um cartão do Notion</span>
      <select value={modo} onChange={e => setModo(e.target.value as any)} className="bg-black/40 border border-white/15 rounded-full px-2 py-0.5 text-xs"><option value="acrescentar">acrescentar ao campo Roteiro do pulso</option><option value="substituir">substituir o campo</option></select>
      <button onClick={onFechar} className="ml-auto text-xs text-nevoa hover:text-white">fechar</button></div>
    {feito ? <div className="mt-2 text-green-300">Enviado para "{feito.titulo}". {feito.url && <a href={feito.url} target="_blank" rel="noreferrer" className="underline">Abrir no Notion ↗</a>}</div> : <>
      {cartaoDoPedido && <button disabled={!!busy} onClick={() => enviar(cartaoDoPedido)} className="mt-2 rounded-full bg-laranja text-marinho font-bold px-3 py-1 text-xs disabled:opacity-50">{busy === cartaoDoPedido ? 'Enviando…' : 'Enviar para o cartão deste pedido'}</button>}
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="Buscar cartão pelo título (base Mídias › Instagram)" className="mt-2 w-full bg-black/40 border border-white/15 rounded-xl px-3 py-1.5 text-sm" />
      <div className="mt-2 grid gap-1 max-h-48 overflow-auto">{cartoes === null ? <div className="text-nevoa text-xs">…</div> : cartoes.length === 0 ? <div className="text-nevoa text-xs">Nenhum cartão com esse título. O app não cria cartão: crie no Notion e busque de novo.</div> : cartoes.map(c => <button key={c.id} disabled={!!busy} onClick={() => enviar(c.id)} className="text-left rounded-lg px-2 py-1 hover:bg-white/5 disabled:opacity-50"><span className="font-medium">{c.titulo}</span> <span className="text-nevoa text-xs">{c.status || ''} {Array.isArray(c.formato) ? c.formato.join(' ') : ''}</span>{busy === c.id && <span className="text-laranja text-xs"> enviando…</span>}</button>)}</div>
      <div className="text-nevoa text-[11px] mt-2">Escreve só no campo de texto "Roteiro do pulso" do cartão escolhido (o workspace está sem blocos livres). Mudar Status e mover cartão continuam manuais.</div>
    </>}
    {erro && <div className="text-red-300 text-xs mt-2">{erro}</div>}
  </div>
}

function Texto({ t }: { t: string }) {
  const partes = t.split(/(`[^`]+`)/g)
  return <div className="msg text-[15px] leading-relaxed">{partes.map((p, i) => p.startsWith('`') ? <code key={i}>{p.slice(1, -1)}</code> : <span key={i}>{p.replace(/\*\*(.+?)\*\*/g, '$1')}</span>)}</div>
}

export default function ConversaPagina() {
  const { id = '' } = useParams()
  const [c, setC] = useState<ConversaDetalhe | null>(null)
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState('')
  const fim = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const statusAnterior = useRef<string | null>(null)
  const mic = useMicrofone(t => setTexto(p => (p ? p + ' ' : '') + t))
  const [cortes, setCortes] = useState<Cortes | null>(null)
  const [sel, setSel] = useState<string[]>([])
  const [criandoCortes, setCriandoCortes] = useState(false)
  const [canva, setCanva] = useState<{ conectado: boolean } | null>(null)
  const [canvaLinks, setCanvaLinks] = useState<{ design_id: string; edit_url: string; quando: string; arquivo: string }[]>([])
  const [canvaOcupado, setCanvaOcupado] = useState(false)
  const [guardadas, setGuardadas] = useState<Set<string>>(new Set())
  const [estilos, setEstilos] = useState<{ nome: string; legenda: Record<string, any> }[]>([])
  const [estiloSel, setEstiloSel] = useState('padrao'); const [corSel, setCorSel] = useState('')
  useEffect(() => { api.estilos().then(setEstilos).catch(() => {}) }, [])
  async function aplicarEstilo() {
    let nome = estiloSel; const base = estilos.find(s => s.nome === estiloSel); const corBase = (base?.legenda?.cor_destaque || '').toUpperCase()
    if (corSel && corSel.toUpperCase() !== corBase) {
      const rot = CORES.find(([h]) => h === corSel)?.[1].split(' ')[0] || 'cor'; nome = `${estiloSel}-${rot}`
      if (!estilos.some(s => s.nome === nome)) { try { await api.novoEstilo({ nome, base: estiloSel, cor_destaque: corSel }); setEstilos(await api.estilos()) } catch (e: any) { if (!/409|existe/.test(e.message)) { setErro(e.message); return } } }
    }
    await variar(`Daqui em diante use o estilo de legenda \`${nome}\` nesta conversa${corSel ? ` (destaque ${corSel})` : ''}. Refaça a legenda da entrega atual nesse estilo sem mudar os cortes (listar_estilos, gerar_legenda, montar) e entregue em pasta nova com sufixo -${nome}.`)
  }
  useEffect(() => { if (c?.codigo) api.textosGuardados().then(g => setGuardadas(new Set(g.filter(x => x.codigo === c.codigo && x.chave).map(x => x.chave!)))).catch(() => {}) }, [c?.codigo])
  async function guardar(chave: string) { try { await api.guardarTexto(id, chave); setGuardadas(p => new Set([...p, chave])) } catch (e: any) { setErro(e.message) } }
  const [notionAlvo, setNotionAlvo] = useState<{ mensagemId: string; titulo: string } | null>(null)
  async function guardarAntiga(mid: string, s: SecaoTexto) { try { await api.guardarTexto(id, '', '', mid, s.titulo); setGuardadas(p => new Set([...p, `m:${mid}:${s.titulo}`])) } catch (e: any) { setErro(e.message) } }
  useEffect(() => { api.canvaEstado().then(setCanva).catch(() => setCanva({ conectado: false })); if (c?.slug) api.canvaLista(id).then(setCanvaLinks).catch(() => {}) }, [id, c?.slug])
  async function abrirNoCanva(arquivo: string) { setCanvaOcupado(true); setErro(''); try { const r = await api.canvaImportar(id, arquivo, c?.titulo || ''); setCanvaLinks(await api.canvaLista(id)); window.open(r.edit_url, '_blank') } catch (e: any) { setErro(e.message) } finally { setCanvaOcupado(false) } }
  async function aprovar() { if (!confirm('Aprovar esta entrega? Se veio de um cartão do Notion, ele passa para Prontos.')) return; try { const r = await api.aprovar(id, 'Ficou bom.'); setErro(''); setC(await api.conversa(id)); alert(r.notion ? `Aprovado. Notion: ${r.notion}` : 'Aprovado.') } catch (e: any) { setErro(e.message) } }
  useEffect(() => { if (!c?.slug) return; api.cortes(id).then(k => { setCortes(k.pronto ? k : null); if (k.pronto && sel.length === 0) setSel(k.cortes.filter(x => !x.editado && (x.nota || 0) >= 4).map(x => x.id)) }).catch(() => setCortes(null)) }, [id, c?.entregas.length, c?.status])
  async function editarCortes() { if (sel.length === 0) return; if (!confirm(`Criar ${sel.length} pedido(s) de edição, um por corte?`)) return; setCriandoCortes(true); try { await api.editarCortes(id, sel); setSel([]); setCortes(await api.cortes(id)); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } finally { setCriandoCortes(false) } }
  const [modelos, setModelos] = useState<{ id: string; rotulo: string; disponivel: boolean }[]>([])
  useEffect(() => { api.estado().then(e => setModelos((e?.modelos || []).filter((m: any) => m.disponivel))).catch(() => {}) }, [])
  const [estiloCfg, setEstiloCfg] = useState<EstiloCfg | null>(null)  // painel Estilo do criativo (fase D)
  async function refazerComEstilo(cfg: EstiloCfg) { try { const { texto: t } = await api.estiloCriativoTexto(cfg); await api.mensagem(id, `Refaça a edição com este estilo, mantendo o conteúdo e o que já está bom (entregue com sufixo -v2 e diga o que mudou). ${t}`); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } }
  async function continuarNova() { try { const r = await api.continuar(id); nav('/novo', { state: { pedido: r.pedido, pasta: r.pasta, fluxo: r.fluxo, estilo: r.estilo } }) } catch (e: any) { setErro(e.message) } }
  async function variar(t: string, modelo = '') { try { await api.mensagem(id, t, modelo); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } }
  useEffect(() => {
    let vivo = true
    const carregar = () => api.conversa(id).then(d => { if (vivo) setC(d) }).catch(e => setErro(e.message))
    carregar(); const t = setInterval(carregar, 5000); return () => { vivo = false; clearInterval(t) }
  }, [id])
  useEffect(() => { fim.current?.scrollIntoView({ block: 'end' }) }, [c?.mensagens.length])
  useEffect(() => {
    if (!c) return
    const ant = statusAnterior.current; statusAnterior.current = c.status
    if (ant && ant !== c.status && (c.status === 'in_review' || c.status === 'done') && 'Notification' in window && Notification.permission === 'granted') {
      try { new Notification('Editor GS', { body: `Entrega pronta: ${c.titulo}`, icon: '/icone-192.png' }) } catch {}
    }
  }, [c?.status])
  useEffect(() => { if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission().catch(() => {}) }, [])
  async function decidir(iid: string, acao: 'aceitar' | 'recusar') { try { await api.decidir(id, iid, acao, acao === 'recusar' ? texto : ''); setTexto(''); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } }
  async function cancelar() { if (!confirm('Cancelar este pedido?')) return; try { await api.cancelar(id); nav('/') } catch (e: any) { setErro(e.message) } }
  const [parando, setParando] = useState(false)
  async function parar() { setParando(true); try { await api.parar(id); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } finally { setParando(false) } }
  async function retomar() { setParando(true); try { await api.retomar(id); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } finally { setParando(false) } }
  // ↶ Desfazer (10/11/2026): volta a pasta de entrega ao checkpoint tirado antes de uma rodada do Editor; só por clique, nunca com rodada em andamento
  const [ckps, setCkps] = useState<Checkpoint[] | null>(null); const [desfazendo, setDesfazendo] = useState(false); const [aviso, setAviso] = useState('')
  async function abrirDesfazer() { setErro(''); setAviso(''); try { setCkps((await api.checkpoints(id)).itens) } catch (e: any) { setErro(e.message) } }
  async function desfazer(k: Checkpoint) {
    const quando = new Date(k.quando).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
    if (!confirm(`Voltar a entrega ao estado ${k.rodada ? `de antes da rodada ${k.rodada}` : `do checkpoint ${k.n}`} (${quando}, ${k.resumo})? O que existe agora fica guardado como um checkpoint novo.`)) return
    setDesfazendo(true); setErro('')
    try { const r = await api.desfazer(id, k.n); setAviso(r.mensagem); setCkps(null); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } finally { setDesfazendo(false) }
  }
  const [anexos, setAnexos] = useState<File[]>([]); const [drive, setDrive] = useState<DriveItem[]>([]); const [enviando, setEnviando] = useState(false)
  const [notionEscrita, setNotionEscrita] = useState(false); const [revisao, setRevisao] = useState<Revisao | null>(null)
  useEffect(() => { api.estado().then(e => setNotionEscrita(!!e?.notion_escrita)).catch(() => {}) }, [])
  useEffect(() => { if (c && !(c.executando || c.editor_status === 'running') && c.slug) api.revisaoMarca(id).then(setRevisao).catch(() => setRevisao(null)) }, [id, c?.atualizado, c?.executando])
  const [cenaArquivo, setCenaArquivo] = useState<number | null>(null); const inputCena = useRef<HTMLInputElement>(null)
  async function arquivoNaCena(f: File) { if (cenaArquivo == null) return; const n = cenaArquivo; setCenaArquivo(null); try { await api.mensagem(id, `Use este arquivo como visual da cena ${n} do plano (mantenha a fala; remonte o vídeo).`, '', [f]); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } }
  async function fecharTitulo() {
    if (!confirm('Pedir ao Editor o título, a descrição do post, as hashtags e o gancho desta entrega? O vídeo não muda.')) return
    setEnviando(true); setErro('')
    try { await api.mensagem(id, 'Feche o título e a descrição do post desta entrega, sem refazer o vídeo nem gerar arquivos novos: `## Título` (YouTube, até 70 caracteres), `## Descrição do post` (Instagram, na voz do Thiago, sem preço, oferta ou número de alunos), `## Hashtags` (até 8) e `## Gancho` (uma linha). Responda só com essas seções.', '', []); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } finally { setEnviando(false) }
  }
  async function enviar() { if (!texto.trim() && anexos.length === 0 && drive.length === 0) return; const t = texto; const fs = anexos; const dv = drive; setTexto(''); setAnexos([]); setDrive([]); setEnviando(true); try { await api.mensagem(id, t, '', fs, dv); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message); setTexto(t); setAnexos(fs); setDrive(dv) } finally { setEnviando(false) } }
  if (!c) return <div className="p-8 text-nevoa">{erro || 'Carregando…'}</div>
  const principais = c.entregas.filter(e => e.principal && e.tipo === 'video')
  const imagens = c.entregas.filter(e => e.tipo === 'imagem' && e.nome !== 'capa.png')
  const capa = c.entregas.find(e => e.nome === 'capa.png')
  const outros = c.entregas.filter(e => !(e.principal && e.tipo === 'video') && !['relatorio.md', 'post.md', 'capa.png', 'capcut.json'].includes(e.nome))
  const rotulos: Record<string, string> = { descricao: 'Descrição do post', hashtags: 'Hashtags', titulo: 'Título (YouTube)', gancho: 'Gancho' }
  const copiar = (t: string) => navigator.clipboard?.writeText(t)
  const chaves = new Map((c.textos || []).map(s => [s.titulo, s.chave]))  // título → chave do gateway (entrega em texto mais recente)
  const ultimaEntrega = [...c.mensagens].reverse().find(m => m.autor === 'editor' && secoesDe(m.texto).secoes.length > 0)?.id
  const planoSec = [...c.mensagens].reverse().map(m => m.autor === 'editor' ? secoesDe(m.texto).secoes.find(s => /plano de cenas/i.test(s.titulo)) : undefined).find(Boolean)
  const planoCenas = planoSec ? planoSec.conteudo.split('\n').map(l => /^\s*(\d+)[.)]\s+(.*)$/.exec(l)).filter(Boolean).map(m => ({ n: Number(m![1]), texto: m![2].trim() })) : []
  const editando = c.executando || c.editor_status === 'running'
  const ROTULO: Record<string, string> = Object.fromEntries(modelos.map(m => [m.id, m.rotulo]))
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col min-h-screen">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-xl truncate">{c.titulo}</h2>
        <span className="selo">{c.codigo}</span>
        {c.modelo && <span className={`text-xs rounded-full px-3 py-1 ${c.modelo.id === 'fable' ? 'bg-laranja/15 text-laranja' : 'bg-white/10 text-nevoa'}`} title="Modelo do agente que responde neste pedido. Para trocar: botões abaixo ou escreva 'usa o Fable' / 'usa o Codex' / 'usa o Gemini' / 'volta para o Opus' na mensagem.">{c.modelo.id === 'fable' ? '✦ ' : ''}{c.modelo.rotulo}</span>}
        {c.economia && <span className="text-xs rounded-full px-3 py-1 bg-laranja/15 text-laranja" title={`Estimativa pelo fluxo ${c.economia.fluxo}: tempo fixo + minutos por minuto de vídeo ou por slide/página`}>≈ {horas(c.economia.minutos)} economizados</span>}
        {c.trabalho && <span className="text-xs rounded-full px-3 py-1 bg-white/10 text-nevoa" title="Soma das rodadas do Editor neste pedido (fila e espera por você não contam)">⏱ o Editor trabalhou {c.trabalho.minutos < 1 ? 'menos de 1 min' : `${Math.round(c.trabalho.minutos)} min`}{c.trabalho.rodadas > 1 ? ` em ${c.trabalho.rodadas} rodadas` : ''}</span>}
        <span className={`text-xs rounded-full px-3 py-1 ${editando ? 'bg-laranja/20 text-laranja' : 'bg-white/10 text-nevoa'}`}>{editando ? 'Editor trabalhando…' : (STATUS[c.status] || c.status)}</span>
        <SeletorPasta valor={c.pasta || ''} onChange={async p => { try { await api.moverPasta(id, p); setC(await api.conversa(id)) } catch (e: any) { setErro(e.message) } }} className="text-xs py-1" />
        <MenuConversa c={c} onMudou={async () => { try { setC(await api.conversa(id)) } catch {} }} onExcluida={() => nav('/')} className="text-lg" />
        {!editando && c.mensagens.length >= 3 && <button onClick={continuarNova} title="Abre um pedido novo já com o resumo do que foi feito aqui e os arquivos entregues (conversa longa fica lenta e cara para o Editor reler)" className={`text-xs rounded-full border px-3 py-1 ${c.mensagens.length >= 8 ? 'border-laranja/60 text-laranja hover:bg-laranja/10' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>↪ Continuar numa conversa nova</button>}
        {editando && <button onClick={parar} disabled={parando} title="Interrompe a edição agora e deixa o pedido em pausa; o que já foi gerado fica" className="ml-auto rounded-full border border-red-400/60 text-red-300 px-3 py-1 text-xs hover:bg-red-500/10 disabled:opacity-40">{parando ? 'Parando…' : '■ Parar'}</button>}
        {!editando && c.status === 'blocked' && <button onClick={retomar} disabled={parando} title="Devolve o pedido à fila do Editor; ele continua de onde parou" className="ml-auto rounded-full border border-laranja/60 text-laranja px-3 py-1 text-xs hover:bg-laranja/10 disabled:opacity-40">{parando ? 'Retomando…' : '▶ Retomar'}</button>}
        {!editando && c.slug && <button onClick={() => (ckps ? setCkps(null) : abrirDesfazer())} title="Volta a pasta da entrega ao estado de antes de uma rodada do Editor (checkpoint tirado automaticamente antes de cada rodada)" className={`${c.status === 'blocked' || (c.status === 'done' || c.status === 'cancelled') ? '' : 'ml-auto '}text-xs rounded-full border border-white/15 text-nevoa px-3 py-1 hover:bg-white/5`}>↶ Desfazer</button>}
        {c.status !== 'done' && c.status !== 'cancelled' && <button onClick={cancelar} className="text-xs text-nevoa hover:text-red-300">Cancelar pedido</button>}
      </div>
      {aviso && <div className="mt-3 rounded-xl border border-green-400/30 bg-green-400/5 px-4 py-2 text-xs text-green-300 flex items-center gap-2"><span className="flex-1">{aviso}</span><button onClick={() => setAviso('')} className="text-nevoa hover:text-white">fechar</button></div>}
      {ckps && <div className="mt-3 rounded-xl border border-white/15 bg-black/30 px-4 py-3 text-xs">
        <div className="flex items-center gap-2 flex-wrap"><span className="font-bold text-sm">↶ Desfazer uma rodada</span><span className="text-nevoa">Cada rodada do Editor começa com um checkpoint da pasta de entrega (até 5). Voltar não apaga nada de vez: o estado atual vira um checkpoint novo.</span><button onClick={() => setCkps(null)} className="ml-auto text-nevoa hover:text-white">fechar</button></div>
        {ckps.length === 0 ? <div className="text-nevoa mt-2">Nenhum checkpoint ainda: a pasta desta entrega só ganha checkpoint a partir da segunda rodada do Editor.</div>
          : <div className="grid gap-1 mt-2">{ckps.map(k => <div key={k.n} className="flex items-center gap-3 rounded-lg bg-white/5 px-3 py-1.5 flex-wrap">
            <span className="selo">#{k.n}</span>
            <span className="font-medium">{k.rodada ? `antes da rodada ${k.rodada}` : (k.motivo || 'checkpoint')}</span>
            <span className="text-nevoa">{new Date(k.quando).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })} · {k.resumo}</span>
            <button onClick={() => desfazer(k)} disabled={desfazendo} className="ml-auto rounded-full border border-laranja/60 text-laranja px-3 py-0.5 hover:bg-laranja/10 disabled:opacity-40">{desfazendo ? '…' : 'Voltar a este'}</button>
          </div>)}</div>}
      </div>}
      {(c.reservas || []).length > 0 && <div className="mt-3 rounded-xl border border-laranja/30 bg-laranja/5 px-4 py-2 text-xs text-nevoa">
        {c.reservas!.map((r, i) => <div key={i}><span className="text-laranja">Reserva automática</span> · {new Date(r.quando).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}: o {ROTULO[r.de] || r.de} parou ({r.motivo}); o pedido passou para o {ROTULO[r.para] || r.para}.</div>)}
      </div>}
      {c.status === 'blocked' && !editando && <div className="mt-3 rounded-xl border border-red-400/30 bg-red-400/5 px-4 py-2 text-xs text-nevoa">O agente desistiu deste pedido depois das tentativas automáticas. Escreva uma mensagem abaixo (ex.: "tente de novo") ou use "Continuar com o…" para reabrir com outro modelo.</div>}
      <div className="flex-1 flex flex-col gap-3 mt-5">
        {c.mensagens.map(m => <div key={m.id} className={`rounded-2xl px-4 py-3 ${m.autor === 'voce' ? 'self-end bg-azul/30 max-w-[92%]' : 'self-start cartao max-w-full w-full sm:max-w-[96%]'}`}>
          <div className="text-[11px] text-nevoa mb-1">{m.autor === 'voce' ? 'Você' : m.autor === 'app' ? 'Editor GS · aviso do app' : 'Editor GS'} · {m.quando ? new Date(m.quando).toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : ''}</div>
          {m.autor === 'editor' ? <><MensagemEditor texto={m.texto} chaves={m.id === ultimaEntrega ? chaves : null} guardadas={guardadas} onGuardar={m.id === ultimaEntrega ? guardar : null} mensagemId={m.id} onGuardarAntiga={m.id !== ultimaEntrega && m.id !== 'pedido' ? guardarAntiga : null} onNotion={notionEscrita ? (mid, titulo) => setNotionAlvo({ mensagemId: mid, titulo }) : undefined} />{notionAlvo && (notionAlvo.mensagemId === m.id || (notionAlvo.mensagemId === 'ultima' && m.id === ultimaEntrega)) && <EnviarNotion conversaId={id} secao={notionAlvo.titulo} mensagemId={notionAlvo.mensagemId} cartaoDoPedido={c.notion_page || null} onFechar={() => setNotionAlvo(null)} />}</> : <Texto t={m.texto} />}</div>)}
        {editando && <div className="self-start cartao px-4 py-3 text-sm text-nevoa animate-pulse">Pensando e editando… o Editor avisa aqui quando terminar.</div>}
        {(c.interacoes || []).map(it => <div key={it.id} className="self-start cartao p-4 border border-laranja/40 max-w-[92%]">
          <div className="text-[11px] uppercase tracking-wide text-laranja mb-1">O Editor precisa da sua decisão</div>
          <div className="font-bold">{it.titulo}</div>
          {it.resumo && <div className="text-sm text-nevoa mt-1 msg">{it.resumo}</div>}
          {it.pergunta && <div className="text-sm mt-2 msg">{it.pergunta}</div>}
          <div className="flex gap-2 mt-3"><button onClick={() => decidir(it.id, 'aceitar')} className="btn-laranja px-4 py-1.5 text-sm">Aprovar</button>
            <button onClick={() => decidir(it.id, 'recusar')} className="rounded-full border border-white/15 px-4 py-1.5 text-sm hover:bg-white/5">Recusar (escreva o motivo abaixo)</button></div>
        </div>)}
        {cortes && <div className="cartao p-4 mt-2 border border-laranja/30">
          <div className="flex items-center gap-2 flex-wrap"><div className="font-bold">Cortes propostos</div><span className="text-xs text-nevoa">{cortes.cortes.length} cortes · origem {cortes.tipo_origem || ''}{cortes.duracao_s ? ` · ${Math.round(cortes.duracao_s / 60)} min` : ''}</span>
            <button onClick={editarCortes} disabled={criandoCortes || sel.length === 0} className="btn-laranja ml-auto px-4 py-1.5 text-sm">{criandoCortes ? 'Criando…' : `Editar os escolhidos (${sel.length})`}</button></div>
          <div className="grid gap-2 mt-3">{cortes.cortes.map(k => <label key={k.id} className={`flex gap-3 rounded-xl p-3 text-sm ${k.editado ? 'bg-white/5 opacity-70' : sel.includes(k.id) ? 'bg-laranja/10 ring-1 ring-laranja/50' : 'bg-black/30'}`}>
            <input type="checkbox" disabled={!!k.editado} checked={sel.includes(k.id)} onChange={e => setSel(e.target.checked ? [...sel, k.id] : sel.filter(x => x !== k.id))} className="mt-1 accent-[#F79615]" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap"><span className="selo">{k.id}</span><span className="font-bold">{k.titulo || k.gancho}</span>{k.nota != null && <span className="text-laranja text-xs">{'★'.repeat(Math.max(0, Math.min(5, Math.round(k.nota))))}</span>}<span className="text-xs text-nevoa">{Math.floor(k.inicio / 60)}:{String(Math.floor(k.inicio % 60)).padStart(2, '0')} → {Math.floor(k.fim / 60)}:{String(Math.floor(k.fim % 60)).padStart(2, '0')} · {Math.round(k.duracao)} s{k.tipo ? ` · ${k.tipo}` : ''}</span></div>
              {k.gancho && k.titulo && <div className="text-nevoa mt-1">Gancho: “{k.gancho}”</div>}
              {k.motivo && <div className="text-nevoa text-xs mt-1">{k.motivo}{k.tema ? ` · ${k.tema}` : ''}</div>}
              {k.pessoas && <div className="text-xs text-laranja mt-1">Aparece: {k.pessoas} (precisa de autorização para publicar)</div>}
              {k.editado && (k.editado.codigo === 'kit' ? <span className="text-xs text-laranja">Já editado neste kit</span> : <a href={`/c/${k.editado.issue_id}`} className="text-xs text-laranja">Em edição: {k.editado.codigo}</a>)}
            </div></label>)}</div>
        </div>}
        {imagens.length > 0 && <div className="cartao p-4 mt-2">
          <div className="font-bold mb-3">Imagens ({imagens.length})</div>
          {c.entregas.some(e => e.nome.startsWith('carrossel') && (e.nome.endsWith('.pptx') || e.nome.endsWith('.pdf'))) && <div className="mb-3 rounded-xl bg-black/30 p-3 text-sm flex flex-wrap items-center gap-3">
            <div><div className="text-[11px] uppercase tracking-wide text-nevoa">Editável para o Canva</div><div className="font-bold">{c.entregas.filter(e => e.nome.endsWith('.pptx') || e.nome.endsWith('.pdf')).map(e => e.nome).join(' · ')}</div><div className="text-nevoa text-xs">Texto, selos, botões e fotos como camadas. No Canva: Criar design → Importar arquivo, ou arraste o arquivo na página inicial.</div></div>
            {c.entregas.some(e => e.nome.endsWith('.pptx')) && <a href={c.entregas.find(e => e.nome.endsWith('.pptx'))!.url} download className="ml-auto rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">Baixar PPTX</a>}
            {c.entregas.some(e => e.nome.endsWith('.pdf')) && <a href={c.entregas.find(e => e.nome.endsWith('.pdf'))!.url} download className="rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">Baixar PDF (fontes embutidas)</a>}
            {canva?.conectado ? <button onClick={() => abrirNoCanva(c.entregas.some(e => e.nome.endsWith('.pptx')) ? c.entregas.find(e => e.nome.endsWith('.pptx'))!.nome : c.entregas.find(e => e.nome.endsWith('.pdf'))!.nome)} disabled={canvaOcupado} className="btn-laranja px-4 py-1.5">{canvaOcupado ? 'Importando…' : 'Abrir no Canva'}</button> : <a href="/estilos" className="rounded-full border border-white/15 px-4 py-1.5 hover:bg-white/5" title="Conecte o Canva uma vez em Estilos para abrir direto">Conectar o Canva</a>}
            {canvaLinks.length > 0 && <div className="w-full text-xs text-nevoa">No Canva: {canvaLinks.slice().reverse().map(l => <a key={l.design_id} href={l.edit_url} target="_blank" rel="noreferrer" className="text-laranja mr-3">{l.arquivo} · {new Date(l.quando).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</a>)}</div>}
          </div>}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">{imagens.map(e => <a key={e.caminho} href={e.url} target="_blank" rel="noreferrer" className="block"><img src={e.url} alt={e.nome} className="w-full rounded-xl bg-black/40" loading="lazy" /><div className="text-xs text-nevoa mt-1 truncate">{e.nome}</div></a>)}</div>
          <div className="mt-3"><Publicar c={c} /></div>
        </div>}
        {principais.length > 0 && <div className="cartao p-4 mt-2">
          <div className="font-bold mb-3">Entrega</div>
          <div className="flex flex-wrap gap-4">
            {principais.map(e => <div key={e.caminho} className="w-full sm:w-[calc(50%-8px)]">
              <video src={e.url} controls playsInline preload="metadata" className="w-full rounded-xl bg-black max-h-[70vh]" />
              <div className="flex items-center gap-2 mt-2 text-sm"><span className="truncate">{e.nome}</span><span className="text-nevoa">{e.tamanho_mb} MB</span>
                <a href={e.url} download className="ml-auto rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Baixar</a></div>
            </div>)}
          </div>
          {capa && <div className="mt-4 flex items-center gap-3"><img src={capa.url} alt="Capa" className="w-24 rounded-lg" /><div className="text-sm"><div className="font-bold">Capa</div><a href={capa.url} download className="text-laranja">Baixar capa</a></div></div>}
          {c.capcut && <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm flex flex-wrap items-center gap-3">
            <div><div className="text-[11px] uppercase tracking-wide text-nevoa">Projeto editável no CapCut</div>
              <div className="font-bold">{c.capcut.nome}</div><div className="text-nevoa text-xs">{c.capcut.n_segmentos} cortes · {c.capcut.n_legendas} legendas · aparece na lista de projetos do CapCut</div></div>
            <button onClick={() => api.abrirCapcut().catch(e => setErro(e.message))} className="ml-auto rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">Abrir o CapCut</button>
          </div>}
          {c.post && c.post_origem === 'arquivo' && <div className="mt-4 grid sm:grid-cols-2 gap-3">
            {Object.entries(c.post).map(([k, v]) => <div key={k} className="rounded-xl bg-black/30 p-3 text-sm">
              <div className="flex items-center mb-1"><span className="text-[11px] uppercase tracking-wide text-nevoa">{rotulos[k] || k}</span>
                <button onClick={() => copiar(v)} className="ml-auto text-xs rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">Copiar</button></div>
              <div className="msg whitespace-pre-wrap">{v}</div></div>)}
          </div>}
          <Publicar c={c} />
          {!editando && <div className="mt-3 flex flex-wrap items-center gap-2 text-xs"><button onClick={fecharTitulo} disabled={enviando} title="Pede ao Editor só o título, a descrição, as hashtags e o gancho desta entrega, sem refazer o vídeo" className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10 disabled:opacity-40">✍ Fechar título e descrição</button><span className="text-nevoa">só o texto do post, sem mexer no vídeo</span></div>}
          {outros.length > 0 && <div className="mt-4 text-sm flex flex-wrap gap-2">{outros.map(e => <a key={e.caminho} href={e.url} download className="selo hover:bg-azul/40">{e.nome}</a>)}</div>}
          {c.relatorio && <details className="mt-4"><summary className="cursor-pointer text-sm text-laranja">Relatório do Editor</summary><pre className="whitespace-pre-wrap text-xs text-nevoa mt-2 font-[Inter]">{c.relatorio}</pre></details>}
          {planoCenas.length > 0 && <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm">
            <div className="flex items-center gap-2 flex-wrap"><div className="text-[11px] uppercase tracking-wide text-nevoa">Plano de cenas ({planoCenas.length})</div>
              <button onClick={() => setTexto('Altere o plano de cenas: ')} className="ml-auto rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">Pedir alterações no plano</button></div>
            <div className="grid gap-1 mt-2">{planoCenas.map(k => <div key={k.n} className="flex flex-wrap items-start gap-2 rounded-lg bg-white/5 px-2 py-1.5">
              <span className="text-laranja font-bold w-5">{k.n}</span><span className="flex-1 text-xs text-white/90 min-w-[12rem]">{k.texto}</span>
              <button onClick={() => setTexto(`Refaça só a cena ${k.n}: `)} className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] hover:bg-white/5" title="Muda só esta cena (texto ou visual); as outras narrações vêm do cache">Refazer só esta</button>
              <button onClick={() => { setCenaArquivo(k.n); inputCena.current?.click() }} className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] hover:bg-white/5" title="Anexa um print, foto ou vídeo seu como visual desta cena">Usar meu arquivo</button>
            </div>)}</div>
            <input ref={inputCena} type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) arquivoNaCena(f) }} />
            <div className="text-nevoa text-[11px] mt-2">Aprovar ou recusar o plano: cartão laranja "O Editor precisa da sua decisão" acima (recusa pede o motivo na caixa). Sem aprovação, nada é montado, a não ser que o pedido tenha o chip Automático.</div>
          </div>}
          {revisao && !editando && <div className={`mt-4 rounded-xl p-3 text-sm ${revisao.ok ? 'bg-black/30' : 'bg-black/30 border border-laranja/30'}`}>
            <div className="flex items-center gap-2 flex-wrap"><div className="text-[11px] uppercase tracking-wide text-nevoa">Revisor de marca</div><AvisosMarca r={revisao} compacto /><span className="text-[11px] text-nevoa ml-auto">regras do manual; aponta, não corrige</span></div>
            {!revisao.ok && <div className="mt-2"><AvisosMarca r={revisao} /></div>}
          </div>}
          {c.peca && c.slug && <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm">
            <div className="flex items-center gap-2 flex-wrap"><div className="text-[11px] uppercase tracking-wide text-nevoa">Etiquetas da peça</div><button onClick={() => nav(`/pecas/${c.slug}`)} className="ml-auto text-xs text-laranja hover:underline">abrir ficha da peça</button></div>
            <div className="mt-2"><FormEtiquetas slug={c.slug} inicial={c.peca} onSalvo={async () => setC(await api.conversa(id))} /></div>
          </div>}
          {(c.textos || []).some(s => s.chave === 'gravar' || s.chave.startsWith('roteiro')) && <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm flex flex-wrap items-center gap-2">
            <div className="text-[11px] uppercase tracking-wide text-nevoa">Gravar com a voz do Thiago</div>
            <button onClick={() => nav(`/teleprompter?c=${id}&secao=${(c.textos || []).some(s => s.chave === 'gravar') ? 'gravar' : 'roteiro'}`)} className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 hover:bg-laranja/10">📜 Abrir teleprompter</button>
            <span className="text-nevoa text-xs">Rola o texto na tela (velocidade, letra, espelho, tela cheia). Depois de gravar, anexe o take aqui embaixo e peça a edição.</span>
          </div>}
          {!editando && c.slug && <div className="mt-4 rounded-xl bg-black/30 p-3 text-sm">
            <div className="text-[11px] uppercase tracking-wide text-nevoa mb-2">Quer uma variação deste vídeo?</div>
            <div className="flex flex-wrap gap-2">
              {[['Versão curta de 20 s', `Faça uma versão curta de até 20 s a partir de saida/${c.slug}/ (reaproveite cortado.mp4, a EDL e as palavras; escolha o trecho com o gancho mais forte e feche numa frase completa). Entregue em pasta nova com sufixo -curta, com capa e a legenda do post na mensagem.`], ['Outro gancho', `Faça uma variação de saida/${c.slug}/ começando por outro gancho (outra frase de impacto e outro primeiro corte), mantendo o resto. Entregue em pasta nova com sufixo -gancho2.`], ['Legenda em outro estilo', `Refaça o final 9:16 de saida/${c.slug}/ com a legenda no estilo destaque-pop (listar_estilos) sem mudar os cortes. Entregue em pasta nova com sufixo -pop.`], ['Só 16:9 recortado no rosto', `Gere uma versão 16:9 de saida/${c.slug}/ reenquadrada no rosto (reenquadrar) em vez de fundo desfocado. Entregue em pasta nova com sufixo -169.`], ['Dublado em inglês', `Dube saida/${c.slug}/ para o inglês no fluxo dublagem: traduza a fala (reaproveite o SRT ou as palavras da entrega), narre com voz sintética sobre o vídeo-base sem legenda (cortado.mp4), legenda karaokê em inglês, e monte final_9x16_en_dub.mp4 na mesma pasta, sem cortar nada.`], ['Transcrição completa', `Transcreva o vídeo de saida/${c.slug}/ (cortado.mp4; se não houver, o final sem legenda ou o bruto em entrada/) e entregue só o texto em ## Transcrição, com parágrafos por assunto e pontuação, sem editar nada nem gerar vídeo novo.`], ['Legenda em inglês', `Traduza a legenda de saida/${c.slug}/ para o inglês no fluxo traduzir-legenda: reaproveite o SRT ou as palavras da entrega (vídeo-base cortado.mp4, sem legenda), gere legenda-en.srt e o ASS com legenda_de_srt e monte final_9x16_en.mp4 na mesma pasta, sem cortar nada.`]].map(([r, t]) => <button key={r} onClick={() => variar(t)} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">{r}</button>)}
            </div>
          </div>}
          <div className="mt-4 flex flex-wrap gap-2 text-sm">
            <button onClick={aprovar} className="rounded-full border border-green-400/60 text-green-300 px-3 py-1.5 hover:bg-green-400/10">✓ Aprovar entrega</button>
            <button onClick={() => setTexto('Ficou bom. ')} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">👍 Ficou bom</button>
            <button onClick={() => setTexto('Faltou algo: ')} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">👎 Faltou algo</button>
            {c.modelo?.id !== 'fable' && modelos.some(m => m.id === 'fable') && <button onClick={() => variar('Refaça esta entrega com uma edição mais robusta: revise cortes, ritmo, ganchos, legenda e acabamento; entregue em pasta nova com sufixo -fable e explique o que mudou.', 'fable')} title="Troca o agente deste pedido para o Claude Fable 5.1 em esforço alto (gasta bem mais da assinatura que o padrão)" className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 hover:bg-laranja/10">✦ Refazer com mais esforço</button>}
            {c.modelo?.id !== 'padrao' && <button onClick={() => variar('Continue este pedido no modelo padrão.', 'padrao')} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">Voltar para o padrão</button>}
            {modelos.filter(m => m.id !== 'padrao' && m.id !== 'fable' && m.id !== c.modelo?.id).map(m => <button key={m.id} onClick={() => variar(`Continue este pedido daqui em diante com o ${m.rotulo}: leia a conversa e os arquivos já entregues antes de agir.`, m.id)} title={`Passa este pedido para o agente ${m.rotulo} (outra cota, bom para tarefas mecânicas)`} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">Continuar com o {m.rotulo.split(' (')[0]}</button>)}
            <button onClick={() => setTexto('Pedir ajuste: ')} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">✎ Pedir ajuste</button>
          </div>
        </div>}
        <div ref={fim} />
      </div>
      {!editando && c.slug && principais.length > 0 && <div className="mt-4 flex flex-wrap items-center gap-2 text-xs"><span className="text-nevoa">Estilo da legenda:</span>
        <select value={estiloSel} onChange={e => setEstiloSel(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1">{estilos.map(s => <option key={s.nome} value={s.nome}>{s.nome}</option>)}</select>
        <span className="text-nevoa ml-1">Cor:</span>{CORES.map(([h, n]) => <button key={h} title={n} onClick={() => setCorSel(corSel === h ? '' : h)} className={`w-6 h-6 rounded-full border-2 ${corSel === h ? 'border-white' : 'border-transparent'}`} style={{ background: h }} />)}
        <button onClick={aplicarEstilo} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">Refazer a legenda assim</button></div>}
      <div className="sticky bottom-16 md:bottom-4 mt-6 cartao p-3 flex flex-wrap gap-2 items-end shadow-xl">
        {(anexos.length > 0 || drive.length > 0) && <div className="w-full flex flex-wrap gap-2 text-xs">{anexos.map((f, i) => <span key={i} className="selo">{f.name} · {(f.size / 1e6).toFixed(1)} MB <button onClick={() => setAnexos(a => a.filter((_, k) => k !== i))} className="ml-1 text-nevoa hover:text-red-300">×</button></span>)}<ChipsDrive itens={drive} onTirar={i => setDrive(d => d.filter((_, k) => k !== i))} /></div>}
        {c.drive?.estado === 'baixando' && <div className="w-full text-xs text-laranja animate-pulse">☁ Baixando do Drive: {c.drive.nomes.join(', ')}. A mensagem vai para o Editor quando terminar.</div>}
        {c.drive?.estado === 'erro' && <div className="w-full text-xs text-red-300">☁ Não baixou do Drive: {c.drive.erro}</div>}
        <textarea value={texto} onChange={e => setTexto(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar() } }} rows={2} placeholder="Responda ou peça um ajuste…" className="flex-1 bg-transparent outline-none resize-none placeholder:text-nevoa" />
        {mic.suportado && <button onClick={mic.alternar} title="Ditar" className={`rounded-full border px-3 py-2 text-sm ${mic.gravando ? 'border-laranja text-laranja animate-pulse' : 'border-white/15 hover:bg-white/5'}`}>🎤</button>}
        {!editando && c.slug && principais.length > 0 && <PainelEstilo valor={estiloCfg} onChange={setEstiloCfg} onAplicar={refazerComEstilo} />}
        <BotaoAnexar rotulo="📎" className="rounded-full border border-white/15 px-3 py-2 hover:bg-white/5" ja={drive} onArquivos={n => setAnexos(a => [...a, ...n])} onDrive={d => setDrive(x => [...x, ...d].slice(0, 10))} />
        {editando ? <button onClick={parar} disabled={parando} title="Parar a edição agora (pausa; Retomar continua)" className="rounded-full border border-red-400/60 text-red-300 px-4 py-2 hover:bg-red-500/10 disabled:opacity-40">{parando ? '…' : '■ Parar'}</button> : null}
        <button onClick={enviar} disabled={enviando || (!texto.trim() && anexos.length === 0 && drive.length === 0)} className="btn-laranja px-4 py-2">{enviando ? 'Enviando…' : 'Enviar'}</button>
      </div>
      {erro && <div className="text-xs text-red-300 mt-2">{erro}</div>}
    </div>
  )
}
