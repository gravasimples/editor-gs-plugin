import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Campanha } from '../api'

// Campanhas e lançamentos (03/11/2026): peças agrupadas pela etiqueta "campanha", com período, objetivo, meta e números do GSI.
const COR: Record<string, string> = { 'no ar': 'bg-green-500/20 text-green-300', planejada: 'bg-azul/30 text-white', encerrada: 'bg-white/10 text-nevoa', 'sem data': 'bg-white/10 text-nevoa' }
const VAZIA = { id: '', nome: '', inicio: '', fim: '', objetivo: '', mensagem: '', meta_pecas: '', redes: '', notas: '' }

export default function Campanhas() {
  const nav = useNavigate()
  const [lista, setLista] = useState<Campanha[] | null>(null); const [erro, setErro] = useState(''); const [aberta, setAberta] = useState('')
  const [form, setForm] = useState<typeof VAZIA | null>(null); const [ocupado, setOcupado] = useState('')
  const carregar = () => api.campanhas().then(r => setLista(r.campanhas)).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [])
  async function salvar() {
    if (!form) return; setErro(''); setOcupado('salvar')
    try { const fd = new FormData(); Object.entries(form).forEach(([k, v]) => fd.append(k, String(v ?? ''))); const c = await api.campanhaSalvar(fd); setForm(null); setAberta(c.id); carregar() }
    catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function analise(c: Campanha) {
    if (!confirm(`Pedir ao Editor a análise da campanha "${c.nome}"? Vira um pedido na fila.`)) return
    setOcupado('analise'); try { const conv = await api.campanhaAnalise(c.id); nav(`/c/${conv.id}`) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function ligar(c: Campanha, slugs: string[]) { setOcupado('ligar'); try { await api.campanhaLigar(c.id, slugs); carregar() } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function apagar(c: Campanha) { if (!confirm(`Apagar a campanha "${c.nome}"? As peças continuam com a etiqueta.`)) return; await api.campanhaApagar(c.id).catch(e => setErro(e.message)); setAberta(''); carregar() }
  const editar = (c: Campanha) => setForm({ id: c.id, nome: c.nome, inicio: c.inicio || '', fim: c.fim || '', objetivo: c.objetivo || '', mensagem: c.mensagem || '', meta_pecas: c.meta_pecas ? String(c.meta_pecas) : '', redes: (c.redes || []).join(','), notas: c.notas || '' })

  return <div className="max-w-5xl mx-auto px-4 py-8">
    <div className="flex flex-wrap items-end gap-3"><div><h2 className="text-2xl">Campanhas e lançamentos</h2>
      <p className="text-nevoa mt-1 text-sm">Cada campanha junta as peças com a etiqueta dela: período, objetivo, meta de peças e os números somados no fim. Peça pedida "para a campanha" já nasce com a etiqueta.</p></div>
      <button onClick={() => setForm({ ...VAZIA })} className="btn-laranja px-4 py-2 ml-auto">＋ Nova campanha</button></div>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}

    {form && <div className="cartao p-4 mt-4 text-sm grid gap-2">
      <div className="font-bold">{form.id ? 'Editar campanha' : 'Nova campanha'}</div>
      <input value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} placeholder="Nome (ex.: Black 2026, Níver, Aula ao vivo de dezembro)" className="bg-card border border-white/15 rounded-xl px-3 py-2" />
      <div className="flex flex-wrap gap-2 items-center"><label className="text-nevoa">Início <input type="date" value={form.inicio} onChange={e => setForm({ ...form, inicio: e.target.value })} className="bg-card border border-white/15 rounded-xl px-2 py-1" /></label>
        <label className="text-nevoa">Fim <input type="date" value={form.fim} onChange={e => setForm({ ...form, fim: e.target.value })} className="bg-card border border-white/15 rounded-xl px-2 py-1" /></label>
        <label className="text-nevoa">Meta <input type="number" min={1} value={form.meta_pecas} onChange={e => setForm({ ...form, meta_pecas: e.target.value })} className="w-16 bg-card border border-white/15 rounded-xl px-2 py-1" /> peças</label>
        {['instagram', 'youtube', 'tiktok'].map(r => { const on = form.redes.split(',').includes(r); return <button key={r} onClick={() => setForm({ ...form, redes: (on ? form.redes.split(',').filter(x => x && x !== r) : [...form.redes.split(',').filter(Boolean), r]).join(',') })} className={`rounded-full border px-3 py-1 ${on ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa'}`}>{r}</button> })}</div>
      <input value={form.objetivo} onChange={e => setForm({ ...form, objetivo: e.target.value })} placeholder="Objetivo (ex.: aquecer a audiência para a aula de dezembro)" className="bg-card border border-white/15 rounded-xl px-3 py-2" />
      <input value={form.mensagem} onChange={e => setForm({ ...form, mensagem: e.target.value })} placeholder="Mensagem-chave (o Editor recebe isso em cada pedido da campanha)" className="bg-card border border-white/15 rounded-xl px-3 py-2" />
      <textarea value={form.notas} onChange={e => setForm({ ...form, notas: e.target.value })} rows={2} placeholder="Notas (opcional)" className="bg-card border border-white/15 rounded-xl px-3 py-2" />
      <div className="text-xs text-nevoa">Peças orgânicas seguem sem preço, oferta ou falsa escassez: o revisor de marca continua valendo.</div>
      <div className="flex gap-2"><button onClick={salvar} disabled={!!ocupado || !form.nome.trim()} className="btn-laranja px-4 py-1.5 disabled:opacity-40">{ocupado === 'salvar' ? '…' : 'Salvar'}</button><button onClick={() => setForm(null)} className="rounded-full border border-white/15 px-4 py-1.5">Cancelar</button></div>
    </div>}

    {!lista && <div className="text-nevoa mt-6">Carregando…</div>}
    {lista && lista.length === 0 && !form && <div className="cartao p-6 mt-6 text-sm text-nevoa">Nenhuma campanha ainda. Crie a primeira (Black, Níver, uma aula ao vivo) e peça as peças por aqui; o app junta tudo e soma os números no fim.</div>}
    <div className="grid gap-3 mt-5">{lista?.map(c => <div key={c.id} className="cartao p-4 text-sm">
      <button onClick={() => setAberta(aberta === c.id ? '' : c.id)} className="w-full text-left flex flex-wrap items-center gap-2">
        <span className="font-bold text-base">{c.nome}</span><span className={`rounded-full px-2 py-0.5 text-[11px] ${COR[c.situacao]}`}>{c.situacao}</span>
        <span className="text-nevoa text-xs">{c.inicio ? `${c.inicio.split('-').reverse().join('/')}${c.fim ? ` a ${c.fim.split('-').reverse().join('/')}` : ''}` : 'sem período'}</span>
        <span className="ml-auto text-xs text-nevoa">{c.n_pecas}{c.meta_pecas ? `/${c.meta_pecas}` : ''} peças · {c.n_publicadas} publicadas{c.views != null ? ` · ${c.views.toLocaleString('pt-BR')} views` : ''}{c.razao_mediana != null ? ` · ${c.razao_mediana}× mediana` : ''}</span>
      </button>
      {c.meta_pecas ? <div className="h-1.5 rounded-full bg-white/10 overflow-hidden mt-2"><div className="h-full bg-laranja" style={{ width: `${Math.min(100, (c.progresso || 0) * 100)}%` }} /></div> : null}
      {aberta === c.id && <div className="mt-3 grid gap-3">
        {(c.objetivo || c.mensagem) && <div className="text-xs">{c.objetivo && <div><span className="text-nevoa">Objetivo:</span> {c.objetivo}</div>}{c.mensagem && <div><span className="text-nevoa">Mensagem-chave:</span> {c.mensagem}</div>}</div>}
        <div className="flex flex-wrap gap-2">
          <Link to={`/novo?campanha=${encodeURIComponent(c.id)}`} className="btn-laranja px-3 py-1.5 text-xs">＋ Pedido para esta campanha</Link>
          <button onClick={() => analise(c)} disabled={!!ocupado} className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 text-xs hover:bg-laranja/10">📊 Pedir análise ao Editor</button>
          <Link to={`/pecas?campanha=${encodeURIComponent(c.nome)}`} className="rounded-full border border-white/15 px-3 py-1.5 text-xs hover:bg-white/5">Ver em Peças</Link>
          <button onClick={() => editar(c)} className="rounded-full border border-white/15 px-3 py-1.5 text-xs hover:bg-white/5">Editar</button>
          <button onClick={() => apagar(c)} className="rounded-full border border-white/15 px-3 py-1.5 text-xs text-nevoa hover:bg-white/5 ml-auto">Apagar</button>
        </div>
        {Object.keys(c.formatos).length > 0 && <div className="text-xs text-nevoa">Por formato: {Object.entries(c.formatos).map(([f, n]) => `${f} ${n}`).join(' · ')}{c.melhor && <> · melhor: <Link to={`/pecas/${c.melhor.slug}`} className="text-laranja hover:underline">{c.melhor.titulo}</Link>{c.melhor.vs_mediana != null ? ` (${c.melhor.vs_mediana}×)` : ''}</>}</div>}
        {c.pecas.length === 0 ? <div className="text-xs text-nevoa">Nenhuma peça com esta etiqueta ainda.</div> :
          <table className="w-full text-xs"><thead><tr className="text-nevoa text-left"><th className="py-1">Peça</th><th>Formato</th><th>Estado</th><th>Publicada</th><th className="text-right">Views</th><th className="text-right">Razão</th></tr></thead>
            <tbody>{c.pecas.map(p => <tr key={p.slug} className="border-t border-white/5"><td className="py-1"><Link to={`/pecas/${p.slug}`} className="hover:underline">{p.titulo}</Link>{p.codigo && <span className="text-nevoa"> · {p.codigo}</span>}</td><td>{p.formato || '-'}</td><td>{p.estado}</td><td>{p.publicado_em?.slice(0, 10) || '-'}</td><td className="text-right">{p.views?.toLocaleString('pt-BR') ?? '-'}</td><td className="text-right">{p.vs_mediana != null ? `${p.vs_mediana}×` : '-'}</td></tr>)}</tbody></table>}
        {c.sugestoes.length > 0 && <div className="rounded-xl bg-black/20 p-3 text-xs"><div className="text-nevoa">Publicadas no período sem campanha (ou como Orgânico):</div>
          {c.sugestoes.map(s => <div key={s.slug} className="flex gap-2 mt-1"><span className="flex-1 truncate">{s.titulo}</span><span className="text-nevoa">{s.publicado_em?.slice(0, 10)}</span><button onClick={() => ligar(c, [s.slug])} disabled={!!ocupado} className="text-laranja hover:underline">ligar</button></div>)}</div>}
      </div>}
    </div>)}</div>
  </div>
}
