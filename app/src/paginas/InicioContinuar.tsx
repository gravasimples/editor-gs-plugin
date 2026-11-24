import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AprovacaoDecisao, type AprovacaoEntrega, type Conversa } from '../api'
import { Icone } from '../Icones'
import { ErroCarga, Esqueleto, ha } from '../Estados'
import { Previa } from '../Previa'

// "Continuar de onde parou" no Início (design fase 2, 17/11/2026). Só rotas que já existem: /conversas (pedidos em andamento),
// /aprovacoes (decisões e entregas esperando, com prévia), /laboratorio (para_testar) e /receitas (propostas, vem do Início).
type Item = { id: string; titulo: string; codigo?: string | null; quando: string; status: 'decisao' | 'editando' | 'baixando' | 'fila' | 'pausado' | 'entregue'; capa?: string | null; video?: string | null; tipo: string; detalhe?: string; entrega?: boolean }
const STATUS: Record<Item['status'], { rotulo: string; cor: string; pulsa?: boolean }> = {
  decisao: { rotulo: 'espera sua decisão', cor: 'bg-laranja text-marinho' },
  editando: { rotulo: 'editando', cor: 'bg-laranja/20 text-laranja', pulsa: true },
  baixando: { rotulo: 'baixando do Drive', cor: 'bg-azul/40 text-white', pulsa: true },
  fila: { rotulo: 'na fila', cor: 'bg-white/10 text-nevoa' },
  pausado: { rotulo: 'pausado', cor: 'bg-white/10 text-nevoa' },
  entregue: { rotulo: 'pronto para aprovar', cor: 'bg-green-500/20 text-green-300' },
}
const ORDEM: Item['status'][] = ['decisao', 'editando', 'baixando', 'fila', 'pausado', 'entregue']
const ehTeste = (p?: string | null) => !!p && /^testes?\b/i.test(p)

function montar(cs: Conversa[], decisoes: AprovacaoDecisao[], entregas: AprovacaoEntrega[]): Item[] {
  const testes = new Set(cs.filter(c => c.teste).map(c => c.id)); const vistos = new Set<string>(); const out: Item[] = []
  const por = (it: Item) => { if (vistos.has(it.id) || testes.has(it.id)) return; vistos.add(it.id); out.push(it) }
  decisoes.forEach(d => por({ id: d.id, titulo: d.titulo, codigo: d.codigo, quando: d.atualizado, status: 'decisao', tipo: 'decisao', detalhe: d.interacao.titulo }))
  cs.filter(c => !c.excluida && (c.executando || c.drive?.estado === 'baixando' || ['in_progress', 'todo', 'backlog', 'blocked'].includes(c.status))).forEach(c => por({
    id: c.id, titulo: c.titulo, codigo: c.codigo, quando: c.atualizado, tipo: 'video',
    status: c.drive?.estado === 'baixando' ? 'baixando' : c.executando || c.status === 'in_progress' ? 'editando' : c.status === 'blocked' ? 'pausado' : 'fila' }))
  entregas.filter(e => !ehTeste(e.pasta)).slice().sort((a, b) => (b.atualizado || '').localeCompare(a.atualizado || '')).forEach(e => por({
    id: e.id, titulo: e.titulo, codigo: e.codigo, quando: e.atualizado, status: 'entregue', entrega: true,
    capa: e.capa?.url || e.imagens[0]?.url, video: e.video?.url, tipo: e.video ? 'video' : e.imagens.length > 1 ? 'carrossel' : e.imagens.length || e.capa ? 'imagem' : 'texto', detalhe: e.textos.gancho }))
  return out.sort((a, b) => ORDEM.indexOf(a.status) - ORDEM.indexOf(b.status) || (b.quando || '').localeCompare(a.quando || '')).slice(0, 8)
}

function Cartao({ it, onAprovado }: { it: Item; onAprovado: (id: string) => void }) {
  const s = STATUS[it.status]; const [busy, setBusy] = useState(false); const [msg, setMsg] = useState('')
  const aprovar = async () => { setBusy(true); try { await api.aprovar(it.id); onAprovado(it.id) } catch (e: any) { setMsg(e.message) } finally { setBusy(false) } }
  return <div className="cartao group flex w-56 shrink-0 snap-start flex-col overflow-hidden border border-white/5 transition hover:-translate-y-0.5 hover:border-white/15">
    <Link to={`/c/${it.id}`} className="relative block">
      <Previa capa={it.capa} video={it.video} tipo={it.tipo} className="aspect-[16/10]" />
      <span className={`absolute left-2 top-2 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold backdrop-blur ${s.cor}`}>{s.pulsa && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}{s.rotulo}</span>
    </Link>
    <div className="flex flex-1 flex-col p-3">
      <Link to={`/c/${it.id}`} className="line-clamp-2 text-sm font-bold leading-snug hover:text-laranja">{it.titulo}</Link>
      {it.detalhe && <div className="mt-1 line-clamp-2 text-[11px] text-white/70">{it.detalhe}</div>}
      <div className="mt-auto flex items-center gap-2 pt-2 text-[11px] text-nevoa"><span>{it.codigo ? `${it.codigo} · ` : ''}{ha(it.quando)}</span>
        {it.entrega ? <button onClick={aprovar} disabled={busy} className="ml-auto rounded-full border border-laranja/60 px-2.5 py-0.5 text-laranja hover:bg-laranja/10">{busy ? '…' : 'Aprovar'}</button>
          : <Link to={`/c/${it.id}`} className="ml-auto inline-flex items-center gap-1 text-laranja">{it.status === 'decisao' ? 'decidir' : 'abrir'}<Icone nome="seta" className="h-3 w-3" /></Link>}</div>
      {msg && <div className="mt-1 text-[11px] text-red-300">{msg}</div>}
    </div>
  </div>
}

export function Continuar({ propostas }: { propostas: number }) {
  const [itens, setItens] = useState<Item[] | null>(null); const [erro, setErro] = useState(''); const [nLab, setNLab] = useState(0); const [nAprov, setNAprov] = useState(0)
  const carregar = () => {
    setErro('')
    Promise.all([api.conversas(), api.aprovacoes()]).then(([cs, ap]) => { setItens(montar(cs, ap.decisoes, ap.entregas)); setNAprov(ap.n) }).catch(e => setErro(String(e?.message || e)))
  }
  useEffect(() => { carregar(); api.laboratorio().then(d => setNLab(d.para_testar)).catch(() => {}) }, [])
  const atalho = (to: string, icone: string, n: number, rotulo: string, sub: string) => <Link to={to} className={`group flex items-center gap-3 rounded-[20px] border p-3 transition hover:-translate-y-0.5 ${n ? 'border-laranja/30 bg-laranja/5 hover:bg-laranja/10' : 'border-white/5 bg-card hover:border-white/15'}`}>
    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${n ? 'bg-laranja text-marinho' : 'bg-white/5 text-nevoa'}`}><Icone nome={icone} className="h-5 w-5" /></span>
    <span className="min-w-0"><span className="block text-sm"><b className={`font-[Unbounded] ${n ? 'text-laranja' : ''}`}>{n}</b> {rotulo}</span><span className="block truncate text-[11px] text-nevoa">{sub}</span></span>
    <span className="ml-auto text-nevoa transition group-hover:translate-x-0.5 group-hover:text-laranja"><Icone nome="seta" className="h-4 w-4" /></span></Link>
  return <div className="mt-8">
    <div className="mb-2 flex items-center text-xs uppercase tracking-wider text-nevoa">Continuar de onde parou{nAprov > 0 && <Link to="/aprovacoes" className="ml-auto normal-case tracking-normal text-laranja hover:underline">{nAprov} esperando você ›</Link>}</div>
    {erro ? <ErroCarga erro={erro} onTentar={carregar} /> : !itens ? <Esqueleto tipo="faixa" n={4} /> : itens.length
      ? <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 [scrollbar-width:thin]">{itens.map(it => <Cartao key={it.id} it={it} onAprovado={id => { setItens(xs => xs && xs.filter(x => x.id !== id)); setNAprov(n => Math.max(0, n - 1)) }} />)}</div>
      : <div className="flex items-center gap-3 rounded-[20px] border border-dashed border-white/10 px-4 py-4 text-sm text-nevoa"><span className="text-laranja"><Icone nome="aprovacoes" /></span>Nada em andamento nem esperando você. Descreva um pedido acima para começar.</div>}
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {atalho('/laboratorio', 'laboratorio', nLab, nLab === 1 ? 'recurso novo para testar' : 'recursos novos para testar', nLab ? 'Laboratório: siga os passos e marque Funcionou ou Deu problema' : 'Laboratório em dia')}
      {atalho('/estilos?aba=receitas#propostas', 'receitas', propostas, propostas === 1 ? 'proposta de receita' : 'propostas de receitas', propostas ? 'Estilos › Receitas › Propostas: aprovar ou recusar' : 'Nenhuma proposta pendente')}
    </div>
  </div>
}
