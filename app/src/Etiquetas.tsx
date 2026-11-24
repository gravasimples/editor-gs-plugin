import { useEffect, useState } from 'react'
import { api, type Etiquetas as Et, type PecaEtiquetas, type PecaOpcoes } from './api'

const ROTULO: Record<string, string> = { reel: 'Reel', story: 'Story', carrossel: 'Carrossel', youtube: 'YouTube', short: 'Short', imagem: 'Imagem', apostila: 'Apostila', outro: 'Outro', thiago: 'voz do Thiago', clonada: 'voz clonada', sintetica: 'voz sintética', sem: 'sem voz', pedido: 'pedido', ideia: 'ideia', notion: 'Notion', pulso: 'pulso', automacao: 'automação', clipador: 'Clipador', referencia: 'referência' }
export const rotulo = (v?: string) => (v ? ROTULO[v] || v : '')

/** Chips de etiquetas da peça (leitura). */
export function ChipsEtiquetas({ e, compacto = false }: { e: Et; compacto?: boolean }) {
  const itens: [string, string | undefined, string][] = [['campanha', e.campanha, 'bg-laranja/20 text-laranja'], ['pilar', e.pilar, 'bg-azul/30 text-white'], ['formato', rotulo(e.formato), 'bg-white/10 text-nevoa'], ['voz', rotulo(e.voz), 'bg-white/10 text-nevoa'], ['origem', rotulo(e.origem), 'bg-white/10 text-nevoa']]
  return <span className="inline-flex flex-wrap gap-1">{itens.filter(([, v]) => v).map(([k, v, cls]) => <span key={k} className={`rounded-full px-2 py-0.5 text-[11px] ${cls}`} title={k}>{v}</span>)}{!compacto && e.gancho && <span className="text-[11px] text-nevoa">“{e.gancho}”</span>}</span>
}

/** Formulário de etiquetas da peça: campanha, pilar, formato, voz, origem, CTA, gancho, redes. Mostra o que foi inferido e o que é escolha humana. */
export function FormEtiquetas({ slug, inicial, onSalvo }: { slug: string; inicial: PecaEtiquetas; inicial2?: never; onSalvo?: (p: PecaEtiquetas) => void }) {
  const [op, setOp] = useState<PecaOpcoes | null>(null)
  const [f, setF] = useState<Et>({ ...inicial.etiquetas })
  const [salvando, setSalvando] = useState(false); const [msg, setMsg] = useState(''); const [novo, setNovo] = useState<{ campo: string; valor: string } | null>(null)
  useEffect(() => { api.pecas().then(r => setOp(r.opcoes)).catch(() => {}) }, [])
  useEffect(() => { setF({ ...inicial.etiquetas }) }, [inicial.atualizado, slug])
  async function salvar() {
    setSalvando(true); setMsg('')
    try {
      const dados: Record<string, string> = {}; const limpar: string[] = []
      for (const k of ['campanha', 'pilar', 'gancho', 'formato', 'cta', 'voz', 'origem', 'nota'] as const) {
        const v = (f as any)[k] as string | undefined
        if (v && v !== (inicial.auto as any)[k]) dados[k] = v
        else if (inicial.humanas && (inicial.humanas as any)[k] && (!v || v === (inicial.auto as any)[k])) limpar.push(k)
      }
      if (f.redes) dados.redes = f.redes.join(',')
      if (limpar.length) dados.limpar = limpar.join(',')
      const r = await api.pecaEtiquetas(slug, dados); setMsg(`Etiquetas gravadas (${r.atualizado?.slice(11, 16)}).`); onSalvo?.(r)
    } catch (e: any) { setMsg(e.message) } finally { setSalvando(false) }
  }
  async function adicionar() {
    if (!novo || !novo.valor.trim()) return
    try { const r = await api.pecaOpcao(novo.campo, novo.valor.trim()); setOp(o => o ? { ...o, [novo.campo]: r[novo.campo] } : o); setF({ ...f, [novo.campo === 'campanhas' ? 'campanha' : novo.campo === 'pilares' ? 'pilar' : 'cta']: novo.valor.trim() }); setNovo(null) } catch (e: any) { setMsg(e.message) }
  }
  const auto = (k: keyof Et) => (inicial.auto as any)[k] && (f as any)[k] === (inicial.auto as any)[k] ? <span className="text-[10px] text-nevoa ml-1">(inferido)</span> : null
  const Sel = ({ k, lista, vazio = '(sem)' }: { k: keyof Et; lista: string[]; vazio?: string }) => <select value={(f as any)[k] || ''} onChange={e => setF({ ...f, [k]: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1 text-xs"><option value="">{vazio}</option>{lista.map(x => <option key={x} value={x}>{rotulo(x) || x}</option>)}</select>
  if (!op) return <div className="text-nevoa text-xs">…</div>
  return <div className="grid gap-2 text-xs">
    <div className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-1">Campanha <Sel k="campanha" lista={op.campanhas} /><button onClick={() => setNovo({ campo: 'campanhas', valor: '' })} className="text-nevoa hover:text-white" title="nova campanha">+</button></label>
      <label className="flex items-center gap-1">Pilar <Sel k="pilar" lista={op.pilares} /><button onClick={() => setNovo({ campo: 'pilares', valor: '' })} className="text-nevoa hover:text-white" title="novo pilar">+</button></label>
      <label className="flex items-center gap-1">Formato <Sel k="formato" lista={op.formatos} />{auto('formato')}</label>
      <label className="flex items-center gap-1">Voz <Sel k="voz" lista={op.vozes} />{auto('voz')}</label>
      <label className="flex items-center gap-1">Origem <Sel k="origem" lista={op.origens} />{auto('origem')}</label>
      <label className="flex items-center gap-1">CTA <Sel k="cta" lista={op.ctas} /><button onClick={() => setNovo({ campo: 'ctas', valor: '' })} className="text-nevoa hover:text-white" title="novo CTA">+</button></label>
    </div>
    {novo && <div className="flex items-center gap-2"><input autoFocus value={novo.valor} onChange={e => setNovo({ ...novo, valor: e.target.value })} onKeyDown={e => { if (e.key === 'Enter') adicionar() }} placeholder={`novo item em ${novo.campo}`} className="rounded-full bg-black/40 px-3 py-1 outline-none" /><button onClick={adicionar} className="rounded-full border border-laranja/60 text-laranja px-3 py-1">Adicionar</button><button onClick={() => setNovo(null)} className="text-nevoa">cancelar</button></div>}
    <label className="flex items-center gap-2">Gancho <input value={f.gancho || ''} onChange={e => setF({ ...f, gancho: e.target.value })} className="flex-1 rounded-full bg-black/40 px-3 py-1 outline-none" placeholder="frase de abertura da peça" />{auto('gancho')}</label>
    <div className="flex flex-wrap items-center gap-2">Redes {op.redes.map(r => <label key={r} className="flex items-center gap-1"><input type="checkbox" checked={(f.redes || []).includes(r)} onChange={e => setF({ ...f, redes: e.target.checked ? [...(f.redes || []), r] : (f.redes || []).filter(x => x !== r) })} className="accent-[#F79615]" />{r}</label>)}
      <button onClick={salvar} disabled={salvando} className="ml-auto rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">{salvando ? 'Gravando…' : 'Gravar etiquetas'}</button></div>
    {msg && <div className="text-laranja">{msg}</div>}
    {inicial.atualizado && <div className="text-nevoa">última gravação {inicial.atualizado.replace('T', ' ')} por {inicial.por}</div>}
  </div>
}
