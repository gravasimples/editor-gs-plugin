import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type SkillItem, type SkillsEstado } from '../api'

// Banco de skills de edição (10/11/2026): catálogo do que existe fora (skills e plugins do Claude Code, repositórios, presets, criadores),
// com decisão humana (avaliar → aprovar → instalar ou reproduzir), pesquisa recorrente pelo Editor e "Ensinar o Editor" (regras e conhecimento).
const COR: Record<string, string> = { achado: 'bg-white/10 text-nevoa', avaliar: 'bg-azul/30 text-white', aprovado: 'bg-green-500/20 text-green-300', instalado: 'bg-laranja/20 text-laranja', reproduzido: 'bg-laranja/20 text-laranja', descartado: 'bg-white/5 text-nevoa line-through' }
const ROT: Record<string, string> = { achado: 'achado', avaliar: 'em avaliação', aprovado: 'aprovado', instalado: 'instalado', reproduzido: 'reproduzido', descartado: 'descartado' }
const VAZIO = { url: '', nome: '', tipo: 'skill-claude', resumo: '', autor: '', licenca: '', preco: '', o_que_aproveitar: '' }

export default function Skills() {
  const nav = useNavigate()
  const [itens, setItens] = useState<SkillItem[]>([]); const [est, setEst] = useState<SkillsEstado | null>(null); const [ligado, setLigado] = useState(false)
  const [erro, setErro] = useState(''); const [aviso, setAviso] = useState(''); const [ocupado, setOcupado] = useState('')
  const [estado, setEstado] = useState(''); const [tipo, setTipo] = useState(''); const [q, setQ] = useState(''); const [aberto, setAberto] = useState('')
  const [form, setForm] = useState<typeof VAZIO | null>(null); const [foco, setFoco] = useState('')
  const [ensinar, setEnsinar] = useState<{ tipo: 'regra' | 'conhecimento'; titulo: string; texto: string; fonte: string } | null>(null); const arq = useRef<HTMLInputElement>(null)
  const carregar = () => api.skills({ estado, tipo, q }).then(r => { setItens(r.itens); setEst(r.estado); setLigado(r.garimpo_ligado) }).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [estado, tipo])
  async function agir(rotulo: string, fn: () => Promise<any>, ok?: (r: any) => string) {
    setOcupado(rotulo); setErro(''); setAviso('')
    try { const r = await fn(); if (ok) setAviso(ok(r)); await carregar() } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  const decidir = (it: SkillItem, e: string) => { const nota = e === 'descartado' ? (prompt('Por que descartar? (fica na ficha)') ?? '') : ''; if (e === 'descartado' && nota === null) return; agir(it.id + e, () => api.skillDecidir(it.id, e, nota)) }
  const T = est?.tipos || {}
  return <div className="max-w-6xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Banco de skills de edição</h2>
    <p className="text-nevoa mt-2 text-sm">O que existe fora e pode ampliar o que o Editor sabe fazer: skills e plugins do Claude Code, repositórios, presets e estilos de criadores que vendem ou publicam, ferramentas e cursos. O Editor pesquisa (uma vez por semana com a chave ligada, ou agora), você decide: <b>avaliar</b> abre uma análise, <b>aprovar</b> libera, <b>instalar</b> põe a skill na pasta do agente, <b>reproduzir</b> abre um pedido de engenharia reversa que vira estilo ou fluxo nosso (nunca cópia de material de terceiro). Nada vira padrão sem a sua aprovação.</p>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {aviso && <div className="text-green-300 text-sm mt-3">{aviso}</div>}

    <div className="cartao p-4 mt-5 grid gap-3 md:grid-cols-[1fr_auto] items-start">
      <div className="text-sm">
        <div className="font-bold">Pesquisa de mercado pelo Editor <span className={`ml-2 selo ${ligado ? '' : 'opacity-60'}`}>{ligado ? 'semanal ligada' : 'semanal desligada'}</span></div>
        <div className="text-nevoa text-xs mt-1">{est?.pesquisa_motivo}{est?.rodadas?.length ? ` · ${est.rodadas.length} rodada(s) recentes` : ''}. Chave semanal em <Link to="/metricas" className="text-laranja hover:underline">Métricas › Automações</Link> (“Garimpo semanal de skills e ferramentas”). Cada rodada é um pedido do modelo padrão com busca na web; zero achados é resultado válido.</div>
        {est && est.rodadas.length > 0 && <div className="mt-2 flex flex-wrap gap-1 text-[11px]">{est.rodadas.slice(-6).reverse().map(r => <span key={r.id} className="rounded-full bg-black/30 px-2 py-0.5">{r.quando.slice(0, 16).replace('T', ' ')} · {r.estado}{r.codigo ? ` · ${r.codigo}` : ''}{r.novos != null ? ` · ${r.novos} novos` : ''}{r.foco ? ` · foco: ${r.foco}` : ''}</span>)}</div>}
      </div>
      <form onSubmit={e => { e.preventDefault(); agir('pesq', () => api.skillsPesquisar(foco), r => `Pedido ${r.conversa?.codigo || ''} de pesquisa aberto no Editor.`); setFoco('') }} className="flex gap-2 items-center">
        <input value={foco} onChange={e => setFoco(e.target.value)} placeholder="foco desta rodada (opcional)" className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm w-56" />
        <button disabled={!!ocupado} className="btn-laranja px-4 py-1.5 text-sm disabled:opacity-50">{ocupado === 'pesq' ? 'abrindo…' : '🔎 Pesquisar agora'}</button>
      </form>
    </div>

    <div className="flex flex-wrap gap-2 mt-5 items-center text-sm">
      {est && <div className="flex flex-wrap gap-1">{['', ...est.estados].map(e => <button key={e || 'tudo'} onClick={() => setEstado(e)} className={`rounded-full px-3 py-1 text-xs border ${estado === e ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{e ? ROT[e] : 'tudo'} · {e ? est.por_estado[e] || 0 : est.n}</button>)}</div>}
      <select value={tipo} onChange={e => setTipo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5"><option value="">todos os tipos</option>{Object.entries(T).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      <form onSubmit={e => { e.preventDefault(); carregar() }} className="flex gap-2 flex-1 min-w-[12rem]"><input value={q} onChange={e => setQ(e.target.value)} placeholder="filtrar por palavra" className="flex-1 rounded-full border border-white/15 bg-card px-3 py-1.5" /><button className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">filtrar</button></form>
      <button onClick={() => setForm(form ? null : { ...VAZIO })} className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 hover:bg-laranja/10">{form ? 'fechar' : '+ Registrar à mão'}</button>
    </div>
    {form && <form onSubmit={e => { e.preventDefault(); agir('reg', () => api.skillsRegistrar(form), r => r.novos.length ? `Registrado: ${r.item.nome}.` : `Já estava no banco: ${r.item.nome}.`); setForm(null) }} className="cartao p-4 mt-3 grid gap-2 md:grid-cols-2 text-sm">
      <input value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} placeholder="link (GitHub, página de venda, perfil…)" className="rounded-xl bg-black/30 px-3 py-2 md:col-span-2" />
      <input value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} placeholder="nome" className="rounded-xl bg-black/30 px-3 py-2" />
      <select value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })} className="rounded-xl bg-black/30 px-3 py-2">{Object.entries(T).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      <input value={form.autor} onChange={e => setForm({ ...form, autor: e.target.value })} placeholder="autor" className="rounded-xl bg-black/30 px-3 py-2" />
      <div className="grid grid-cols-2 gap-2"><input value={form.licenca} onChange={e => setForm({ ...form, licenca: e.target.value })} placeholder="licença" className="rounded-xl bg-black/30 px-3 py-2" /><input value={form.preco} onChange={e => setForm({ ...form, preco: e.target.value })} placeholder="preço" className="rounded-xl bg-black/30 px-3 py-2" /></div>
      <textarea value={form.resumo} onChange={e => setForm({ ...form, resumo: e.target.value })} placeholder="o que é, em 2 frases" rows={2} className="rounded-xl bg-black/30 px-3 py-2 md:col-span-2" />
      <input value={form.o_que_aproveitar} onChange={e => setForm({ ...form, o_que_aproveitar: e.target.value })} placeholder="o que aproveitar (separe por ;)" className="rounded-xl bg-black/30 px-3 py-2 md:col-span-2" />
      <div className="md:col-span-2 flex gap-2"><button disabled={!!ocupado} className="btn-laranja px-4 py-1.5">Registrar</button><button type="button" onClick={() => setForm(null)} className="rounded-full border border-white/15 px-3 py-1.5">cancelar</button></div>
    </form>}

    <div className="mt-4 grid gap-2">
      {itens.length === 0 && <div className="text-nevoa text-sm">Nada aqui ainda. Clique em “Pesquisar agora” ou registre um link à mão.</div>}
      {itens.map(it => <div key={it.id} className="cartao p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setAberto(aberto === it.id ? '' : it.id)} className="font-bold text-left hover:text-laranja">{it.nome}</button>
          <span className={`rounded-full px-2 py-0.5 text-[11px] ${COR[it.estado] || ''}`}>{ROT[it.estado] || it.estado}</span>
          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-nevoa">{T[it.tipo] || it.tipo}</span>
          {it.licenca && <span className="text-[11px] text-nevoa">{it.licenca}</span>}{it.preco && <span className="text-[11px] text-nevoa">· {it.preco}</span>}
          {it.url && <a href={it.url} target="_blank" className="text-xs text-nevoa hover:underline">abrir ↗</a>}
          <span className="ml-auto text-[11px] text-nevoa">{it.fonte} · {it.achado_em?.slice(0, 10)}</span>
        </div>
        {it.resumo && <div className="text-nevoa mt-1">{it.resumo}</div>}
        {it.o_que_aproveitar?.length > 0 && <div className="mt-1 flex flex-wrap gap-1">{it.o_que_aproveitar.map((x, i) => <span key={i} className="rounded-full bg-laranja/10 text-laranja px-2 py-0.5 text-[11px]">{x}</span>)}</div>}
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {it.estado !== 'descartado' && it.estado !== 'instalado' && <button disabled={!!ocupado} onClick={() => agir(it.id + 'av', () => api.skillReproduzir(it.id, 'avaliar'), r => `Pedido ${r.codigo} de avaliação aberto.`)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">🔍 Avaliar (pedido)</button>}
          {['achado', 'avaliar'].includes(it.estado) && <button disabled={!!ocupado} onClick={() => decidir(it, 'aprovado')} className="rounded-full border border-green-400/60 text-green-300 px-3 py-1 hover:bg-green-400/10">✓ Aprovar</button>}
          {['aprovado', 'reproduzido'].includes(it.estado) && ['skill-claude', 'plugin'].includes(it.tipo) && <button disabled={!!ocupado} onClick={() => agir(it.id + 'in', () => api.skillInstalar(it.id), r => `Skill ${r.skill} instalada em ${r.pasta}.`)} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">{ocupado === it.id + 'in' ? 'instalando…' : '⬇ Instalar skill'}</button>}
          {it.estado === 'instalado' && <button disabled={!!ocupado} onClick={() => agir(it.id + 'des', () => api.skillDesinstalar(it.id))} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">desinstalar</button>}
          {['aprovado', 'instalado', 'reproduzido'].includes(it.estado) && <button disabled={!!ocupado} onClick={() => agir(it.id + 'rep', () => api.skillReproduzir(it.id, 'reproduzir'), r => `Pedido ${r.codigo} de reprodução aberto no Editor.`)} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 hover:bg-laranja/10">⚙ Reproduzir no Editor</button>}
          {it.estado !== 'descartado' && <button disabled={!!ocupado} onClick={() => decidir(it, 'descartado')} className="rounded-full border border-white/15 px-3 py-1 text-nevoa hover:bg-white/5">descartar</button>}
          {it.estado === 'descartado' && <button disabled={!!ocupado} onClick={() => decidir(it, 'achado')} className="rounded-full border border-white/15 px-3 py-1 text-nevoa hover:bg-white/5">voltar para achado</button>}
          <button onClick={() => { const t = prompt('Nota para a ficha:'); if (t) agir(it.id + 'nota', () => api.skillAnotar(it.id, t)) }} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">+ nota</button>
        </div>
        {aberto === it.id && <div className="mt-3 grid gap-1 text-xs text-nevoa border-t border-white/10 pt-2">
          {it.autor && <div><b className="text-white">Autor:</b> {it.autor}</div>}
          {it.evidencia && <div><b className="text-white">Evidência:</b> {it.evidencia}</div>}
          {it.como_reproduzir && <div><b className="text-white">Como reproduzir (hipótese):</b> {it.como_reproduzir}</div>}
          {it.instalacao && <div><b className="text-white">Instalada:</b> {it.instalacao.skill} em {it.instalacao.pasta} ({it.instalacao.quando.slice(0, 16).replace('T', ' ')})</div>}
          {it.decidido_por && <div><b className="text-white">Decisão:</b> {it.decidido_por} em {it.decidido_em?.slice(0, 16).replace('T', ' ')}</div>}
          {it.notas?.length > 0 && <div><b className="text-white">Notas:</b> {it.notas.map((n, i) => <div key={i} className="ml-2">· {n.quando.slice(0, 16).replace('T', ' ')} {n.por}: {n.texto}</div>)}</div>}
          <div><b className="text-white">Editar:</b> <button onClick={() => { const u = prompt('Link (para skill: pasta exata no GitHub, ex. https://github.com/dono/repo/tree/main/skills/x):', it.url); if (u != null) agir(it.id + 'ed', () => api.skillEditar(it.id, { url: u })) }} className="text-laranja hover:underline">link</button> · <button onClick={() => { const r = prompt('Como reproduzir no Editor (hipótese):', it.como_reproduzir); if (r != null) agir(it.id + 'ed', () => api.skillEditar(it.id, { como_reproduzir: r })) }} className="text-laranja hover:underline">como reproduzir</button></div>
        </div>}
      </div>)}
    </div>

    <div className="grid gap-4 md:grid-cols-2 mt-8">
      <div className="cartao p-4 text-sm">
        <div className="font-bold">🎓 Ensinar o Editor</div>
        <div className="text-nevoa text-xs mt-1">Regra curta vira memória (vale em toda edição). Conhecimento (texto longo, transcrição de aula, método, .txt/.md/.srt) vira arquivo que o Editor lê quando o pedido tocar no assunto. Vídeo ou link de referência: <Link to="/referencias" className="text-laranja hover:underline">Referências</Link>.</div>
        {!ensinar && <div className="mt-3 flex gap-2"><button onClick={() => setEnsinar({ tipo: 'regra', titulo: '', texto: '', fonte: '' })} className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 text-xs hover:bg-laranja/10">+ Regra</button><button onClick={() => setEnsinar({ tipo: 'conhecimento', titulo: '', texto: '', fonte: '' })} className="rounded-full border border-laranja/60 text-laranja px-3 py-1.5 text-xs hover:bg-laranja/10">+ Conhecimento</button><button onClick={() => nav('/referencias')} className="rounded-full border border-white/15 px-3 py-1.5 text-xs hover:bg-white/5">+ Vídeo/link</button></div>}
        {ensinar && <form onSubmit={e => { e.preventDefault(); const fd = new FormData(); fd.append('tipo', ensinar.tipo); fd.append('titulo', ensinar.titulo); fd.append('texto', ensinar.texto); fd.append('fonte', ensinar.fonte); if (arq.current?.files?.[0]) fd.append('arquivo', arq.current.files[0]); agir('ens', () => api.skillsEnsinar(fd), r => r.tipo === 'regra' ? `Regra guardada: “${r.memoria?.texto}”.` : `Conhecimento guardado em ${r.arquivo}.`); setEnsinar(null) }} className="mt-3 grid gap-2">
          {ensinar.tipo === 'conhecimento' && <input value={ensinar.titulo} onChange={e => setEnsinar({ ...ensinar, titulo: e.target.value })} placeholder="título" className="rounded-xl bg-black/30 px-3 py-2" />}
          <textarea value={ensinar.texto} onChange={e => setEnsinar({ ...ensinar, texto: e.target.value })} rows={ensinar.tipo === 'regra' ? 2 : 6} placeholder={ensinar.tipo === 'regra' ? 'ex.: nunca usar clarão em vídeo de aula' : 'cole o texto, método ou transcrição'} className="rounded-xl bg-black/30 px-3 py-2" />
          {ensinar.tipo === 'conhecimento' && <div className="flex flex-wrap gap-2 items-center text-xs"><input value={ensinar.fonte} onChange={e => setEnsinar({ ...ensinar, fonte: e.target.value })} placeholder="fonte (opcional)" className="rounded-xl bg-black/30 px-3 py-1.5 flex-1" /><input ref={arq} type="file" accept=".txt,.md,.srt,.vtt" className="text-nevoa" /></div>}
          <div className="flex gap-2"><button disabled={!!ocupado} className="btn-laranja px-4 py-1.5 text-xs">Guardar</button><button type="button" onClick={() => setEnsinar(null)} className="rounded-full border border-white/15 px-3 py-1.5 text-xs">cancelar</button></div>
        </form>}
        {est && est.conhecimento.length > 0 && <div className="mt-3 grid gap-1 text-xs">{est.conhecimento.map(c => <div key={c.arquivo} className="flex items-center gap-2"><span className="flex-1 truncate">{c.titulo}</span><span className="text-nevoa">{c.quando.slice(0, 10)} · {Math.round(c.tamanho / 1000)} k</span><button onClick={() => { if (confirm(`Apagar “${c.titulo}”?`)) agir('apg', () => api.skillsConhecimentoApagar(c.arquivo)) }} className="text-nevoa hover:text-red-300">apagar</button></div>)}</div>}
      </div>
      <div className="cartao p-4 text-sm">
        <div className="font-bold">🧩 Skills instaladas no agente</div>
        <div className="text-nevoa text-xs mt-1">Pasta <code>.claude/skills/</code> do workspace; o Claude Code carrega sozinho nas próximas rodadas. O Editor usa quando o pedido ou o fluxo citar a skill.</div>
        {est && est.instaladas.length === 0 && <div className="text-nevoa text-xs mt-3">Nenhuma ainda.</div>}
        {est && est.instaladas.map(s => <div key={s.pasta} className="mt-2 text-xs"><b>{s.pasta}</b> <span className="text-nevoa">· {s.arquivos} arquivo(s)</span><div className="text-nevoa">{s.descricao}</div></div>)}
      </div>
    </div>
  </div>
}
