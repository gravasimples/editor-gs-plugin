import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type SkillsDemos as Dados, type DemoFormato } from '../api'

// Demos de skills (12/11/2026): para cada skill instalada, três edições de amostra com os mesmos brutos (Reels, ADS, aula), lado a lado,
// para ver o estilo e a capacidade de cada uma antes de decidir o que aproveitar. Gerar é clique humano; entra no fim da fila.
const ST: Record<string, string> = { todo: 'na fila', backlog: 'na fila', in_progress: 'editando', in_review: 'entregue', done: 'aprovado', blocked: 'travou', cancelled: 'cancelado', sumiu: 'pedido apagado' }
const ORDEM = ['reels', 'ads', 'aula']

function Celula({ f, rotulo, saida }: { f: DemoFormato | null; rotulo: string; saida: string }) {
  const vertical = saida === '9:16'
  return <div className="cartao overflow-hidden flex flex-col">
    <div className={`bg-black/40 flex items-center justify-center ${vertical ? 'aspect-[9/16] max-h-[420px]' : 'aspect-video'}`}>
      {f?.video
        ? <video src={f.video} controls playsInline preload="metadata" className="h-full w-full object-contain bg-black" />
        : <div className="text-nevoa text-xs text-center px-4">{f ? (f.status === 'blocked' ? 'O pedido travou. Abra a conversa para ver o motivo.' : `${ST[f.status || ''] || f.status || '…'}`) : 'Sem demo ainda'}</div>}
    </div>
    <div className="p-3 text-xs flex items-center justify-between gap-2">
      <span className="font-bold">{rotulo} <span className="text-nevoa font-normal">· {saida}</span></span>
      {f && <Link to={`/c/${f.issue_id}`} className="text-laranja hover:underline whitespace-nowrap">{f.codigo || 'conversa'} ›</Link>}
    </div>
  </div>
}

export default function SkillsDemos() {
  const [d, setD] = useState<Dados | null>(null); const [erro, setErro] = useState(''); const [aviso, setAviso] = useState(''); const [ocupado, setOcupado] = useState('')
  const carregar = () => api.skillsDemos().then(setD).catch(e => setErro(e.message))
  useEffect(() => { carregar(); const t = setInterval(carregar, 30000); return () => clearInterval(t) }, [])
  async function gerar(skill: string, formatos?: string) {
    setOcupado(skill + (formatos || '')); setErro(''); setAviso('')
    try { const r = await api.skillDemosGerar(skill, formatos); setAviso(r.criados.length ? `${r.criados.length} pedido(s) de demo na fila: ${r.criados.map(c => c.codigo).join(', ')}.` : 'Essas demos já estão na fila.'); await carregar() }
    catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  return <div className="max-w-6xl mx-auto px-4 py-8">
    <div className="flex items-baseline justify-between gap-3 flex-wrap">
      <h2 className="text-2xl">Demos de skills</h2>
      <Link to="/skills" className="text-sm text-laranja hover:underline">Banco de skills ›</Link>
    </div>
    <p className="text-nevoa mt-2 text-sm max-w-3xl">Cada skill instalada edita os mesmos três brutos: um <b>Reels</b> no padrão do Insta do GS, um <b>anúncio</b> no estilo dos ADS que rodam e uma <b>aula</b> com edição básica. Assim dá para comparar estilo e capacidade lado a lado antes de decidir o que vira padrão. As demos entram no fim da fila, depois dos seus pedidos.</p>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {aviso && <div className="text-green-300 text-sm mt-3">{aviso}</div>}
    {d && d.brutos_faltando.length > 0 && <div className="text-amber-300 text-sm mt-3">Faltam brutos de teste: {d.brutos_faltando.join(', ')}.</div>}
    {d && d.skills.length === 0 && <div className="cartao p-6 mt-6 text-sm text-nevoa">Nenhuma skill instalada. Instale pelo <Link to="/skills" className="text-laranja hover:underline">Banco de skills</Link>.</div>}
    {d && d.skills.map(s => {
      const feitas = ORDEM.filter(k => s.formatos[k]).length
      return <section key={s.skill} className="mt-8">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-lg font-bold">{s.nome}</h3>
            <div className="text-xs text-nevoa">{s.skill}{s.url && <> · <a href={s.url} target="_blank" rel="noreferrer" className="hover:underline">origem ↗</a></>}</div>
          </div>
          <button disabled={!!ocupado} onClick={() => gerar(s.skill)} className={`${feitas ? 'rounded-full border border-white/15 hover:bg-white/5' : 'btn-laranja'} px-4 py-1.5 text-sm disabled:opacity-50`}>
            {ocupado === s.skill ? 'abrindo…' : feitas ? '↻ Refazer as 3 demos' : '▶ Gerar as 3 demos'}
          </button>
        </div>
        <div className="grid gap-4 mt-3 md:grid-cols-[1fr_1fr_1.6fr] items-start">
          {d && ORDEM.map(k => <Celula key={k} f={s.formatos[k]} rotulo={d.formatos[k].rotulo} saida={d.formatos[k].saida} />)}
        </div>
      </section>
    })}
  </div>
}
