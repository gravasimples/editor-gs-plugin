import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, PASTA_TESTES, type Conversa } from './api'
import Inicio from './paginas/Inicio'
import ConversaPagina from './paginas/Conversa'
import { pedirNovaPasta } from './Pastas'
import { MenuConversa } from './MenuConversa'
// páginas sob demanda (code-splitting): o bundle único tinha 522 KB; Início e Conversa ficam no principal (11/11/2026)
const Fluxos = lazy(() => import('./paginas/Fluxos'))
const Estilos = lazy(() => import('./paginas/Estilos'))
const VozPagina = lazy(() => import('./paginas/Voz'))
const Biblioteca = lazy(() => import('./paginas/Biblioteca'))
const Ideias = lazy(() => import('./paginas/Ideias'))
const Ajuda = lazy(() => import('./paginas/Ajuda'))
const Laboratorio = lazy(() => import('./paginas/Laboratorio'))
const Referencias = lazy(() => import('./paginas/Referencias'))
const Clipador = lazy(() => import('./paginas/Clipador'))
const Acervo = lazy(() => import('./paginas/Acervo'))
const Ganchos = lazy(() => import('./paginas/Ganchos'))
const Redes = lazy(() => import('./paginas/Redes'))
const MarcaPagina = lazy(() => import('./paginas/Marca'))
const Textos = lazy(() => import('./paginas/Textos'))
const Teleprompter = lazy(() => import('./paginas/Teleprompter'))
const Operacao = lazy(() => import('./paginas/Operacao'))
const PecasLista = lazy(() => import('./paginas/Pecas').then(m => ({ default: m.PecasLista })))
const PecaFichaPagina = lazy(() => import('./paginas/Pecas').then(m => ({ default: m.PecaFichaPagina })))
const Metricas = lazy(() => import('./paginas/Metricas'))
const Campanhas = lazy(() => import('./paginas/Campanhas'))
const Aprovacoes = lazy(() => import('./paginas/Aprovacoes'))
const Lixeira = lazy(() => import('./paginas/Lixeira'))
const Skills = lazy(() => import('./paginas/Skills'))
const SkillsDemos = lazy(() => import('./paginas/SkillsDemos'))

const situacao = (c: Conversa) => c.drive?.estado === 'baixando' ? 'baixando do Drive…' : c.executando ? 'editando…' : (c.status === 'in_review' ? 'entregue' : c.status === 'done' ? 'concluído' : c.status === 'blocked' ? 'pausado' : 'na fila')

// Menu em seções (análise de 11/11/2026): uso diário em cima, ferramentas de engenharia recolhidas em Ajustes. Rotas iguais.
type ItemNav = { to: string; rotulo: string; icone: string }
const grupos: { titulo: string; itens: ItemNav[] }[] = [
  { titulo: 'Pedidos', itens: [{ to: '/aprovacoes', rotulo: 'Aprovações', icone: '✓' }, { to: '/laboratorio', rotulo: 'Laboratório', icone: '🧪' }, { to: '/campanhas', rotulo: 'Campanhas', icone: '🎯' }] },
  { titulo: 'Criar', itens: [{ to: '/clipador', rotulo: 'Cortes de vídeo longo', icone: '✂' }, { to: '/ideias', rotulo: 'Ideias', icone: '💡' }] },
  { titulo: 'Entregas', itens: [{ to: '/biblioteca', rotulo: 'Biblioteca', icone: '▤' }, { to: '/pecas', rotulo: 'Peças', icone: '◫' }, { to: '/textos', rotulo: 'Textos', icone: '✎' }] },
  { titulo: 'Repertório', itens: [{ to: '/estilos', rotulo: 'Estilos', icone: 'Aa' }, { to: '/demos', rotulo: 'Demos de skills', icone: '▶' }, { to: '/fluxos', rotulo: 'Fluxos', icone: '⟳' }, { to: '/referencias', rotulo: 'Referências', icone: '🔗' },
    { to: '/ganchos', rotulo: 'Ganchos', icone: '🪝' }, { to: '/acervo', rotulo: 'Busca por fala', icone: '🔎' }, { to: '/marca', rotulo: 'Marca', icone: '◆' }] },
  { titulo: 'Resultados', itens: [{ to: '/metricas', rotulo: 'Métricas', icone: '📈' }, { to: '/redes', rotulo: 'Redes e calendário', icone: '📅' }] },
]
const ajustes: ItemNav[] = [{ to: '/voz', rotulo: 'Voz', icone: '🎙' }, { to: '/skills', rotulo: 'Banco de skills', icone: '🧩' }, { to: '/operacao', rotulo: 'Operação', icone: '⚙' },
  { to: '/ajuda', rotulo: 'Ajuda · celular', icone: '📱' }]
const nav: ItemNav[] = [{ to: '/', rotulo: 'Novo pedido', icone: '✦' }, ...grupos.flatMap(g => g.itens), ...ajustes.filter(a => a.to !== '/ajuda')]

declare const __BUILD_ID__: string

/** Faixa "Nova versão": compara o build deste app com /versao.json do gateway (a cada minuto e ao voltar para a aba). Resolve o PWA do celular preso numa versão antiga. */
function NovaVersao() {
  const [nova, setNova] = useState(false)
  useEffect(() => {
    const ver = () => api.versao().then(v => { if (v.build && v.build !== __BUILD_ID__) setNova(true) }).catch(() => {})
    ver(); const t = setInterval(ver, 60_000); const vis = () => { if (document.visibilityState === 'visible') ver() }
    document.addEventListener('visibilitychange', vis); return () => { clearInterval(t); document.removeEventListener('visibilitychange', vis) }
  }, [])
  if (!nova) return null
  const atualizar = async () => { try { const r = await navigator.serviceWorker?.getRegistration(); await r?.update() } catch {} window.location.reload() }
  return <div className="sticky top-0 z-30 bg-laranja text-marinho text-sm px-4 py-2 flex items-center gap-3"><span>Nova versão do Editor GS disponível.</span><button onClick={atualizar} className="ml-auto rounded-full bg-marinho text-white px-3 py-1 text-xs font-bold">Atualizar</button></div>
}

export default function App() {
  const [maisAberto, setMaisAberto] = useState(false)
  const [nLab, setNLab] = useState(0)  // Laboratório: quantos recursos novos esperam teste (13/11/2026)
  useEffect(() => { const f = () => api.laboratorio().then(d => setNLab(d.para_testar)).catch(() => {}); f(); window.addEventListener('laboratorio', f); return () => window.removeEventListener('laboratorio', f) }, [])
  const [conversas, setConversas] = useState<Conversa[]>([])
  const [estado, setEstado] = useState<any>(null)
  const loc = useLocation()
  const navegar = useNavigate()
  const carregarRef = useRef<() => void>(() => {})
  const depoisDeExcluir = (id: string) => { setConversas(cs => cs.filter(x => x.id !== id)); if (loc.pathname === `/c/${id}`) navegar('/') }
  const [busca, setBusca] = useState('')
  const [resultados, setResultados] = useState<any[]>([])
  const [pastas, setPastas] = useState<{ nome: string; n: number }[]>([])
  const [pastaSel, setPastaSel] = useState<string>(() => { try { return localStorage.getItem('gs-pasta') || '' } catch { return '' } })
  const escolherPasta = (p: string) => { setPastaSel(p); try { localStorage.setItem('gs-pasta', p) } catch {} }
  // conversas de teste do sistema (pasta "Testes do sistema", "Teste tecnico do sistema") ficam escondidas por padrão (11/11/2026)
  const [mostrarTestes, setMostrarTestes] = useState<boolean>(() => { try { return localStorage.getItem('gs-testes') === '1' } catch { return false } })
  const alternarTestes = () => { const v = !mostrarTestes; setMostrarTestes(v); try { localStorage.setItem('gs-testes', v ? '1' : '') } catch {} }
  const carregarPastas = () => api.pastas().then(r => setPastas(r.pastas)).catch(() => {})
  async function novaPasta() { const n = await pedirNovaPasta(); if (n) { await carregarPastas(); escolherPasta(n) } }
  async function renomearPasta() { const n = prompt('Novo nome da pasta:', pastaSel); if (!n?.trim() || n === pastaSel) return; try { const r = await api.renomearPasta(pastaSel, n); await carregarPastas(); escolherPasta(r.nome) } catch (e: any) { alert(e.message) } }
  async function apagarPasta() { if (!confirm(`Apagar a pasta “${pastaSel}”? Os pedidos continuam, só ficam sem pasta.`)) return; try { await api.apagarPasta(pastaSel); await carregarPastas(); escolherPasta('') } catch (e: any) { alert(e.message) } }
  useEffect(() => { const q = busca.trim(); if (q.length < 2) { setResultados([]); return } const t = setTimeout(() => api.busca(q).then(setResultados).catch(() => setResultados([])), 350); return () => clearTimeout(t) }, [busca])
  // carrega uma vez + polling de 8 s (pausa com a aba oculta); antes dependia de loc.pathname e refazia tudo a cada troca de aba (11/11/2026)
  const conversasRef = useRef<Conversa[]>([]); conversasRef.current = conversas
  useEffect(() => {
    carregarRef.current = () => { api.conversas().then(setConversas).catch(() => {}); carregarPastas() }
    const carregar = () => { api.conversas().then(setConversas).catch(() => {}); api.estado().then(setEstado).catch(() => setEstado({ paperclip: 'offline' })); carregarPastas() }
    carregar()
    const t = setInterval(() => { if (document.visibilityState !== 'hidden') carregar() }, 8000)
    const vis = () => { if (document.visibilityState === 'visible') carregar() }
    document.addEventListener('visibilitychange', vis); return () => { clearInterval(t); document.removeEventListener('visibilitychange', vis) }
  }, [])
  // pedido recém-criado (Início → /c/<id>) ainda fora da lista lateral: recarrega só as conversas
  useEffect(() => { const m = loc.pathname.match(/^\/c\/([^/]+)/); if (m && !conversasRef.current.some(c => c.id === m[1])) carregarRef.current() }, [loc.pathname])
  const online = estado?.paperclip === 'ok'
  const nTestes = conversas.filter(c => c.teste).length
  const visiveis = mostrarTestes || pastaSel === PASTA_TESTES ? conversas : conversas.filter(c => !c.teste)
  const contagem: Record<string, number> = {}; conversas.forEach(c => { const k = c.pasta || ''; if (!c.teste || mostrarTestes || k === PASTA_TESTES) contagem[k] = (contagem[k] || 0) + 1 })
  const nomesPastas = Array.from(new Set([...pastas.map(p => p.nome), ...conversas.map(c => c.pasta || '').filter(Boolean)])).filter(n => !(n === PASTA_TESTES || /^testes?/i.test(n)) || mostrarTestes || pastaSel === n)  // pastas de teste só com “mostrar testes” (12/11/2026)
  const lista = pastaSel === '__sem' ? visiveis.filter(c => !c.pasta) : pastaSel ? visiveis.filter(c => c.pasta === pastaSel) : visiveis
  const chip = (ativo: boolean) => `rounded-full px-2.5 py-1 text-[11px] border ${ativo ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/10 text-nevoa hover:bg-white/5'}`
  return (
    <div className="min-h-full md:grid md:grid-cols-[280px_1fr]">
      <aside className="hidden md:flex flex-col gap-4 p-5 border-r border-white/5 bg-[#060e2a] min-h-screen sticky top-0 h-screen overflow-y-auto">
        <div className="flex items-center gap-3 px-1">
          <img src="/icone-192.png" alt="" className="w-10 h-10 rounded-xl" />
          <div><div className="font-[Unbounded] font-bold leading-none">Editor GS</div><div className="text-xs text-nevoa">Grava Simples</div></div>
        </div>
        <NavLink to="/" state={{ pasta: pastaSel === '__sem' ? '' : pastaSel }} className="btn-laranja text-center py-3">+ Novo pedido</NavLink>
        <nav className="flex flex-col gap-0.5">
          {grupos.map(g => <div key={g.titulo} className="flex flex-col gap-0.5">
            <div className="text-[10px] uppercase tracking-wider text-nevoa/70 px-3 mt-2">{g.titulo}</div>
            {g.itens.map(n => <NavLink key={n.to} to={n.to} className={({ isActive }) => `rounded-xl px-3 py-1.5 text-sm hover:bg-white/5 ${isActive ? 'bg-white/10 text-white' : 'text-nevoa'}`}>
              <span className="inline-block w-6 text-laranja">{n.icone}</span>{n.rotulo}{n.to === '/laboratorio' && nLab > 0 && <span className="ml-2 rounded-full bg-laranja px-1.5 text-[10px] font-bold text-[#000921]">{nLab}</span>}</NavLink>)}
          </div>)}
          <details className="mt-2" open={ajustes.some(a => loc.pathname.startsWith(a.to)) || undefined}>
            <summary className="cursor-pointer rounded-xl px-3 py-1.5 text-sm text-nevoa hover:bg-white/5"><span className="inline-block w-6 text-laranja">⚙</span>Ajustes</summary>
            {ajustes.map(n => <NavLink key={n.to} to={n.to} className={({ isActive }) => `block rounded-xl pl-9 pr-3 py-1.5 text-sm hover:bg-white/5 ${isActive ? 'bg-white/10 text-white' : 'text-nevoa'}`}>{n.rotulo}</NavLink>)}
          </details>
        </nav>
        <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="🔍 Buscar nas conversas" className="rounded-xl bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-nevoa" />
        {busca.trim().length >= 2 && <div className="flex flex-col gap-1 -mx-1">{resultados.map(r => <NavLink key={r.id} to={`/c/${r.id}`} onClick={() => setBusca('')} className="rounded-xl px-3 py-2 text-sm hover:bg-white/5"><div className="truncate">{r.titulo}</div><div className="text-[11px] text-nevoa truncate">{r.codigo} · {r.onde}: {r.trecho}</div></NavLink>)}{resultados.length === 0 && <div className="text-xs text-nevoa px-3">Nada encontrado.</div>}</div>}
        <div className="text-xs uppercase tracking-wide text-nevoa mt-2 px-1 flex items-center">Pastas<button onClick={novaPasta} title="Criar pasta (campanha, semana, cliente…)" className="ml-auto text-laranja normal-case tracking-normal hover:underline">+ nova</button></div>
        <div className="flex flex-wrap gap-1 px-1">
          <button onClick={() => escolherPasta('')} className={chip(pastaSel === '')}>Todas · {visiveis.length}</button>
          {nomesPastas.map(n => <button key={n} onClick={() => escolherPasta(pastaSel === n ? '' : n)} className={chip(pastaSel === n)}>📁 {n} · {contagem[n] || 0}</button>)}
          {(contagem[''] || 0) > 0 && nomesPastas.length > 0 && <button onClick={() => escolherPasta(pastaSel === '__sem' ? '' : '__sem')} className={chip(pastaSel === '__sem')}>Sem pasta · {contagem['']}</button>}
        </div>
        {pastaSel && pastaSel !== '__sem' && <div className="text-[11px] text-nevoa px-1 -mt-2"><button onClick={renomearPasta} className="hover:text-white">renomear</button> · <button onClick={apagarPasta} className="hover:text-red-300">apagar pasta</button></div>}
        <div className="text-xs uppercase tracking-wide text-nevoa mt-2 px-1 flex items-center">{pastaSel === '__sem' ? 'Sem pasta' : pastaSel ? `📁 ${pastaSel}` : 'Recentes'}{nTestes > 0 && <button onClick={alternarTestes} title="Conversas de teste do sistema (pasta “Testes do sistema”)" className="ml-auto normal-case tracking-normal text-[11px] hover:text-white">{mostrarTestes ? 'esconder testes' : `mostrar testes · ${nTestes}`}</button>}</div>
        <div className="flex flex-col gap-1 -mx-1">
          {lista.slice(0, pastaSel ? 60 : 12).map(c => <div key={c.id} className="group relative">
            <NavLink to={`/c/${c.id}`} className={({ isActive }) => `block rounded-xl pl-3 pr-8 py-2 text-sm hover:bg-white/5 ${isActive ? 'bg-white/10' : ''}`}>
              <div className="truncate">{c.titulo}</div>
              <div className="text-[11px] text-nevoa truncate">{c.codigo} · {situacao(c)}{c.pasta && !pastaSel ? ` · 📁 ${c.pasta}` : ''}</div>
            </NavLink>
            <MenuConversa c={c} onMudou={() => carregarRef.current()} onExcluida={() => depoisDeExcluir(c.id)} className="absolute right-1.5 top-2" />
          </div>)}
          {lista.length === 0 && <div className="text-xs text-nevoa px-3">{pastaSel ? 'Nenhum pedido nesta pasta.' : 'Nenhum pedido ainda.'}</div>}
          <NavLink to="/lixeira" className={({ isActive }) => `rounded-xl px-3 py-1.5 text-[11px] hover:bg-white/5 ${isActive ? 'text-white' : 'text-nevoa'}`}>🗑 Lixeira</NavLink>
        </div>
        <div className="mt-auto text-[11px] text-nevoa px-1">
          <span className={`inline-block w-2 h-2 rounded-full mr-2 ${online ? 'bg-green-400' : 'bg-red-400'}`} />
          {online ? `Editor ${estado?.editor?.status ?? ''} · ${estado?.editor?.modelo ?? ''}` : 'Editor fora do ar'}
        </div>
      </aside>
      <main className="pb-20 md:pb-0">
        <NovaVersao />
        <header className="md:hidden flex items-center gap-3 p-4 border-b border-white/5">
          <img src="/icone-192.png" alt="" className="w-8 h-8 rounded-lg" /><div className="font-[Unbounded] font-bold">Editor GS</div>
          <span className={`ml-auto w-2 h-2 rounded-full ${online ? 'bg-green-400' : 'bg-red-400'}`} />
        </header>
        <Suspense fallback={<div className="p-6 text-sm text-nevoa">Carregando…</div>}>
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/novo" element={<Inicio />} />
          <Route path="/c/:id" element={<ConversaPagina />} />
          <Route path="/ideias" element={<Ideias />} />
          <Route path="/referencias" element={<Referencias />} />
          <Route path="/clipador" element={<Clipador />} />
          <Route path="/acervo" element={<Acervo />} />
          <Route path="/ganchos" element={<Ganchos />} />
          <Route path="/fluxos" element={<Fluxos />} />
          <Route path="/estilos" element={<Estilos />} />
          <Route path="/voz" element={<VozPagina />} />
          <Route path="/biblioteca" element={<Biblioteca />} />
          <Route path="/redes" element={<Redes />} />
          <Route path="/ajuda" element={<Ajuda />} />
          <Route path="/laboratorio" element={<Laboratorio />} />
          <Route path="/marca" element={<MarcaPagina />} />
          <Route path="/textos" element={<Textos />} />
          <Route path="/teleprompter" element={<Teleprompter />} />
          <Route path="/operacao" element={<Operacao />} />
          <Route path="/pecas" element={<PecasLista />} />
          <Route path="/metricas" element={<Metricas />} />
          <Route path="/campanhas" element={<Campanhas />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/demos" element={<SkillsDemos />} />
          <Route path="/aprovacoes" element={<Aprovacoes />} />
          <Route path="/lixeira" element={<Lixeira />} />
          <Route path="/pecas/:slug" element={<PecaFichaPagina />} />
        </Routes>
        </Suspense>
      </main>
      {maisAberto && <div className="md:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setMaisAberto(false)}>
        <div className="absolute bottom-16 inset-x-0 bg-[#060e2a] border-t border-white/10 rounded-t-2xl p-4 grid grid-cols-3 gap-2 text-xs" onClick={e => e.stopPropagation()}>
          {[...nav.filter(n => !['/', '/textos', '/biblioteca'].includes(n.to)), { to: '/ajuda', rotulo: 'Ajuda · celular', icone: '📱' }].map(n => <NavLink key={n.to} to={n.to} onClick={() => setMaisAberto(false)} className={({ isActive }) => `rounded-xl px-2 py-3 text-center ${isActive ? 'bg-white/10 text-white' : 'text-nevoa bg-white/5'}`}><div className="text-lg">{n.icone}</div>{n.rotulo}</NavLink>)}
          <div className="col-span-3 text-[11px] text-nevoa px-1 pt-1">Pastas: {nomesPastas.length ? nomesPastas.map(n => <button key={n} onClick={() => { escolherPasta(pastaSel === n ? '' : n); setMaisAberto(false) }} className={`mr-2 ${pastaSel === n ? 'text-laranja' : ''}`}>📁 {n}</button>) : 'nenhuma'}</div>
          <div className="col-span-3 max-h-40 overflow-y-auto grid gap-1">{lista.slice(0, 8).map(c => <div key={c.id} className="relative min-w-0"><NavLink to={`/c/${c.id}`} onClick={() => setMaisAberto(false)} className="block rounded-lg pl-2 pr-9 py-1.5 bg-black/30"><div className="truncate">{c.titulo}</div><div className="text-[10px] text-nevoa">{c.codigo} · {situacao(c)}</div></NavLink><MenuConversa c={c} onMudou={() => carregarRef.current()} onExcluida={() => depoisDeExcluir(c.id)} className="absolute right-1 top-1.5 text-base" /></div>)}<NavLink to="/lixeira" onClick={() => setMaisAberto(false)} className="rounded-lg px-2 py-1.5 text-nevoa">🗑 Lixeira</NavLink></div>
        </div>
      </div>}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-[#060e2a] border-t border-white/5 grid grid-cols-5 text-[10px]">
        {[{ to: '/', rotulo: 'Novo', icone: '✦' }, { to: conversas[0] ? `/c/${conversas[0].id}` : '/', rotulo: 'Recentes', icone: '💬' }, { to: '/textos', rotulo: 'Textos', icone: '✎' }, { to: '/biblioteca', rotulo: 'Arquivos', icone: '▤' }].map(n => <NavLink key={n.rotulo} to={n.to} end={n.to === '/'} onClick={() => setMaisAberto(false)} className={({ isActive }) => `py-3 text-center ${isActive && n.rotulo !== 'Recentes' ? 'text-laranja' : 'text-nevoa'}`}><div className="text-base">{n.icone}</div>{n.rotulo}</NavLink>)}
        <button onClick={() => setMaisAberto(v => !v)} className={`py-3 text-center ${maisAberto ? 'text-laranja' : 'text-nevoa'}`}><div className="text-base">☰</div>Mais</button>
      </nav>
    </div>
  )
}
