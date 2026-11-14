import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Automacao, type Posmortem, type Resultados, type Rodadas } from '../api'
import { ChipsEtiquetas } from '../Etiquetas'
import { AutomacoesDados } from '../AutomacoesDados'
import { PastaVigiada } from '../PastaVigiada'
import { PerfilRende } from '../PerfilRende'

const n = (x: number | null | undefined) => (x == null ? '—' : x.toLocaleString('pt-BR'))
type Dados = { painel: Resultados; pecas: any; posmortem: { pendentes: any[]; feitos: Posmortem[]; dias: number }; automacoes: Automacao[] }

export default function Metricas() {
  const [aba, setAba] = useState<'painel' | 'rende' | 'pos' | 'auto' | 'rel'>('painel')
  const [dias, setDias] = useState<7 | 30 | 90>(30); const [d, setD] = useState<Dados | null>(null); const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState('')
  const [rel, setRel] = useState<{ conteudo: string; arquivo: string; fim: string } | null>(null); const [fim, setFim] = useState(new Date().toISOString().slice(0, 10))
  const carregar = () => api.metricas(dias).then(setD).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [dias])
  async function gerar(slug = '') { setOcupado('pos'); try { const r = await api.posmortemGerar(slug); await carregar(); setErro(r.n ? '' : 'Nada para gerar: nenhuma peça publicada há 7 dias com métrica.') } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function relatorio() { setOcupado('rel'); try { setRel(await api.relatorioSemana(fim)) } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function alternar(a: Automacao) { try { await api.automacaoAlternar(a.id, !a.ligada); carregar(); carregarRodadas() } catch (e: any) { setErro(e.message) } }
  const [rod, setRod] = useState<Rodadas | null>(null); const [aviso, setAviso] = useState('')
  const estadoRodada: Record<string, string> = { pedido_aberto: 'pedido aberto no Editor (em andamento)', rascunho_publora: 'rascunho de Story na Publora', entregue_sem_publora: 'entregue · Publora não configurada', entregue_sem_video: 'entregue sem o vídeo', bloqueado_revisor: 'segurada pelo revisor de marca', sem_fonte: 'sem fonte nova', sem_video_origem: 'original não baixou', cancelado: 'cancelada', falhou: 'falhou' }
  const carregarRodadas = () => api.automacoesRodadas().then(setRod).catch(() => {})
  useEffect(() => { if (aba === 'auto') carregarRodadas() }, [aba])
  async function rodarStories() { if (!confirm('Abrir agora um pedido da série de Stories no Editor? Continua só rascunho: nada é publicado.')) return; setOcupado('stories'); try { const r = await api.storiesRodar(); setAviso(r.estado === 'sem_fonte' ? 'Nenhuma dúvida nova no GSI para esta rodada.' : `Pedido ${r.codigo || ''} aberto no Editor.`); carregarRodadas(); carregar() } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  const abertas = (id: string) => (rod?.rodadas || []).filter(r => r.automacao === id && r.estado === 'pedido_aberto')
  const msgConferir = (id: string, feitas: any[]) => { const ab = abertas(id).filter(r => !feitas.some(f => f.id === r.id)); return (feitas.length ? `${feitas.length} rodada(s) atualizada(s)${feitas.map(f => ` · ${f.codigo || ''} ${estadoRodada[f.estado] || f.estado}`).join('')}.` : 'Nada mudou.') + (ab.length ? ` ${ab.length} pedido(s) ainda em andamento no Editor (${ab.map(r => r.codigo).join(', ')}): confira de novo quando a entrega sair (o laço também confere a cada 10 min).` : '') }
  const [avisoStories, setAvisoStories] = useState(''); const [avisoReciclado, setAvisoReciclado] = useState('')
  const [exp, setExp] = useState<{ itens: any[]; abertos: number; ganhou: number; perdeu: number; empate: number; fechados_agora: number; regra: string } | null>(null)
  useEffect(() => { if (aba === 'auto') api.experimentos().then(setExp).catch(() => {}) }, [aba])
  async function fecharExp() { setOcupado('exp'); try { const r = await api.experimentos(true); setExp(r); setAvisoReciclado(r.fechados_agora ? `${r.fechados_agora} experimento(s) fechado(s).` : 'Nenhum experimento pronto para fechar (precisa de 7 dias de publicado e métrica do GSI).') } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function concluirStories() { setOcupado('concluir'); setAvisoStories('Conferindo…'); try { const r = await api.storiesConcluir(); setAvisoStories(msgConferir('stories_serie', r.feitas)); carregarRodadas(); carregar() } catch (e: any) { setAvisoStories(`Não consegui conferir: ${e.message}`) } finally { setOcupado('') } }
  async function configStories(campos: Record<string, string>) { try { await api.storiesConfig(campos); carregarRodadas(); carregar() } catch (e: any) { setErro(e.message) } }
  async function rodarReciclado() { if (!confirm('Abrir agora um pedido de Reel reciclado no Editor? O app escolhe um evergreen seu acima da mediana, baixa o original (pode levar um minuto) e pede só gancho, capa e legenda novos. Continua só rascunho: nada é publicado.')) return; setOcupado('reciclado'); try { const r = await api.recicladoRodar(); setAviso(r.estado === 'sem_fonte' ? 'Nenhum evergreen disponível com os critérios atuais.' : r.estado === 'sem_video_origem' ? 'Não consegui baixar o original; veja a lista de rodadas.' : `Pedido ${r.codigo || ''} aberto no Editor (${r.fonte?.titulo || ''}).`); carregarRodadas(); carregar() } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  async function concluirReciclado() { setOcupado('concluir2'); setAvisoReciclado('Conferindo…'); try { const r = await api.recicladoConcluir(); setAvisoReciclado(msgConferir('reel_reciclado', r.feitas)); carregarRodadas(); carregar() } catch (e: any) { setAvisoReciclado(`Não consegui conferir: ${e.message}`) } finally { setOcupado('') } }
  async function configReciclado(campos: Record<string, string>) { try { await api.recicladoConfig(campos); carregarRodadas(); carregar() } catch (e: any) { setErro(e.message) } }
  const estadoReciclado: Record<string, string> = { ...estadoRodada, rascunho_publora: 'rascunho de Reels na Publora', sem_fonte: 'sem evergreen disponível' }
  const res = d?.painel
  const cor = (r: number | null) => r == null ? 'text-nevoa' : r >= 1.5 ? 'text-green-300' : r <= 0.6 ? 'text-red-300' : ''
  return <div className="max-w-5xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Métricas e Automações</h2>
    <p className="text-nevoa mt-2 text-sm">O que foi publicado, como foi contra a mediana do formato, o que as automações fizeram e o que aprendemos. Versão 1: números do GSI (YouTube pela API, Instagram pela coleta antiga até a Meta entrar); vendas ficam fora por decisão. Peças e etiquetas: <Link to="/pecas" className="text-laranja hover:underline">Peças</Link>.</p>
    <div className="flex gap-2 mt-5 flex-wrap">{([['painel', '📈 Painel'], ['rende', '🧠 O que rende'], ['pos', '🧾 Pós-mortem'], ['auto', '⚙ Automações'], ['rel', '📄 Relatórios']] as const).map(([a, r]) => <button key={a} onClick={() => setAba(a)} className={`rounded-full px-3 py-1.5 text-sm border ${aba === a ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{r}{a === 'pos' && d?.posmortem.pendentes.length ? ` (${d.posmortem.pendentes.length})` : ''}</button>)}</div>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    {!d && <div className="text-nevoa mt-4">…</div>}

    {d && aba === 'painel' && res && <div className="mt-5">
      <div className="flex flex-wrap items-center gap-2 text-sm">{([7, 30, 90] as const).map(x => <button key={x} onClick={() => setDias(x)} className={`rounded-full px-3 py-1 border ${dias === x ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa'}`}>{x} dias</button>)}<span className="text-nevoa text-xs ml-2">{res.inicio} a {res.fim} · última medição {res.ultima_medicao ? new Date(res.ultima_medicao).toLocaleString('pt-BR') : '—'}</span></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">{([['Conteúdos', res.total.conteudos, res.anterior.conteudos], ['Views', res.total.views, res.anterior.views], ['Likes', res.total.likes, res.anterior.likes], ['Comentários', res.total.comentarios, res.anterior.comentarios]] as [string, number, number][]).map(([r, a, b]) => <div key={r} className="cartao p-3"><div className="text-[11px] text-nevoa uppercase tracking-wide">{r}</div><div className="text-xl font-bold">{n(a)}</div><div className={`text-xs ${b && a >= b ? 'text-green-300' : 'text-nevoa'}`}>{b ? `${a >= b ? '+' : ''}${Math.round((a - b) / b * 100)}% vs período anterior (${n(b)})` : 'sem período anterior'}</div></div>)}</div>
      <div className="grid md:grid-cols-2 gap-4 mt-4 text-sm">
        <div className="cartao p-3"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">Por formato (mediana de views)</div>{res.formatos.map(f => <div key={f.formato} className="flex gap-3 py-0.5"><span className="w-40 shrink-0">{f.formato}</span><span className="text-nevoa">{f.conteudos} conteúdos</span><span>{n(f.views)} views</span><span className="text-nevoa">mediana {n(f.views_mediana)}</span></div>)}{res.formatos.length === 0 && <div className="text-nevoa">Nada medido no período.</div>}</div>
        <div className="cartao p-3"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">Peças do Editor GS</div>
          <div className="flex flex-wrap gap-2 text-xs"><span className="selo">{d.pecas.total} peças</span><span className="selo">{d.pecas.com_metrica} com métrica</span><span className={`selo ${d.pecas.sem_etiqueta ? 'text-laranja' : ''}`}>{d.pecas.sem_etiqueta} sem campanha/pilar</span>{Object.entries(d.pecas.estados as Record<string, number>).map(([k, v]) => <span key={k} className="selo">{k}: {v}</span>)}</div>
          <div className="text-xs text-nevoa mt-2">Campanhas: {Object.entries(d.pecas.campanhas as Record<string, number>).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>
          <div className="text-xs text-nevoa mt-1">Pilares: {Object.entries(d.pecas.pilares as Record<string, number>).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>
          <Link to="/pecas" className="text-xs text-laranja hover:underline mt-2 inline-block">abrir a tabela de peças →</Link></div>
      </div>
      <div className="cartao p-3 mt-4 text-sm"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">Top do período (GSI, por views)</div>
        {res.top.map(i => <div key={i.id} className="flex items-center gap-3 py-1 border-t border-white/5 first:border-0"><span className="text-nevoa w-20 shrink-0 text-xs">{i.publicado.slice(5).split('-').reverse().join('/')}</span><a href={i.url} target="_blank" className="flex-1 truncate hover:underline">{i.titulo}</a><span className="text-xs text-nevoa">{i.plataforma}/{i.formato || '?'}</span><span className="w-20 text-right">{n(i.views)}</span><span className={`w-16 text-right ${cor(i.vs_mediana_formato)}`}>{i.vs_mediana_formato != null ? `${Number(i.vs_mediana_formato).toFixed(2)}×` : '—'}</span></div>)}
        {res.top.length === 0 && <div className="text-nevoa">Nenhum conteúdo medido no período.</div>}</div>
      <p className="text-nevoa text-[11px] mt-3">× = views divididas pela mediana do formato nos últimos 90 dias (performance-snapshot do GSI). Verde ≥ 1,5; vermelho ≤ 0,6. Para hipóteses e próximos conteúdos: Redes → Resultados → "Pedir análise ao Editor".</p>
    </div>}

    {aba === 'rende' && <PerfilRende />}
    {d && aba === 'pos' && <div className="mt-5 text-sm">
      <div className="flex flex-wrap items-center gap-2"><div className="font-bold">Pós-mortem D+{d.posmortem.dias}</div><span className="text-nevoa text-xs">ficha factual por peça publicada há {d.posmortem.dias}+ dias com métrica: números × mediana, veredito e uma hipótese (não causa). Vira aprendizado proposto; validar é humano.</span>
        <button onClick={() => gerar()} disabled={!!ocupado || d.posmortem.pendentes.length === 0} className="btn-laranja ml-auto px-4 py-1.5 disabled:opacity-40">{ocupado === 'pos' ? 'Gerando…' : `Gerar ${d.posmortem.pendentes.length} pendente(s)`}</button></div>
      {d.posmortem.pendentes.length > 0 && <div className="cartao p-3 mt-3"><div className="text-xs uppercase tracking-wide text-nevoa mb-1">Pendentes</div>{d.posmortem.pendentes.map(p => <div key={p.slug} className="flex items-center gap-2 py-1 border-t border-white/5 first:border-0 text-xs"><Link to={`/pecas/${p.slug}`} className="flex-1 truncate hover:underline">{p.titulo}</Link><span className="text-nevoa">{p.publicado_em?.slice(0, 10)}</span><span>{n(p.views)} views</span><span className={cor(p.vs_mediana)}>{p.vs_mediana != null ? `${p.vs_mediana.toFixed(2)}×` : '—'}</span><button onClick={() => gerar(p.slug)} className="rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">gerar</button></div>)}</div>}
      <div className="grid gap-3 mt-3">{d.posmortem.feitos.map(p => <div key={p.slug} className="cartao p-3">
        <div className="flex flex-wrap items-center gap-2"><Link to={`/pecas/${p.slug}`} className="font-bold hover:underline">{p.titulo || p.slug}</Link>{p.codigo && <span className="selo">{p.codigo}</span>}<span className={`rounded-full px-2 py-0.5 text-[11px] ${p.veredito.startsWith('acima') ? 'bg-green-500/20 text-green-300' : p.veredito.startsWith('abaixo') ? 'bg-red-500/20 text-red-300' : 'bg-white/10 text-nevoa'}`}>{p.veredito}</span><span className="text-nevoa text-xs ml-auto">publicada {p.publicado_em?.slice(0, 10)} · {p.idade_dias} dias · gerado {p.gerado_em.replace('T', ' ')}</span></div>
        <div className="text-xs mt-1">{p.plataforma}: {n(p.views)} views, {n(p.likes)} likes, {n(p.comentarios)} comentários · {p.razao != null ? `${Number(p.razao).toFixed(2)}× a mediana do formato ${p.formato_gsi || ''} (${n(p.mediana_formato)})` : 'sem mediana'}</div>
        <div className="mt-1"><ChipsEtiquetas e={p.etiquetas} /></div>
        <div className="text-xs text-nevoa mt-1">Hipótese: {p.hipotese}</div>
      </div>)}{d.posmortem.feitos.length === 0 && <div className="text-nevoa text-xs">Nenhum pós-mortem ainda. Ele aparece quando uma peça publicada por aqui completa 7 dias e o GSI já mediu.</div>}</div>
    </div>}

    {d && aba === 'auto' && <div className="mt-5 text-sm">
      <p className="text-nevoa text-xs">Três grupos: as do GSI (lidas dos arquivos dele; ligar e pausar é lá), as do próprio app, e as planejadas na proposta de 31/10 (a chave registra o que você quer ligado quando existirem; nada roda por causa dela).</p>
      {aviso && <div className="text-laranja text-xs mt-2">{aviso}</div>}
      {rod && <div className="cartao p-3 mt-4">
        <div className="flex flex-wrap items-center gap-2"><span className={`inline-block w-2 h-2 rounded-full ${d.automacoes.find(a => a.id === 'stories_serie')?.ligada ? 'bg-green-400' : 'bg-white/20'}`} /><span className="font-bold">Série de Stories · {rod.series[rod.config.serie]?.nome || rod.config.serie}</span>{!d.automacoes.find(a => a.id === 'stories_serie')?.ligada && <button onClick={() => { const a = d.automacoes.find(x => x.id === 'stories_serie'); if (a) alternar(a) }} className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-nevoa hover:bg-white/5">desligada · ligar agenda</button>}<span className="text-nevoa text-xs">· {rod.devida ? 'na hora de rodar' : rod.motivo} · próxima {rod.proxima}</span>
          <button onClick={rodarStories} disabled={!!ocupado} className="btn-laranja ml-auto px-3 py-1 text-xs disabled:opacity-40">{ocupado === 'stories' ? 'Abrindo…' : 'Rodar agora'}</button>
          <button onClick={concluirStories} disabled={!!ocupado} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-40">{ocupado === 'concluir' ? 'Conferindo…' : 'Conferir entregas'}</button></div>
        {avisoStories && <div className="text-xs text-laranja mt-1">{avisoStories}</div>}
        <div className="text-xs text-nevoa mt-1">O app escolhe uma dúvida real da audiência (comentário público, sem autor) no GSI, abre o pedido no Editor com o fluxo stories-serie e, quando a entrega fica pronta, manda o vídeo das 3 telas à Publora como <b>rascunho</b> de Story. Agendar e publicar continuam sendo cliques seus. {rod.publora ? '' : 'Publora ainda sem chave: a rodada para em "entregue" e você publica pelo cartão.'}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs mt-2"><span className="text-nevoa">Toda</span>
          <select value={rod.config.dia_semana} onChange={e => configStories({ dia_semana: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{rod.dias.map((n, i) => <option key={i} value={i}>{n}</option>)}</select>
          <span className="text-nevoa">às</span>
          <select value={rod.config.hora} onChange={e => configStories({ hora: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{h}h</option>)}</select>
          <span className="text-nevoa">· fontes: {rod.config.plataformas.join(', ')}{rod.config.contas.length ? ` · contas: ${rod.config.contas.join(', ')}` : ' · conta do Instagram da Publora (automática)'}</span></div>
        {rod.rodadas.filter(r => r.automacao === 'stories_serie').length > 0 && <div className="mt-3 grid gap-1 text-xs">{rod.rodadas.filter(r => r.automacao === 'stories_serie').map(r => <div key={r.id} className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-1">
          <span className="text-nevoa w-28 shrink-0">{r.quando.slice(0, 16).replace('T', ' ')}</span>
          {r.issue ? <Link to={`/c/${r.issue}`} className="hover:underline">{r.codigo || 'pedido'}</Link> : <span className="text-nevoa">—</span>}
          <span className={`rounded-full px-2 py-0.5 text-[11px] ${r.estado === 'rascunho_publora' ? 'bg-green-500/20 text-green-300' : r.estado === 'bloqueado_revisor' || r.estado === 'falhou' ? 'bg-red-500/20 text-red-300' : 'bg-white/10 text-nevoa'}`}>{estadoRodada[r.estado] || r.estado}</span>
          {r.fonte && <span className="truncate flex-1 text-white/80" title={r.fonte.texto}>“{r.fonte.texto.slice(0, 90)}{r.fonte.texto.length > 90 ? '…' : ''}” <span className="text-nevoa">({r.fonte.plataforma}{r.fonte.topicos?.length ? ` · ${r.fonte.topicos.join(', ')}` : ''})</span></span>}
          {r.por && r.por !== 'laço' && <span className="text-nevoa">por {r.por}</span>}
        </div>)}</div>}
        {rod.rodadas.filter(r => r.automacao === 'stories_serie').length === 0 && <div className="text-nevoa text-xs mt-2">Nenhuma rodada ainda.</div>}
      </div>}
      {rod && rod.reciclado && <div className="cartao p-3 mt-4">
        <div className="flex flex-wrap items-center gap-2"><span className={`inline-block w-2 h-2 rounded-full ${d.automacoes.find(a => a.id === 'reel_reciclado')?.ligada ? 'bg-green-400' : 'bg-white/20'}`} /><span className="font-bold">Reel reciclado com gancho novo</span>{!d.automacoes.find(a => a.id === 'reel_reciclado')?.ligada && <button onClick={() => { const a = d.automacoes.find(x => x.id === 'reel_reciclado'); if (a) alternar(a) }} className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-nevoa hover:bg-white/5">desligada · ligar agenda</button>}<span className="text-nevoa text-xs">· {rod.reciclado.devida ? 'na hora de rodar' : rod.reciclado.motivo} · próxima {rod.reciclado.proxima}</span>
          <button onClick={rodarReciclado} disabled={!!ocupado} className="btn-laranja ml-auto px-3 py-1 text-xs disabled:opacity-40">{ocupado === 'reciclado' ? 'Baixando e abrindo…' : 'Rodar agora'}</button>
          <button onClick={concluirReciclado} disabled={!!ocupado} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-40">{ocupado === 'concluir2' ? 'Conferindo…' : 'Conferir entregas'}</button></div>
        {avisoReciclado && <div className="text-xs text-laranja mt-1">{avisoReciclado}</div>}
        <div className="text-xs text-nevoa mt-1">Experimento "mesma peça, outro gancho": o app escolhe um Reel ou Short seu que rendeu acima da mediana (GSI) ou uma peça publicada por aqui, baixa o original, e o Editor entrega a mesma edição com só o gancho na tela, a capa e a legenda trocados. Vai à Publora como <b>rascunho</b> de Reels; a ficha da peça guarda o experimento e o pós-mortem D+7 fecha a comparação. {rod.publora ? '' : 'Publora ainda sem chave: a rodada para em "entregue".'}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs mt-2"><span className="text-nevoa">A cada</span>
          <select value={rod.reciclado.config.cada_dias} onChange={e => configReciclado({ cada_dias: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{[1, 2, 3, 5, 7, 10, 14, 21, 30].map(x => <option key={x} value={x}>{x} dia(s)</option>)}</select>
          <span className="text-nevoa">às</span>
          <select value={rod.reciclado.config.hora} onChange={e => configReciclado({ hora: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{h}h</option>)}</select>
          <span className="text-nevoa">· razão mínima</span>
          <select value={rod.reciclado.config.min_razao} onChange={e => configReciclado({ min_razao: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{[1, 1.2, 1.5, 2, 3, 5, 10].map(x => <option key={x} value={x}>{x}×</option>)}</select>
          <span className="text-nevoa">· publicada há</span>
          <select value={rod.reciclado.config.min_idade_dias} onChange={e => configReciclado({ min_idade_dias: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1">{[0, 14, 30, 45, 60, 90, 180].map(x => <option key={x} value={x}>{x}+ dias</option>)}</select>
          <label className="flex items-center gap-1 text-nevoa"><input type="checkbox" checked={rod.reciclado.config.voz_clonada} onChange={e => configReciclado({ voz_clonada: e.target.checked ? 'sim' : 'nao' })} /> abertura com voz clonada (rotulada)</label>
          <span className="text-nevoa">· fontes: {rod.reciclado.config.plataformas.join(', ')}</span></div>
        {rod.reciclado.candidatos.length > 0 && <div className="mt-3"><div className="text-[11px] uppercase tracking-wide text-nevoa">Próximos candidatos (ainda não reciclados)</div>
          <div className="grid gap-1 text-xs mt-1">{rod.reciclado.candidatos.map(c => <div key={`${c.plataforma}-${c.id}`} className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-1">
            <span className="text-nevoa w-20 shrink-0">{c.publicado.slice(5).split('-').reverse().join('/')}</span>
            {c.url ? <a href={c.url} target="_blank" className="flex-1 truncate hover:underline" title={c.legenda}>{c.titulo}</a> : <Link to={`/pecas/${c.slug_origem}`} className="flex-1 truncate hover:underline">{c.titulo}</Link>}
            <span className="text-nevoa">{c.origem === 'app' ? 'peça do app' : c.plataforma}{c.duracao_s ? ` · ${c.duracao_s} s` : ''}</span><span>{n(c.views)}</span><span className={cor(c.razao)}>{c.razao != null ? `${c.razao}×` : '—'}</span>
          </div>)}</div></div>}
        {rod.reciclado.candidatos.length === 0 && <div className="text-nevoa text-xs mt-2">Nenhum candidato com os critérios atuais (ou todos já reciclados).</div>}
        {exp && exp.itens.length > 0 && <div className="mt-3 text-xs"><div className="flex items-center gap-2"><span className="text-[11px] uppercase tracking-wide text-nevoa">Experimentos "mesma peça, outro gancho"</span><span className="text-nevoa">{exp.abertos} aberto(s) · <span className="text-green-300">{exp.ganhou} ganhou</span> · <span className="text-red-300">{exp.perdeu} perdeu</span> · {exp.empate} empate</span><button onClick={fecharExp} disabled={!!ocupado} className="ml-auto rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5 disabled:opacity-40">{ocupado === 'exp' ? 'Conferindo…' : 'Fechar os prontos (D+7)'}</button></div>
          <div className="grid gap-1 mt-1">{exp.itens.map(e => <div key={e.slug} className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-1"><Link to={`/pecas/${e.slug}`} className="hover:underline">{e.codigo || e.slug}</Link><span className={`rounded-full px-2 py-0.5 text-[11px] ${e.status === 'ganhou' ? 'bg-green-500/20 text-green-300' : e.status === 'perdeu' ? 'bg-red-500/20 text-red-300' : 'bg-white/10 text-nevoa'}`}>{e.status}</span><span className="truncate flex-1" title={`original: ${e.gancho_original || '—'}`}>“{e.gancho_novo}” <span className="text-nevoa">vs “{(e.gancho_original || '').slice(0, 50)}”</span></span>{e.resultado && <span className="text-nevoa">{e.resultado.razao_nova}× vs {e.resultado.razao_original}×</span>}{!e.resultado && <span className="text-nevoa">original {e.original?.razao}×</span>}</div>)}</div>
          <div className="text-[11px] text-nevoa mt-1">{exp.regra}.</div></div>}
        {rod.rodadas.filter(r => r.automacao === 'reel_reciclado').length > 0 && <div className="mt-3 grid gap-1 text-xs"><div className="text-[11px] uppercase tracking-wide text-nevoa">Rodadas</div>{rod.rodadas.filter(r => r.automacao === 'reel_reciclado').map(r => <div key={r.id} className="flex flex-wrap items-center gap-2 border-t border-white/5 pt-1">
          <span className="text-nevoa w-28 shrink-0">{r.quando.slice(0, 16).replace('T', ' ')}</span>
          {r.issue ? <Link to={`/c/${r.issue}`} className="hover:underline">{r.codigo || 'pedido'}</Link> : <span className="text-nevoa">—</span>}
          <span className={`rounded-full px-2 py-0.5 text-[11px] ${r.estado === 'rascunho_publora' ? 'bg-green-500/20 text-green-300' : r.estado === 'bloqueado_revisor' || r.estado === 'falhou' || r.estado === 'sem_video_origem' ? 'bg-red-500/20 text-red-300' : 'bg-white/10 text-nevoa'}`}>{estadoReciclado[r.estado] || r.estado}</span>
          {r.fonte && <span className="truncate flex-1 text-white/80" title={r.fonte.legenda || ''}>{r.fonte.titulo} <span className="text-nevoa">({r.fonte.origem === 'app' ? 'peça do app' : r.fonte.plataforma}{r.fonte.razao != null ? ` · ${r.fonte.razao}×` : ''})</span></span>}
          {r.gancho_novo && <span className="text-laranja truncate max-w-[16rem]" title={`original: ${r.gancho_original || '—'}`}>“{r.gancho_novo}”</span>}
          {r.slug && (r.estado === 'rascunho_publora' || r.estado === 'entregue_sem_publora') && <Link to={`/pecas/${r.slug}`} className="text-nevoa hover:underline">ficha</Link>}
          {r.por && r.por !== 'laço' && <span className="text-nevoa">por {r.por}</span>}
        </div>)}</div>}
      </div>}
      <AutomacoesDados onMudou={carregar} />
      <PastaVigiada />
      {(['GSI', 'Editor GS', 'Planejada'] as const).map(g => <div key={g} className="mt-4"><div className="text-xs uppercase tracking-wide text-nevoa mb-2">{g === 'Planejada' ? 'Planejadas (proposta de 31/10)' : g}</div>
        <div className="grid gap-2">{d.automacoes.filter(a => a.grupo === g).map(a => <div key={a.id} className="cartao p-3">
          <div className="flex flex-wrap items-center gap-2"><span className={`inline-block w-2 h-2 rounded-full ${a.ligada ? 'bg-green-400' : 'bg-white/20'}`} /><span className="font-bold">{a.nome}</span><span className="text-nevoa text-xs">· {a.estado}</span>{a.tamanho && <span className="selo">{a.tamanho}</span>}
            {(g === 'Planejada' || a.existe) && <button onClick={() => alternar(a)} className={`ml-auto rounded-full border px-3 py-1 text-xs ${a.ligada ? 'border-laranja text-laranja' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{a.ligada ? 'quero (ligada)' : 'quero esta'}</button>}
            {a.ultima && <span className="ml-auto text-xs text-nevoa">última: {a.ultima}</span>}</div>
          <div className="text-xs mt-1">{a.detalhe}</div>
          {a.precisa && <div className="text-xs text-nevoa mt-1">precisa: {a.precisa}</div>}
          <div className="text-[11px] text-nevoa mt-1">onde: {a.onde}{a.ultimo_arquivo ? ` · ${a.ultimo_arquivo}` : ''}</div>
        </div>)}</div></div>)}
    </div>}

    {d && aba === 'rel' && <div className="mt-5 text-sm">
      <div className="cartao p-3"><div className="flex flex-wrap items-center gap-2"><div className="font-bold">Relatório da semana</div><span className="text-nevoa text-xs">7 dias até</span><input type="date" value={fim} onChange={e => setFim(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1 text-xs" /><button onClick={relatorio} disabled={ocupado === 'rel'} className="btn-laranja px-4 py-1.5">{ocupado === 'rel' ? 'Gerando…' : 'Gerar'}</button>{rel && <span className="text-xs text-nevoa">gravado em workspace/relatorios/{rel.arquivo.split('/').pop()}</span>}</div>
        {rel && <pre className="whitespace-pre-wrap text-xs text-white/80 mt-3 max-h-[32rem] overflow-auto font-sans">{rel.conteudo}</pre>}
        <div className="text-xs text-nevoa mt-2">Números do GSI e das peças do app, sem modelo de linguagem. O relatório do mês continua em Redes → Resultados.</div></div>
    </div>}
  </div>
}
