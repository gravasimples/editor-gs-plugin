import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type CalendarioItem, type Comentario, type Resultados } from '../api'
import { Conexoes } from '../Conexoes'

const PLAT: Record<string, string> = { instagram: 'Instagram', youtube: 'YouTube', tiktok: 'TikTok', facebook: 'Facebook' }
const TIPO: Record<string, string> = { agendado: 'agendado', rascunho: 'rascunho', postado: 'postado', planejado: 'planejado', recorrente: 'recorrente', published: 'postado', failed: 'falhou' }
const COR: Record<string, string> = { agendado: 'text-laranja', rascunho: 'text-nevoa', postado: 'text-green-300', planejado: 'text-white/80', recorrente: 'text-nevoa', failed: 'text-red-300' }
const DIAS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb']

function Dia({ d }: { d: string }) { const x = new Date(d + 'T12:00:00'); return <>{DIAS[x.getDay()]} {x.getDate().toString().padStart(2, '0')}/{(x.getMonth() + 1).toString().padStart(2, '0')}</> }
const n = (v: number | null | undefined) => (v ?? 0).toLocaleString('pt-BR')

export default function Redes() {
  const nav = useNavigate()
  const [aba, setAba] = useState<'cal' | 'com' | 'res'>('cal')
  const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState('')
  // calendário
  const [cal, setCal] = useState<{ hoje: string; itens: CalendarioItem[]; aviso?: string | null } | null>(null)
  const [fontes, setFontes] = useState<Record<string, boolean>>({ publora: true, youtube: true, instagram: true, notion: true, recorrente: false })
  // comentários
  const [com, setCom] = useState<{ itens: Comentario[]; n: number; sem_resposta: number } | null>(null)
  const [todos, setTodos] = useState(false); const [sel, setSel] = useState<string[]>([])
  // resultados
  const [dias, setDias] = useState<7 | 30 | 90>(30); const [res, setRes] = useState<Resultados | null>(null)
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7)); const [rel, setRel] = useState<{ mes: string; conteudo: string } | null>(null)
  useEffect(() => { setErro(''); if (aba === 'cal') api.calendario().then(setCal).catch(e => setErro(e.message)) }, [aba])
  useEffect(() => { setErro(''); if (aba === 'com') api.comentarios(30, todos).then(setCom).catch(e => setErro(e.message)) }, [aba, todos])
  useEffect(() => { setErro(''); if (aba === 'res') api.resultados(dias).then(setRes).catch(e => setErro(e.message)) }, [aba, dias])
  async function rascunhar() {
    setOcupado('Criando pedido…')
    try { const c = await api.rascunharRespostas(sel); nav(`/c/${c.id}`) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function analisar() {
    setOcupado('Criando pedido…')
    try { const c = await api.analisarResultados(dias); nav(`/c/${c.id}`) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function relatorio() { setOcupado('Gerando…'); try { setRel(await api.relatorioMes(mes)) } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  const porDia: Record<string, CalendarioItem[]> = {}
  cal?.itens.filter(i => fontes[i.origem] && (i.tipo !== 'recorrente' || fontes.recorrente)).forEach(i => { (porDia[i.dia] ||= []).push(i) })
  const diasCal = Object.keys(porDia).sort()
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Redes</h2>
    <p className="text-nevoa mt-2">Calendário, comentários e resultados das contas da Grava Simples. Tudo é leitura (GSI, Notion Mídias e Publora); responder e publicar continua sendo um clique seu.</p>
    <Conexoes />
    <div className="flex gap-2 mt-5 flex-wrap">{([['cal', '📅 Calendário'], ['com', '💬 Comentários'], ['res', '📈 Resultados']] as const).map(([a, r]) => <button key={a} onClick={() => setAba(a)} className={`rounded-full px-4 py-1.5 text-sm border ${aba === a ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{r}</button>)}</div>
    {erro && <div className="text-red-300 mt-4 text-sm">{erro}</div>}
    {ocupado && <div className="text-nevoa mt-4 text-sm animate-pulse">{ocupado}</div>}

    {aba === 'cal' && <div className="mt-5">
      <div className="flex flex-wrap gap-2 text-xs">{(['publora', 'youtube', 'instagram', 'notion', 'recorrente'] as const).map(f => <label key={f} className={`selo cursor-pointer ${fontes[f] ? 'ring-1 ring-laranja' : 'opacity-50'}`}><input type="checkbox" className="hidden" checked={fontes[f]} onChange={e => setFontes({ ...fontes, [f]: e.target.checked })} />{f === 'publora' ? 'Agendados (Publora)' : f === 'notion' ? 'Planejados (Notion)' : f === 'recorrente' ? 'Recorrentes (stories fixos)' : `Postados (${PLAT[f]})`}</label>)}</div>
      {cal?.aviso && <div className="text-xs text-nevoa mt-2">{cal.aviso}</div>}
      {!cal && <div className="text-nevoa mt-4 text-sm">Carregando…</div>}
      <div className="grid gap-3 mt-4">{diasCal.map(d => <div key={d} className={`cartao p-3 ${d === cal?.hoje ? 'ring-1 ring-laranja' : ''}`}>
        <div className="text-xs uppercase tracking-wide text-nevoa mb-2"><Dia d={d} />{d === cal?.hoje && <span className="text-laranja"> · hoje</span>}</div>
        {porDia[d].map((i, k) => <div key={k} className="flex items-start gap-2 text-sm py-1 border-t border-white/5 first:border-0">
          <span className="text-nevoa w-12 shrink-0">{i.hora || ''}</span>
          <span className={`w-20 shrink-0 ${COR[i.tipo] || 'text-nevoa'}`}>{TIPO[i.tipo] || i.tipo}</span>
          <span className="flex-1 min-w-0 truncate">{i.url || i.notion_url ? <a href={i.url || i.notion_url || '#'} target="_blank" rel="noreferrer" className="hover:underline">{i.titulo}</a> : i.titulo}{i.status && i.origem === 'notion' && <span className="text-nevoa"> · {i.status}</span>}</span>
          <span className="text-xs text-nevoa shrink-0">{(i.plataformas || []).map(p => PLAT[p] || p).join(', ')}{i.formato && Array.isArray(i.formato) ? ` · ${i.formato.join('/')}` : i.formato ? ` · ${i.formato}` : ''}</span>
        </div>)}
      </div>)}{cal && diasCal.length === 0 && <div className="text-nevoa text-sm">Nada nesse intervalo (14 dias para trás, 28 para a frente).</div>}</div>
    </div>}

    {aba === 'com' && <div className="mt-5">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-nevoa">{com ? `${com.sem_resposta} sem resposta de ${com.n} nos últimos 30 dias` : '…'}</span>
        <label className="selo cursor-pointer ml-2"><input type="checkbox" className="mr-1" checked={todos} onChange={e => setTodos(e.target.checked)} />mostrar respondidos</label>
        <button onClick={rascunhar} disabled={!!ocupado || !com || com.sem_resposta === 0} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{sel.length ? `Rascunhar ${sel.length} resposta(s)` : 'Rascunhar respostas (até 20)'}</button>
      </div>
      <div className="text-xs text-nevoa mt-2">O Editor só escreve os rascunhos (na voz do Thiago) na mensagem da conversa (seção Respostas; também na página Textos); responder na rede é à mão. Perguntas de preço ou vaga ficam marcadas para humano. Autor aparece pseudonimizado.</div>
      <div className="grid gap-2 mt-4">{com?.itens.map(c => <label key={c.id} className={`cartao p-3 flex gap-3 cursor-pointer ${sel.includes(c.id) ? 'ring-1 ring-laranja' : ''}`}>
        {!c.respondido && <input type="checkbox" className="mt-1" checked={sel.includes(c.id)} onChange={e => setSel(e.target.checked ? [...sel, c.id] : sel.filter(x => x !== c.id))} />}
        <div className="flex-1 min-w-0"><div className="text-sm">{c.texto}</div>
          <div className="text-xs text-nevoa mt-1 flex flex-wrap gap-2"><span>{PLAT[c.plataforma] || c.plataforma}</span><span>{new Date(c.quando).toLocaleDateString('pt-BR')}</span><span>aluno {c.autor || '?'}</span>{c.likes > 0 && <span>{c.likes} curtidas</span>}<a href={c.url} target="_blank" rel="noreferrer" className="truncate hover:underline">em: {c.conteudo}</a>{c.respondido && <span className="text-green-300">respondido</span>}</div></div>
      </label>)}{com && com.itens.length === 0 && <div className="text-nevoa text-sm">Nenhum comentário pendente nos últimos 30 dias (YouTube pela Data API; Instagram só depois da Meta).</div>}</div>
    </div>}

    {aba === 'res' && <div className="mt-5">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {([7, 30, 90] as const).map(d => <button key={d} onClick={() => setDias(d)} className={`rounded-full px-3 py-1 border ${dias === d ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa'}`}>{d} dias</button>)}
        <button onClick={analisar} disabled={!!ocupado || !res?.itens.length} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">Pedir análise ao Editor</button>
      </div>
      {res && <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">{([['Conteúdos', res.total.conteudos, res.anterior.conteudos], ['Views', res.total.views, res.anterior.views], ['Likes', res.total.likes, res.anterior.likes], ['Comentários', res.total.comentarios, res.anterior.comentarios]] as [string, number, number][]).map(([r, v, a]) => <div key={r} className="cartao p-3"><div className="text-xs text-nevoa">{r}</div><div className="text-2xl font-bold">{n(v)}</div><div className="text-xs text-nevoa">antes: {n(a)}{a ? <span className={v >= a ? 'text-green-300' : 'text-red-300'}> ({v >= a ? '+' : ''}{Math.round((v - a) / a * 100)}%)</span> : null}</div></div>)}</div>
        <div className="text-xs text-nevoa mt-2">Mediana {n(res.total.views_mediana)} views · engajamento médio {res.total.engajamento_medio ?? '—'} · última medição {res.ultima_medicao ? new Date(res.ultima_medicao).toLocaleString('pt-BR') : '—'}. {res.nota}</div>
        {res.formatos.length > 0 && <div className="cartao p-3 mt-4 text-sm"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">Por formato</div>{res.formatos.map(f => <div key={f.formato} className="flex gap-3 py-0.5"><span className="w-40 shrink-0">{f.formato}</span><span className="text-nevoa">{f.conteudos} conteúdos · {n(f.views)} views · mediana {n(f.views_mediana)}</span></div>)}</div>}
        <div className="cartao p-3 mt-4 text-sm"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">Conteúdos do período (por views)</div>
          {res.itens.map(i => <div key={i.id} className="flex items-center gap-3 py-1 border-t border-white/5 first:border-0"><span className="text-nevoa w-20 shrink-0 text-xs">{i.publicado.slice(5).split('-').reverse().join('/')}</span><a href={i.url} target="_blank" rel="noreferrer" className="flex-1 min-w-0 truncate hover:underline">{i.titulo}</a><span className="text-xs text-nevoa shrink-0">{PLAT[i.plataforma]}/{i.formato || '?'}</span><span className="w-20 text-right shrink-0">{n(i.views)}</span><span className={`w-14 text-right text-xs shrink-0 ${(i.vs_mediana_formato ?? 1) >= 1 ? 'text-green-300' : 'text-nevoa'}`}>{i.vs_mediana_formato != null ? `${i.vs_mediana_formato}×` : ''}</span></div>)}
          {res.itens.length === 0 && <div className="text-nevoa">Nenhum conteúdo medido nesse período.</div>}</div>
        <div className="cartao p-3 mt-4 text-sm">
          <div className="flex flex-wrap items-center gap-2"><div className="text-xs uppercase tracking-wide text-nevoa">Relatório do mês</div><input type="month" value={mes} onChange={e => setMes(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1" /><button onClick={relatorio} disabled={!!ocupado} className="rounded-full border border-laranja/60 text-laranja px-4 py-1 hover:bg-laranja/10">Gerar</button>{rel && <a href={`/api/gs/redes/relatorio-mes/arquivo?mes=${rel.mes}`} className="selo">Baixar .md</a>}</div>
          {rel && <pre className="whitespace-pre-wrap text-xs text-white/80 mt-3 max-h-96 overflow-auto">{rel.conteudo}</pre>}
          <div className="text-xs text-nevoa mt-2">Números do GSI, sem modelo de linguagem. Para hipóteses e próximos conteúdos, use "Pedir análise ao Editor".</div>
        </div>
      </>}
    </div>}
  </div>
}
