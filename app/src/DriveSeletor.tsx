import { useEffect, useRef, useState } from 'react'
import { api, type DriveItem, type DrivePasta } from './api'

const ICONE: Record<string, string> = { video: '🎬', audio: '🎵', imagem: '🖼', pdf: '📄', outro: '📎' }
const LEMBRAR = 'gs-drive-ultima'

/** Janela para navegar no Google Drive conectado e escolher arquivos (como no Máquina). Só lê o Drive; o download acontece no envio. */
export function DriveSeletor({ aberto, onFechar, onEscolher, ja = [] }: { aberto: boolean; onFechar: () => void; onEscolher: (itens: DriveItem[]) => void; ja?: DriveItem[] }) {
  const [raizes, setRaizes] = useState<{ id: string; rotulo: string }[]>([])
  const [raiz, setRaiz] = useState('0')
  const [caminho, setCaminho] = useState(() => { try { return localStorage.getItem(LEMBRAR) || '' } catch { return '' } })
  const [pasta, setPasta] = useState<DrivePasta | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [filtro, setFiltro] = useState('')
  const [sel, setSel] = useState<DriveItem[]>([])
  const pedido = useRef(0)
  useEffect(() => { if (aberto) { setSel([]); api.driveRaizes().then(r => { setRaizes(r.raizes); if (r.raizes.length && !r.raizes.some(x => x.id === raiz)) setRaiz(r.raizes[0].id) }).catch(e => setErro(e.message)) } }, [aberto])
  useEffect(() => {
    if (!aberto) return
    const n = ++pedido.current; setCarregando(true); setErro(''); setFiltro('')
    api.driveListar(raiz, caminho).then(p => { if (n === pedido.current) { setPasta(p); try { localStorage.setItem(LEMBRAR, caminho) } catch {} } })
      .catch(e => { if (n === pedido.current) { setErro(e.message); if (caminho) { setCaminho('') } } })
      .finally(() => { if (n === pedido.current) setCarregando(false) })
  }, [aberto, raiz, caminho])
  if (!aberto) return null
  const partes = caminho ? caminho.split('/') : []
  const f = filtro.trim().toLowerCase()
  const pastas = (pasta?.pastas || []).filter(p => !f || p.nome.toLowerCase().includes(f))
  const arquivos = (pasta?.arquivos || []).filter(a => !f || a.nome.toLowerCase().includes(f))
  const marcado = (c: string) => sel.some(s => s.caminho === c && s.raiz === raiz)
  const jaTem = (c: string) => ja.some(s => s.caminho === c && s.raiz === raiz)
  const alternar = (a: DrivePasta['arquivos'][number]) => setSel(s => marcado(a.caminho) ? s.filter(x => !(x.caminho === a.caminho && x.raiz === raiz)) : [...s, { raiz, caminho: a.caminho, nome: a.nome, tipo: a.tipo, tamanho_mb: a.tamanho_mb }])
  const mb = sel.reduce((t, s) => t + s.tamanho_mb, 0)
  return <div className="fixed inset-0 z-50 bg-black/70 flex items-end md:items-center justify-center" onClick={onFechar}>
    <div className="bg-[#060e2a] border border-white/10 w-full md:max-w-2xl max-h-[85vh] rounded-t-2xl md:rounded-2xl flex flex-col" onClick={e => e.stopPropagation()}>
      <div className="p-4 border-b border-white/10 flex items-center gap-2">
        <div className="font-bold">☁ Escolher do Google Drive</div>
        {raizes.length > 1 && <select value={raiz} onChange={e => { setRaiz(e.target.value); setCaminho('') }} className="rounded-full border border-white/15 bg-card px-3 py-1 text-xs">{raizes.map(r => <option key={r.id} value={r.id}>{r.rotulo}</option>)}</select>}
        <button onClick={onFechar} className="ml-auto text-nevoa hover:text-white px-2">✕</button>
      </div>
      <div className="px-4 pt-3 flex flex-wrap items-center gap-1 text-xs">
        <button onClick={() => setCaminho('')} className="text-laranja hover:underline">{raizes.find(r => r.id === raiz)?.rotulo || 'Drive'}</button>
        {partes.map((p, i) => <span key={i} className="flex items-center gap-1"><span className="text-nevoa">/</span><button onClick={() => setCaminho(partes.slice(0, i + 1).join('/'))} className={i === partes.length - 1 ? 'text-white' : 'text-laranja hover:underline'}>{p}</button></span>)}
      </div>
      <div className="px-4 pt-2"><input value={filtro} onChange={e => setFiltro(e.target.value)} placeholder="Filtrar nesta pasta" className="w-full rounded-xl bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-nevoa" /></div>
      <div className="flex-1 overflow-y-auto p-2 mt-1">
        {carregando && <div className="text-nevoa text-sm p-3 animate-pulse">Lendo o Drive…</div>}
        {erro && <div className="text-red-300 text-sm p-3">{erro}</div>}
        {!carregando && pasta && <>
          {caminho && <button onClick={() => setCaminho(partes.slice(0, -1).join('/'))} className="w-full text-left rounded-lg px-3 py-2 text-sm hover:bg-white/5 text-nevoa">↩ Voltar</button>}
          {pastas.map(p => <button key={p.caminho} onClick={() => setCaminho(p.caminho)} className="w-full text-left rounded-lg px-3 py-2 text-sm hover:bg-white/5 flex items-center gap-2"><span>📁</span><span className="truncate">{p.nome}</span><span className="ml-auto text-nevoa">›</span></button>)}
          {arquivos.map(a => <label key={a.caminho} className={`w-full rounded-lg px-3 py-2 text-sm flex items-center gap-2 ${a.baixavel && !jaTem(a.caminho) ? 'hover:bg-white/5 cursor-pointer' : 'opacity-40'}`} title={a.baixavel ? '' : 'Documento do Google (Docs, Planilhas, Slides) não vira arquivo de mídia'}>
            <input type="checkbox" disabled={!a.baixavel || jaTem(a.caminho)} checked={marcado(a.caminho) || jaTem(a.caminho)} onChange={() => alternar(a)} className="accent-[#F79615]" />
            <span>{ICONE[a.tipo] || '📎'}</span><span className="truncate">{a.nome}</span>
            <span className="ml-auto text-[11px] text-nevoa whitespace-nowrap">{a.baixavel ? `${a.tamanho_mb >= 1000 ? (a.tamanho_mb / 1000).toFixed(1) + ' GB' : a.tamanho_mb.toFixed(a.tamanho_mb < 10 ? 1 : 0) + ' MB'}` : 'Google Docs'}{a.modificado ? ` · ${new Date(a.modificado).toLocaleDateString('pt-BR')}` : ''}</span>
          </label>)}
          {pastas.length === 0 && arquivos.length === 0 && <div className="text-nevoa text-sm p-3">{f ? 'Nada com esse nome nesta pasta.' : 'Pasta vazia.'}</div>}
        </>}
      </div>
      <div className="p-4 border-t border-white/10 flex items-center gap-2 text-sm">
        <span className="text-nevoa text-xs">{sel.length ? `${sel.length} escolhido(s) · ${mb >= 1000 ? (mb / 1000).toFixed(1) + ' GB' : mb.toFixed(0) + ' MB'}. O Editor baixa do Drive ao enviar.` : 'Marque um ou mais arquivos (até 10).'}</span>
        <button onClick={onFechar} className="ml-auto rounded-full border border-white/15 px-4 py-1.5">Cancelar</button>
        <button disabled={!sel.length} onClick={() => { onEscolher(sel); onFechar() }} className="btn-laranja px-4 py-1.5">Anexar {sel.length || ''}</button>
      </div>
    </div>
  </div>
}

/** Botão 📎 com as duas origens: computador e Google Drive. */
export function BotaoAnexar({ onArquivos, onDrive, ja = [], accept, rotulo = '📎 Anexar', className = '' }: { onArquivos: (f: File[]) => void; onDrive: (d: DriveItem[]) => void; ja?: DriveItem[]; accept?: string; rotulo?: string; className?: string }) {
  const [menu, setMenu] = useState(false)
  const [drive, setDrive] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  return <span className="relative inline-block">
    <button type="button" onClick={() => setMenu(m => !m)} title="Anexar do computador ou do Google Drive" className={className || 'rounded-full border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5'}>{rotulo}</button>
    <input ref={input} type="file" multiple accept={accept} className="hidden" onChange={e => { const n = Array.from(e.target.files || []); e.target.value = ''; if (n.length) onArquivos(n) }} />
    {menu && <>
      <div className="fixed inset-0 z-40" onClick={() => setMenu(false)} />
      <div className="absolute z-50 bottom-full mb-2 left-0 w-56 rounded-xl border border-white/10 bg-[#0B193D] shadow-xl py-1 text-sm">
        <button onClick={() => { setMenu(false); input.current?.click() }} className="w-full text-left px-3 py-2 hover:bg-white/5">💻 Do computador</button>
        <button onClick={() => { setMenu(false); setDrive(true) }} className="w-full text-left px-3 py-2 hover:bg-white/5">☁ Do Google Drive</button>
      </div>
    </>}
    <DriveSeletor aberto={drive} onFechar={() => setDrive(false)} onEscolher={onDrive} ja={ja} />
  </span>
}

export function ChipsDrive({ itens, onTirar }: { itens: DriveItem[]; onTirar: (i: number) => void }) {
  if (!itens.length) return null
  return <>{itens.map((d, i) => <span key={d.raiz + d.caminho} className="selo" title={d.caminho}>☁ {d.nome} · {d.tamanho_mb >= 1000 ? (d.tamanho_mb / 1000).toFixed(1) + ' GB' : d.tamanho_mb.toFixed(0) + ' MB'} <button onClick={() => onTirar(i)} className="ml-1">✕</button></span>)}</>
}
