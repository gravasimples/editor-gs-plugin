import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Armazenamento, type Avulso, type Entrega, type Uso, type UsoEntrega } from '../api'
import { horas } from '../api'

export default function Biblioteca() {
  const nav = useNavigate()
  const [pastas, setPastas] = useState<{ slug: string; itens: Entrega[]; uso?: UsoEntrega; conversa?: string | null; pasta?: string | null }[]>([])
  const [filtro, setFiltro] = useState<'todos' | 'postado' | 'drive' | 'nao-usado'>('todos'); const [buscaBib, setBuscaBib] = useState('')
  const [mat, setMat] = useState<any>(null); const [sinc, setSinc] = useState(false); const [erro, setErro] = useState('')
  const [avulsos, setAvulsos] = useState<Avulso[]>([]); const [progresso, setProgresso] = useState<number | null>(null)
  const [arm, setArm] = useState<Armazenamento | null>(null); const [uso, setUso] = useState<Uso | null>(null); const [limpando, setLimpando] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { api.biblioteca().then(setPastas).catch(() => {}); api.materiais().then(setMat).catch(() => {}); api.avulsos().then(setAvulsos).catch(() => {}); api.armazenamento().then(setArm).catch(() => {}); api.uso().then(setUso).catch(() => {}) }, [])
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
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Biblioteca</h2><p className="text-nevoa mt-2">Tudo que o Editor entregou, por pedido; arquivos avulsos; materiais do Drive; espaço e uso.</p>
    {erro && <div className="text-red-300 mt-3 text-sm">{erro}</div>}

    <div className="grid md:grid-cols-2 gap-4 mt-5">
      <div className="cartao p-4 text-sm">
        <div className="font-bold">Armazenamento</div>
        {arm ? <>
          <div className="text-nevoa text-xs mt-1">{arm.total_mb} MB no workspace · {arm.disco.livre_gb} GB livres no disco</div>
          <div className="flex flex-wrap gap-2 mt-2">{Object.entries(arm.pastas_mb).filter(([, v]) => v > 0).map(([k, v]) => <span key={k} className="selo">{k} {v} MB</span>)}</div>
          <div className="text-nevoa text-xs mt-2">Trabalho (camadas, rascunhos): {arm.trabalho_mb} MB · versões anteriores: {arm.anteriores_mb} MB</div>
          <button onClick={limpar} disabled={limpando || arm.limpeza.candidatos.length === 0} className="rounded-full border border-white/15 px-4 py-1.5 mt-3 hover:bg-white/5 disabled:opacity-40">{limpando ? 'Limpando…' : arm.limpeza.candidatos.length ? `Limpar trabalho com mais de ${arm.limpeza.dias} dias (${arm.limpeza.mb} MB)` : 'Nada para limpar'}</button>
        </> : <div className="text-nevoa text-xs mt-1">…</div>}
      </div>
      <div className="cartao p-4 text-sm">
        <div className="font-bold">Uso do Editor</div>
        {uso ? <>
          <div className="grid grid-cols-3 gap-2 mt-2">{(['hoje', '7_dias', '30_dias'] as const).map(k => <div key={k} className="rounded-xl bg-black/30 p-2"><div className="text-[11px] text-nevoa">{k.replace('_', ' ')}</div><div className="text-lg font-bold">{uso.periodos[k].criados}</div><div className="text-[11px] text-nevoa">{uso.periodos[k].concluidos} concluídos</div></div>)}</div>
          <div className="text-nevoa text-xs mt-2">{uso.em_andamento} editando · {uso.na_fila} na fila · {uso.aguardando_voce} aguardando você{uso.duracao_media_min != null && <> · média {uso.duracao_media_min} min por pedido ({uso.n_medidos})</>}</div>
          <div className="text-nevoa text-xs mt-1">{uso.nota}</div>
          {uso.por_agente && Object.keys(uso.por_agente).length > 0 && <div className="mt-3"><div className="text-[11px] uppercase tracking-wide text-nevoa">Por agente (30 dias)</div>
            <table className="w-full text-xs mt-1"><tbody>{Object.entries(uso.por_agente).sort((a, b) => b[1].pedidos_30d - a[1].pedidos_30d).map(([n, u]) => <tr key={n} className="border-t border-white/10"><td className="py-1 pr-2">{n}</td><td className="py-1 pr-2 text-nevoa">{u.pedidos_30d} pedidos</td><td className="py-1 pr-2 text-nevoa">{u.concluidos_30d} concluídos</td><td className="py-1 pr-2 text-nevoa">{u.duracao_media_min != null ? `${u.duracao_media_min} min` : '—'}</td><td className="py-1 text-laranja">{u.em_andamento ? `${u.em_andamento} agora` : ''}</td></tr>)}</tbody></table>
            <div className="text-nevoa text-[11px] mt-1">O consumo da janela de 5 h/semanal da assinatura não é exposto pelo Paperclip nem pelo Claude Code; aqui vai o que dá para medir: pedidos e tempo por agente.</div></div>}
          {uso.economia && uso.economia.n_entregas > 0 && <div className="mt-3 rounded-xl bg-laranja/10 border border-laranja/30 p-3">
            <div className="font-bold text-laranja">Tempo economizado</div>
            <div className="grid grid-cols-4 gap-2 mt-2">{(['hoje', '7_dias', '30_dias'] as const).map(k => <div key={k}><div className="text-[11px] text-nevoa">{k.replace('_', ' ')}</div><div className="font-bold">{horas(uso.economia!.periodos_min[k] || 0)}</div></div>)}<div><div className="text-[11px] text-nevoa">total ({uso.economia.n_entregas} entregas)</div><div className="font-bold">{horas(uso.economia.total_min)}</div></div></div>
            <div className="text-nevoa text-[11px] mt-2">{uso.economia.nota}</div>
          </div>}
        </> : <div className="text-nevoa text-xs mt-1">…</div>}
      </div>
    </div>

    <div className="cartao p-4 mt-4 text-sm">
      <div className="flex items-center gap-3 flex-wrap"><div><div className="font-bold">Arquivos avulsos</div><div className="text-nevoa text-xs">Vídeos, áudios e imagens que você quer deixar prontos para pedidos futuros. Ficam em entrada/_biblioteca.</div></div>
        <button onClick={() => inputRef.current?.click()} disabled={progresso !== null} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{progresso !== null ? `Enviando ${progresso}%` : 'Enviar arquivos'}</button>
        <input ref={inputRef} type="file" multiple className="hidden" onChange={e => { enviar(e.target.files); e.target.value = '' }} /></div>
      {avulsos.length > 0 && <div className="grid gap-1 mt-3">{avulsos.map(a => <div key={a.nome} className="flex items-center gap-2"><span className="w-5">{a.tipo === 'video' ? '🎬' : a.tipo === 'imagem' ? '🖼' : a.tipo === 'audio' ? '🎙' : '📄'}</span><span className="flex-1 min-w-0 truncate">{a.nome}</span><span className="text-xs text-nevoa">{a.tamanho_mb} MB</span><button onClick={() => usar(a)} className="text-xs text-laranja">Usar num pedido</button><button onClick={() => apagarAvulso(a)} className="text-xs text-nevoa hover:text-red-300">✕</button></div>)}</div>}
    </div>

    <div className="cartao p-4 mt-4 text-sm">
      <div className="flex items-center gap-3 flex-wrap"><div><div className="font-bold">Materiais do Drive</div><div className="text-nevoa text-xs">{mat ? (mat.configurado ? `${mat.n_arquivos} arquivos · origem ${mat.origem}${mat.ultima_sincronizacao ? ` · sincronizado ${new Date(mat.ultima_sincronizacao).toLocaleString('pt-BR')}` : ''}` : mat.pendencias.join('; ')) : '…'}</div></div>
        <button onClick={sincronizar} disabled={sinc || !mat?.configurado} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{sinc ? 'Sincronizando…' : 'Sincronizar do Drive'}</button></div>
      {mat?.itens?.length > 0 && <div className="flex flex-wrap gap-2 mt-3">{mat.itens.slice(0, 60).map((i: any) => <span key={i.caminho} className="selo" title={`${i.tamanho_mb} MB${i.duracao_s ? ` · ${Math.round(i.duracao_s)} s` : ''}`}>{i.tipo === 'video' ? '🎬 ' : i.tipo === 'imagem' ? '🖼 ' : '📄 '}{i.caminho}</span>)}{mat.itens.length > 60 && <span className="text-nevoa">… e mais {mat.itens.length - 60}</span>}</div>}
      <div className="text-xs text-nevoa mt-2">Espelho só leitura de uma pasta do Drive (logo, fotos, takes, prints). O Editor consulta o índice antes de capa, carrossel e b-roll. Guia: Ajuda → Materiais do Drive.</div>
    </div>

    <h3 className="text-lg mt-8">Entregas</h3>
    <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
      {([['todos', 'Todas'], ['postado', 'Já postadas ou agendadas'], ['drive', 'Só no Drive'], ['nao-usado', 'Ainda não usadas']] as const).map(([k, r]) => <button key={k} onClick={() => setFiltro(k)} className={`rounded-full border px-3 py-1 ${filtro === k ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>{r} ({pastas.filter(p => k === 'todos' || (k === 'postado' && p.uso?.rotulo === 'postado ou agendado') || (k === 'drive' && p.uso?.rotulo === 'no Drive') || (k === 'nao-usado' && (!p.uso || p.uso.rotulo === 'ainda não usado'))).length})</button>)}
      <input value={buscaBib} onChange={e => setBuscaBib(e.target.value)} placeholder="filtrar por nome ou pasta" className="ml-auto rounded-full bg-black/40 px-3 py-1 outline-none w-48" />
    </div>
    {pastas.filter(p => (filtro === 'todos' || (filtro === 'postado' && p.uso?.rotulo === 'postado ou agendado') || (filtro === 'drive' && p.uso?.rotulo === 'no Drive') || (filtro === 'nao-usado' && (!p.uso || p.uso.rotulo === 'ainda não usado'))) && (!buscaBib.trim() || `${p.slug} ${p.pasta || ''}`.toLowerCase().includes(buscaBib.toLowerCase()))).map(p => <div key={p.slug} className="mt-5">
      <div className="flex flex-wrap items-center gap-2 mb-2"><div className="font-bold">{p.slug}</div>
        {p.uso && <span className={`rounded-full px-2 py-0.5 text-[11px] ${p.uso.rotulo === 'postado ou agendado' ? 'bg-green-500/20 text-green-300' : p.uso.rotulo === 'no Drive' ? 'bg-azul/30 text-white' : 'bg-white/10 text-nevoa'}`} title={p.uso.ultimo ? `último registro ${p.uso.ultimo.replace('T', ' ')}` : ''}>{p.uso.rotulo}{p.uso.publora ? ` · Publora ${p.uso.publora}` : ''}{p.uso.youtube ? ` · YouTube ${p.uso.youtube}` : ''}{p.uso.drive ? ` · Drive ${p.uso.drive}` : ''}</span>}
        {p.pasta && <span className="selo">{p.pasta}</span>}
        {p.conversa && <button onClick={() => nav(`/c/${p.conversa}`)} className="ml-auto text-xs text-laranja hover:underline">abrir conversa</button>}</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{p.itens.filter(i => i.tipo === 'video').map(i => <div key={i.caminho} className="cartao p-2"><video src={i.url} preload="metadata" controls className="w-full rounded-lg bg-black aspect-[9/16] object-contain" /><div className="text-xs text-nevoa mt-1 truncate">{i.nome} · {i.tamanho_mb} MB</div></div>)}</div>
      <div className="flex flex-wrap gap-2 mt-2 text-sm">{p.itens.filter(i => i.tipo !== 'video').map(i => <a key={i.caminho} href={i.url} download className="selo">{i.nome}</a>)}</div>
    </div>)}
    {pastas.length === 0 && <div className="text-nevoa mt-6">Nada entregue ainda.</div>}
  </div>
}
