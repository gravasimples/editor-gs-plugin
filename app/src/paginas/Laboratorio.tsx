import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Laboratorio as Dados, type Novidade } from '../api'

// Laboratório (13/11/2026): cada recurso novo chega aqui com o passo a passo para o Raphael testar. Funcionou / Deu problema fica gravado
// (workspace/laboratorio/avaliacoes.json); problema vira anotação para a próxima rodada de construção.
const ROT: Record<string, string> = { para_testar: 'para testar', funcionou: 'funcionou', com_problema: 'deu problema', ignorado: 'deixei para depois' }
const COR: Record<string, string> = { para_testar: 'bg-laranja/15 text-laranja', funcionou: 'bg-green-400/15 text-green-300', com_problema: 'bg-red-400/15 text-red-300', ignorado: 'bg-white/5 text-nevoa' }
const FILTROS = [['', 'Tudo'], ['para_testar', 'Para testar'], ['com_problema', 'Com problema'], ['funcionou', 'Funcionou']] as const

export default function Laboratorio() {
  const [d, setD] = useState<Dados | null>(null)
  const [erro, setErro] = useState('')
  const [filtro, setFiltro] = useState('')
  const [feitos, setFeitos] = useState<Record<string, number[]>>({})
  const [problema, setProblema] = useState<{ id: string; nota: string } | null>(null)
  const [ocupado, setOcupado] = useState('')
  const carregar = () => api.laboratorio().then(setD).catch(e => setErro(String(e.message || e)))
  useEffect(() => { carregar() }, [])

  async function avaliar(it: Novidade, estado: string, nota = '') {
    setOcupado(it.id); setErro('')
    try { await api.laboratorioAvaliar(it.id, estado, nota); setProblema(null); await carregar(); window.dispatchEvent(new Event('laboratorio')) }
    catch (e: any) { setErro(String(e.message || e)) }
    finally { setOcupado('') }
  }
  const marcar = (id: string, i: number) => setFeitos(f => { const a = f[id] || []; return { ...f, [id]: a.includes(i) ? a.filter(x => x !== i) : [...a, i] } })
  const itens = (d?.itens || []).filter(i => !filtro || i.estado === filtro)

  return <div className="p-4 md:p-8 max-w-4xl">
    <h1 className="font-[Unbounded] text-2xl font-bold">🧪 Laboratório</h1>
    <p className="text-nevoa mt-2 text-sm">O que ficou pronto para você testar. Siga os passos, marque <b>Funcionou</b> ou <b>Deu problema</b>. O problema vira anotação e entra na próxima rodada de construção.</p>
    {d && <div className="mt-4 flex flex-wrap gap-2 text-xs">
      {FILTROS.map(([k, r]) => <button key={k} onClick={() => setFiltro(k)} className={`rounded-full px-3 py-1 border ${filtro === k ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/10 text-nevoa hover:bg-white/5'}`}>
        {r}{k === 'para_testar' && d.para_testar ? ` · ${d.para_testar}` : ''}{k === 'com_problema' && d.com_problema ? ` · ${d.com_problema}` : ''}</button>)}
    </div>}
    {erro && <div className="mt-3 text-sm text-red-300">{erro}</div>}
    {!d && !erro && <div className="mt-6 text-nevoa text-sm">Carregando…</div>}
    {d && itens.length === 0 && <div className="mt-6 text-nevoa text-sm">Nada aqui.</div>}
    <div className="mt-4 grid gap-3">
      {itens.map(it => <div key={it.id} className={`cartao p-4 text-sm ${it.estado === 'para_testar' ? 'ring-1 ring-laranja/30' : ''}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-bold">{it.titulo}</span>
          <span className={`rounded-full px-2 py-0.5 text-[11px] ${COR[it.estado]}`}>{ROT[it.estado]}</span>
          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-nevoa">{it.area}</span>
          <span className="ml-auto text-[11px] text-nevoa">{it.data.split('-').reverse().slice(0, 2).join('/')}</span>
        </div>
        <div className="text-nevoa mt-1">{it.o_que_e}</div>
        <ol className="mt-3 grid gap-1">
          {it.como_testar.map((p, i) => { const ok = (feitos[it.id] || []).includes(i); return <li key={i}>
            <button onClick={() => marcar(it.id, i)} className={`flex items-start gap-2 text-left ${ok ? 'text-nevoa line-through' : ''}`}>
              <span className={`mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${ok ? 'border-laranja bg-laranja text-[#000921]' : 'border-white/30'}`}>{ok ? '✓' : i + 1}</span>{p}</button>
          </li> })}
        </ol>
        {it.nota && <div className="mt-2 rounded-xl bg-black/30 px-3 py-2 text-xs"><b>Sua nota:</b> {it.nota} <span className="text-nevoa">· {it.avaliado_em.slice(0, 16).replace('T', ' ')}</span></div>}
        {problema?.id === it.id
          ? <form onSubmit={e => { e.preventDefault(); avaliar(it, 'com_problema', problema.nota) }} className="mt-3 grid gap-2">
              <textarea autoFocus value={problema.nota} onChange={e => setProblema({ id: it.id, nota: e.target.value })} rows={3} placeholder="O que você fez e o que apareceu (ex.: cliquei em Renderizar, travou em 40%)" className="rounded-xl bg-black/30 px-3 py-2" />
              <div className="flex gap-2 text-xs"><button disabled={!!ocupado || !problema.nota.trim()} className="rounded-full border border-red-400/60 text-red-300 px-3 py-1.5 hover:bg-red-400/10">Mandar problema</button><button type="button" onClick={() => setProblema(null)} className="rounded-full border border-white/15 px-3 py-1.5">cancelar</button></div>
            </form>
          : <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {it.onde && <Link to={it.onde} className="btn-laranja px-3 py-1.5">Abrir para testar ›</Link>}
              {it.estado !== 'funcionou' && <button disabled={!!ocupado} onClick={() => avaliar(it, 'funcionou')} className="rounded-full border border-green-400/60 text-green-300 px-3 py-1.5 hover:bg-green-400/10">✅ Funcionou</button>}
              <button disabled={!!ocupado} onClick={() => setProblema({ id: it.id, nota: '' })} className="rounded-full border border-red-400/60 text-red-300 px-3 py-1.5 hover:bg-red-400/10">⚠ Deu problema</button>
              {it.estado === 'para_testar' && <button disabled={!!ocupado} onClick={() => avaliar(it, 'ignorado')} className="rounded-full border border-white/15 px-3 py-1.5 text-nevoa hover:bg-white/5">depois</button>}
              {it.estado !== 'para_testar' && <button disabled={!!ocupado} onClick={() => avaliar(it, 'para_testar')} className="rounded-full border border-white/15 px-3 py-1.5 text-nevoa hover:bg-white/5">↺ testar de novo</button>}
            </div>}
      </div>)}
    </div>
  </div>
}
