import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Armazenamento, type Avulso, type Conversa, type Entrega, type Uso, type UsoEntrega } from '../api'
import { horas } from '../api'
import { Icone } from '../Icones'
import { Carga, Esqueleto, ha, useCarga } from '../Estados'
import { Previa, TIPOS, midiaDe, tipoDe } from '../Previa'

type Pasta = { slug: string; itens: Entrega[]; uso?: UsoEntrega; conversa?: string | null; pasta?: string | null; teste?: boolean }
const USOS = [['todos', 'Todas'], ['postado', 'Postadas ou agendadas'], ['drive', 'Só no Drive'], ['nao-usado', 'Ainda não usadas']] as const
type FiltroUso = typeof USOS[number][0]
const passaUso = (p: Pasta, f: FiltroUso) => f === 'todos' || (f === 'postado' && p.uso?.rotulo === 'postado ou agendado') || (f === 'drive' && p.uso?.rotulo === 'no Drive') || (f === 'nao-usado' && (!p.uso || p.uso.rotulo === 'ainda não usado'))
const semAcento = (t: string) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
/** "2026-11-15-reproduzir-no-editor" → "Reproduzir no editor" (quando a conversa não está mais na lista). */
const nomeDoSlug = (slug: string) => { const t = slug.replace(/^\d{4}-\d{2}-\d{2}-?/, '').replace(/[-_]+/g, ' ').trim(); return t ? t[0].toUpperCase() + t.slice(1) : slug }
const dataDoSlug = (slug: string) => slug.match(/^\d{4}-\d{2}-\d{2}/)?.[0]
const corUso = (r?: string) => r === 'postado ou agendado' ? 'bg-green-500/80 text-[#04170b]' : r === 'no Drive' ? 'bg-azul/90 text-white' : 'bg-black/60 text-nevoa'

/** Cartão de uma entrega: prévia, tipo, uso, nome e as duas ações (Baixar o principal, abrir a conversa). */
function CartaoEntrega({ p, conv, onAbrir }: { p: Pasta; conv?: Conversa; onAbrir: () => void }) {
  const tipo = tipoDe(p.itens); const t = TIPOS[tipo]; const { video, capa } = midiaDe(p.itens)
  const principal = video || p.itens.find(i => i.principal) || capa || p.itens[0]
  const quando = p.itens.reduce((m, i) => i.modificado > m ? i.modificado : m, '') || dataDoSlug(p.slug)
  return <div className="cartao group flex flex-col overflow-hidden border border-white/5 transition hover:-translate-y-0.5 hover:border-white/15">
    <div className="relative">
      <Previa capa={capa?.url} video={video?.url} tipo={tipo} onClick={onAbrir} />
      <span className={`absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[10px] backdrop-blur ${t.cor}`}><Icone nome={t.icone} className="h-3 w-3" />{t.rotulo}</span>
      {p.uso && p.uso.rotulo !== 'ainda não usado' && <span className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-[10px] font-bold backdrop-blur ${corUso(p.uso.rotulo)}`}>{p.uso.rotulo === 'no Drive' ? 'no Drive' : 'postado'}</span>}
    </div>
    <div className="flex flex-1 flex-col p-3">
      <button onClick={onAbrir} className="line-clamp-2 text-left text-sm font-bold leading-snug hover:text-laranja">{conv?.titulo || nomeDoSlug(p.slug)}</button>
      <div className="mt-1 truncate text-[11px] text-nevoa">{conv?.codigo ? `${conv.codigo} · ` : ''}{ha(quando)} · {p.itens.length} arquivo{p.itens.length === 1 ? '' : 's'}{p.pasta ? ` · ${p.pasta}` : ''}</div>
      <div className="mt-auto flex items-center gap-1.5 pt-3">
        {principal ? <a href={principal.url} download className="btn-laranja inline-flex items-center gap-1.5 px-3 py-1 text-xs"><Icone nome="baixar" className="h-3.5 w-3.5" />Baixar</a> : null}
        <button onClick={onAbrir} title="Ver todos os arquivos" className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-nevoa hover:bg-white/5 hover:text-white">Arquivos</button>
        {p.conversa && <Link to={`/c/${p.conversa}`} title="Abrir a conversa do pedido" className="ml-auto rounded-full p-1.5 text-nevoa hover:bg-white/5 hover:text-laranja"><Icone nome="conversa" className="h-4 w-4" /></Link>}
      </div>
    </div>
  </div>
}

/** Gaveta com todos os arquivos da entrega (mesma linguagem da gaveta de Receitas). */
function Gaveta({ p, conv, onFechar }: { p: Pasta; conv?: Conversa; onFechar: () => void }) {
  useEffect(() => { const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onFechar() }; window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onFechar])
  const videos = p.itens.filter(i => i.tipo === 'video'); const imgs = p.itens.filter(i => i.tipo === 'imagem'); const outros = p.itens.filter(i => i.tipo !== 'video' && i.tipo !== 'imagem')
  return <div className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]" onClick={onFechar}>
    <aside onClick={e => e.stopPropagation()} className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-y-auto border-l border-white/10 bg-[#071030] shadow-2xl animate-[gs-entra_.18s_ease-out]">
      <div className="sticky top-0 z-10 flex items-start gap-3 border-b border-white/5 bg-[#071030]/95 p-4 backdrop-blur">
        <div className="min-w-0"><div className="text-[11px] uppercase tracking-wider text-laranja">{TIPOS[tipoDe(p.itens)].rotulo}{p.uso ? ` · ${p.uso.rotulo}` : ''}</div>
          <h3 className="mt-0.5 text-lg leading-snug">{conv?.titulo || nomeDoSlug(p.slug)}</h3>
          <div className="truncate text-xs text-nevoa">{conv?.codigo ? `${conv.codigo} · ` : ''}{p.slug}</div></div>
        <button onClick={onFechar} className="ml-auto rounded-full p-2 text-nevoa hover:bg-white/5 hover:text-white" aria-label="Fechar"><Icone nome="fechar" /></button>
      </div>
      <div className="grid gap-4 p-4">
        {p.conversa && <Link to={`/c/${p.conversa}`} className="btn-laranja inline-flex w-fit items-center gap-2 px-4 py-1.5 text-sm"><Icone nome="conversa" className="h-4 w-4" />Abrir a conversa</Link>}
        {p.uso && (p.uso.publora || p.uso.youtube || p.uso.drive) ? <div className="text-xs text-nevoa">Publora {p.uso.publora} · YouTube {p.uso.youtube} · Drive {p.uso.drive}{p.uso.ultimo ? ` · último ${p.uso.ultimo.replace('T', ' ').slice(0, 16)}` : ''}</div> : null}
        {videos.map(v => <div key={v.caminho}><video src={v.url} controls preload="metadata" playsInline className="max-h-[60vh] w-full rounded-xl bg-black" />
          <div className="mt-1 flex items-center gap-2 text-xs text-nevoa"><span className="truncate">{v.nome} · {v.tamanho_mb} MB</span><a href={v.url} download className="ml-auto text-laranja hover:underline">baixar</a></div></div>)}
        {imgs.length > 0 && <div className="grid grid-cols-3 gap-2">{imgs.map(i => <a key={i.caminho} href={i.url} target="_blank" rel="noreferrer" className="overflow-hidden rounded-lg bg-black/30" title={i.nome}><img src={i.url} alt={i.nome} loading="lazy" className="aspect-square w-full object-cover hover:opacity-80" /></a>)}</div>}
        {outros.length > 0 && <div className="grid gap-1">{outros.map(i => <a key={i.caminho} href={i.url} download className="flex items-center gap-2 rounded-xl bg-black/20 px-3 py-2 text-sm hover:bg-white/5"><span className={(TIPOS[i.tipo] || TIPOS.arquivo).cor}><Icone nome={(TIPOS[i.tipo] || { icone: i.tipo === 'legenda' ? 'legenda' : 'arquivo' }).icone} className="h-4 w-4" /></span><span className="min-w-0 flex-1 truncate">{i.nome}</span><span className="text-xs text-nevoa">{i.tamanho_mb} MB</span><Icone nome="baixar" className="h-4 w-4 text-nevoa" /></a>)}</div>}
        {p.itens.length === 0 && <div className="text-sm text-nevoa">Esta pasta de entrega ainda não tem arquivos (o pedido pode estar em andamento).</div>}
      </div>
    </aside>
  </div>
}

export default function Biblioteca() {
  const nav = useNavigate()
  const bib = useCarga(() => api.biblioteca())
  const [convs, setConvs] = useState<Record<string, Conversa>>({})
  useEffect(() => { api.conversas().then(cs => setConvs(Object.fromEntries(cs.map(c => [c.id, c])))).catch(() => {}) }, [])
  const pastas = bib.dados || []
  const [mostrarTestes, setMostrarTestes] = useState(false)  // entregas de teste do sistema escondidas por padrão (11/11/2026)
  const entregas = mostrarTestes ? pastas : pastas.filter(p => !p.teste); const nTestes = pastas.length - pastas.filter(p => !p.teste).length
  const [filtro, setFiltro] = useState<FiltroUso>('todos'); const [tipo, setTipo] = useState(''); const [buscaBib, setBuscaBib] = useState(''); const [aberta, setAberta] = useState('')
  const [mat, setMat] = useState<any>(null); const [sinc, setSinc] = useState(false); const [erro, setErro] = useState('')
  const [avulsos, setAvulsos] = useState<Avulso[]>([]); const [progresso, setProgresso] = useState<number | null>(null)
  const [arm, setArm] = useState<Armazenamento | null>(null); const [uso, setUso] = useState<Uso | null>(null); const [limpando, setLimpando] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { api.materiais().then(setMat).catch(() => {}); api.avulsos().then(setAvulsos).catch(() => {}); api.armazenamento().then(setArm).catch(() => {}); api.uso().then(setUso).catch(() => {}) }, [])
  async function sincronizar() { setSinc(true); setErro(''); try { await api.materiaisSincronizar(); setMat(await api.materiais()) } catch (e: any) { setErro(e.message) } finally { setSinc(false) } }
  async function enviar(files: FileList | null) {
    if (!files || files.length === 0) return
    const fd = new FormData(); Array.from(files).forEach(f => fd.append('arquivos', f)); setProgresso(0); setErro('')
    try { await api.uploadAvulso(fd, setProgresso); setAvulsos(await api.avulsos()); setArm(await api.armazenamento()) } catch (e: any) { setErro(e.message) } finally { setProgresso(null) }
  }
  async function apagarAvulso(a: Avulso) { if (!confirm(`Apagar ${a.nome} da biblioteca?`)) return; try { await api.apagarAvulso(a.nome); setAvulsos(avulsos.filter(x => x.nome !== a.nome)) } catch (e: any) { setErro(e.message) } }
  function usar(a: Avulso) { nav('/', { state: { pedido: `Use o arquivo \`${a.caminho}\` (já está na biblioteca, não precisa anexar). ` } }) }
  async function limpar() {
    if (!arm || arm.limpeza.candidatos.length === 0) return
    if (!confirm(`Apagar ${arm.limpeza.candidatos.length} pasta(s) de trabalho paradas há mais de ${arm.limpeza.dias} dias (${arm.limpeza.mb} MB)? Entregas, versões anteriores e entradas ficam.`)) return
    setLimpando(true); setErro('')
    try { const r = await api.limparTrabalho(arm.limpeza.dias); alert(`Liberados ${r.mb} MB.`); setArm(await api.armazenamento()) } catch (e: any) { setErro(e.message) } finally { setLimpando(false) }
  }
  const tipos = useMemo(() => { const c: Record<string, number> = {}; entregas.forEach(p => { const t = tipoDe(p.itens); c[t] = (c[t] || 0) + 1 }); return c }, [entregas])
  const q = semAcento(buscaBib.trim())
  const lista = entregas.filter(p => passaUso(p, filtro) && (!tipo || tipoDe(p.itens) === tipo) && (!q || semAcento(`${p.slug} ${p.pasta || ''} ${(p.conversa && convs[p.conversa]?.titulo) || ''} ${(p.conversa && convs[p.conversa]?.codigo) || ''}`).includes(q)))
  const chip = (ativo: boolean) => `inline-flex shrink-0 whitespace-nowrap items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${ativo ? 'border-laranja bg-laranja/10 text-laranja' : 'border-white/10 text-nevoa hover:bg-white/5 hover:text-white'}`
  const filtrando = filtro !== 'todos' || !!tipo || !!q
  const pAberta = pastas.find(p => p.slug === aberta)
  return <div className="max-w-6xl mx-auto px-4 py-8">
    <div className="flex flex-wrap items-end gap-3"><div><h2 className="text-2xl">Biblioteca</h2><p className="text-nevoa mt-1 text-sm">Tudo que o Editor entregou. Toque na prévia para ver os arquivos.</p></div>
      {uso?.economia && uso.economia.n_entregas > 0 && <div className="ml-auto rounded-2xl border border-laranja/30 bg-laranja/10 px-3 py-2 text-xs"><span className="text-nevoa">tempo economizado em 30 dias </span><b className="text-laranja">{horas(uso.economia.periodos_min['30_dias'] || 0)}</b></div>}</div>
    {erro && <div className="text-red-300 mt-3 text-sm">{erro}</div>}

    <input value={buscaBib} onChange={e => setBuscaBib(e.target.value)} placeholder="Buscar por nome, código ou pasta" className="mt-5 w-full rounded-full bg-black/30 px-4 py-1.5 text-sm outline-none placeholder:text-nevoa sm:w-80" />
    <div className="mt-2 -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 items-center">
      {USOS.map(([k, r]) => <button key={k} onClick={() => setFiltro(k)} className={chip(filtro === k)}>{r} <span className="opacity-60">{entregas.filter(p => passaUso(p, k)).length}</span></button>)}
    </div>
    <div className="mt-2 -mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0 items-center">
      <button onClick={() => setTipo('')} className={chip(!tipo)}>Todos os tipos</button>
      {Object.entries(tipos).sort((a, b) => b[1] - a[1]).map(([k, n]) => <button key={k} onClick={() => setTipo(tipo === k ? '' : k)} className={chip(tipo === k)}><span className={tipo === k ? '' : TIPOS[k].cor}><Icone nome={TIPOS[k].icone} className="h-3.5 w-3.5" /></span>{TIPOS[k].rotulo} <span className="opacity-60">{n}</span></button>)}
      {nTestes > 0 && <button onClick={() => setMostrarTestes(!mostrarTestes)} title="Entregas da pasta “Testes do sistema” e testes técnicos" className={`${chip(mostrarTestes)} ml-auto`}>{mostrarTestes ? 'esconder testes' : `mostrar testes · ${nTestes}`}</button>}
    </div>

    <Carga carregando={bib.carregando} erro={bib.erro} semDados={!bib.dados} onTentar={bib.recarregar} esqueleto={<Esqueleto className="mt-4" n={8} />}
      vazio={lista.length ? null : filtrando ? { icone: 'busca', titulo: 'Nada com esse filtro', texto: 'Tente outro tipo ou limpe a busca.', acao: { rotulo: 'Limpar filtros', onClick: () => { setFiltro('todos'); setTipo(''); setBuscaBib('') } } }
        : { icone: 'biblioteca', titulo: 'Nada entregue ainda', texto: 'Quando o Editor terminar um pedido, o vídeo, a capa e os textos aparecem aqui.', acao: { rotulo: 'Fazer um pedido', to: '/' } }}>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{lista.map(p => <CartaoEntrega key={p.slug} p={p} conv={p.conversa ? convs[p.conversa] : undefined} onAbrir={() => setAberta(p.slug)} />)}</div>
    </Carga>
    {pAberta && <Gaveta p={pAberta} conv={pAberta.conversa ? convs[pAberta.conversa] : undefined} onFechar={() => setAberta('')} />}

    <h3 className="text-lg mt-10">Arquivos, Drive e espaço</h3>
    <div className="grid md:grid-cols-2 gap-4 mt-3">
      <div className="cartao p-4 text-sm">
        <div className="font-bold">Armazenamento</div>
        {arm ? <>
          <div className="text-nevoa text-xs mt-1">{arm.total_mb} MB no workspace · {arm.disco.livre_gb} GB livres no disco</div>
          <div className="flex flex-wrap gap-2 mt-2">{Object.entries(arm.pastas_mb).filter(([, v]) => v > 0).map(([k, v]) => <span key={k} className="selo">{k} {v} MB</span>)}</div>
          <div className="text-nevoa text-xs mt-2">Trabalho (camadas, rascunhos): {arm.trabalho_mb} MB · versões anteriores: {arm.anteriores_mb} MB</div>
          <button onClick={limpar} disabled={limpando || arm.limpeza.candidatos.length === 0} className="rounded-full border border-white/15 px-4 py-1.5 mt-3 hover:bg-white/5 disabled:opacity-40">{limpando ? 'Limpando…' : arm.limpeza.candidatos.length ? `Limpar trabalho com mais de ${arm.limpeza.dias} dias (${arm.limpeza.mb} MB)` : 'Nada para limpar'}</button>
        </> : <Esqueleto tipo="bloco" className="mt-2 !p-0 !bg-transparent" />}
      </div>
      <div className="cartao p-4 text-sm">
        <div className="font-bold">Uso do Editor</div>
        {uso ? <>
          <div className="grid grid-cols-3 gap-2 mt-2">{(['hoje', '7_dias', '30_dias'] as const).map(k => <div key={k} className="rounded-xl bg-black/30 p-2"><div className="text-[11px] text-nevoa">{k.replace('_', ' ')}</div><div className="text-lg font-bold">{uso.periodos[k].criados}</div><div className="text-[11px] text-nevoa">{uso.periodos[k].concluidos} concluídos</div></div>)}</div>
          <div className="text-nevoa text-xs mt-2">{uso.em_andamento} editando · {uso.na_fila} na fila · {uso.aguardando_voce} aguardando você{uso.duracao_media_min != null && <> · média {uso.duracao_media_min} min por pedido ({uso.n_medidos})</>}</div>
          <div className="text-nevoa text-xs mt-1">{uso.nota}</div>
          {uso.por_agente && Object.keys(uso.por_agente).length > 0 && <div className="mt-3"><div className="text-[11px] uppercase tracking-wide text-nevoa">Por agente (30 dias)</div>
            <div className="overflow-x-auto"><table className="w-full text-xs mt-1"><tbody>{Object.entries(uso.por_agente).sort((a, b) => b[1].pedidos_30d - a[1].pedidos_30d).map(([n, u]) => <tr key={n} className="border-t border-white/10"><td className="py-1 pr-2">{n}</td><td className="py-1 pr-2 text-nevoa">{u.pedidos_30d} pedidos</td><td className="py-1 pr-2 text-nevoa">{u.concluidos_30d} concluídos</td><td className="py-1 pr-2 text-nevoa">{u.duracao_media_min != null ? `${u.duracao_media_min} min` : '—'}</td><td className="py-1 text-laranja">{u.em_andamento ? `${u.em_andamento} agora` : ''}</td></tr>)}</tbody></table></div>
            <div className="text-nevoa text-[11px] mt-1">O consumo da janela de 5 h/semanal da assinatura não é exposto pelo Paperclip nem pelo Claude Code; aqui vai o que dá para medir: pedidos e tempo por agente.</div></div>}
          {uso.economia && uso.economia.n_entregas > 0 && <div className="mt-3 rounded-xl bg-laranja/10 border border-laranja/30 p-3">
            <div className="font-bold text-laranja">Tempo economizado</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">{(['hoje', '7_dias', '30_dias'] as const).map(k => <div key={k}><div className="text-[11px] text-nevoa">{k.replace('_', ' ')}</div><div className="font-bold">{horas(uso.economia!.periodos_min[k] || 0)}</div></div>)}<div><div className="text-[11px] text-nevoa">total ({uso.economia.n_entregas} entregas)</div><div className="font-bold">{horas(uso.economia.total_min)}</div></div></div>
            <div className="text-nevoa text-[11px] mt-2">{uso.economia.nota}</div>
          </div>}
        </> : <Esqueleto tipo="bloco" className="mt-2 !p-0 !bg-transparent" />}
      </div>
    </div>

    <div className="cartao p-4 mt-4 text-sm">
      <div className="flex items-center gap-3 flex-wrap"><div><div className="font-bold">Arquivos avulsos</div><div className="text-nevoa text-xs">Vídeos, áudios e imagens que você quer deixar prontos para pedidos futuros. Ficam em entrada/_biblioteca.</div></div>
        <button onClick={() => inputRef.current?.click()} disabled={progresso !== null} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{progresso !== null ? `Enviando ${progresso}%` : 'Enviar arquivos'}</button>
        <input ref={inputRef} type="file" multiple className="hidden" onChange={e => { enviar(e.target.files); e.target.value = '' }} /></div>
      {avulsos.length > 0 && <div className="grid gap-1 mt-3">{avulsos.map(a => <div key={a.nome} className="flex items-center gap-2"><span className={`w-5 ${(TIPOS[a.tipo] || TIPOS.arquivo).cor}`}><Icone nome={(TIPOS[a.tipo] || TIPOS.arquivo).icone} className="h-4 w-4" /></span><span className="flex-1 min-w-0 truncate">{a.nome}</span><span className="text-xs text-nevoa">{a.tamanho_mb} MB</span><button onClick={() => usar(a)} className="text-xs text-laranja">Usar num pedido</button><button onClick={() => apagarAvulso(a)} className="text-xs text-nevoa hover:text-red-300">✕</button></div>)}</div>}
    </div>

    <div className="cartao p-4 mt-4 text-sm">
      <div className="flex items-center gap-3 flex-wrap"><div><div className="font-bold">Materiais do Drive</div><div className="text-nevoa text-xs">{mat ? (mat.configurado ? `${mat.n_arquivos} arquivos · origem ${mat.origem}${mat.ultima_sincronizacao ? ` · sincronizado ${new Date(mat.ultima_sincronizacao).toLocaleString('pt-BR')}` : ''}` : mat.pendencias.join('; ')) : '…'}</div></div>
        <button onClick={sincronizar} disabled={sinc || !mat?.configurado} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{sinc ? 'Sincronizando…' : 'Sincronizar do Drive'}</button></div>
      {mat?.itens?.length > 0 && <div className="flex flex-wrap gap-2 mt-3">{mat.itens.slice(0, 60).map((i: any) => <span key={i.caminho} className="selo" title={`${i.tamanho_mb} MB${i.duracao_s ? ` · ${Math.round(i.duracao_s)} s` : ''}`}>{i.caminho}</span>)}{mat.itens.length > 60 && <span className="text-nevoa">… e mais {mat.itens.length - 60}</span>}</div>}
      <div className="text-xs text-nevoa mt-2">Espelho só leitura de uma pasta do Drive (logo, fotos, takes, prints). O Editor consulta o índice antes de capa, carrossel e b-roll. Guia: Ajuda → Materiais do Drive.</div>
    </div>
  </div>
}
