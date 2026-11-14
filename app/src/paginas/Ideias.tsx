import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Anotacao, type Ideia } from '../api'
const ABAS: [string, string][] = [['anotacoes', 'Anotações do celular'], ['com_material', 'Com material (Notion)'], ['carrosseis', 'Carrosséis (Notion)'], ['approved', 'Aprovadas no GSI'], ['proposed', 'Propostas no GSI']]
export default function Ideias() {
  const [ideias, setIdeias] = useState<Ideia[]>([]); const [filtro, setFiltro] = useState('com_material'); const [erro, setErro] = useState(''); const [carregando, setCarregando] = useState(false)
  const nav = useNavigate()
  const [notas, setNotas] = useState<Anotacao[]>([]); const [notaTexto, setNotaTexto] = useState('')
  useEffect(() => { setErro(''); setCarregando(true); if (filtro === 'anotacoes') { api.anotacoes().then(setNotas).catch(e => setErro(e.message)).finally(() => setCarregando(false)); return } api.ideias(filtro).then(setIdeias).catch(e => setErro(e.message)).finally(() => setCarregando(false)) }, [filtro])
  async function anotar() { if (!notaTexto.trim()) return; try { await api.novaAnotacao(notaTexto); setNotaTexto(''); setNotas(await api.anotacoes()) } catch (e: any) { setErro(e.message) } }
  async function pedidoDaNota(n: Anotacao) { try { const r = await api.anotacaoPedido(n.id); nav(r.url) } catch (e: any) { setErro(e.message) } }
  async function mudarStatus(n: Anotacao, st: string) { try { const r = await api.anotacaoStatus(n.id, st); setNotas(notas.map(x => x.id === n.id ? r : x)) } catch (e: any) { setErro(e.message) } }
  const COLUNAS: [string, string][] = [['a_fazer', 'A fazer'], ['em_producao', 'Em produção'], ['feita', 'Feitas']]
  async function apagarNota(n: Anotacao) { if (!confirm(`Apagar a anotação "${n.titulo}"?`)) return; try { await api.apagarAnotacao(n.id); setNotas(notas.filter(x => x.id !== n.id)) } catch (e: any) { setErro(e.message) } }
  async function carrossel(i: Ideia) {
    try {
      const t = await api.notionTexto(i.id)
      const roteiro = [t.roteiro_pulso, t.corpo].filter(Boolean).join('\n\n').slice(0, 6000)
      nav('/', { state: { notion_page: i.id, pedido: `Crie o carrossel "${i.titulo}" (cartão do Notion ${t.url || i.notion_url}) com o fluxo carrossel, modelo tipográfico, 5 a 8 slides com CTA no último. Siga o roteiro do cartão abaixo; se eu anexar fotos ou vídeo, use como material (quadros nítidos do vídeo).\n\nROTEIRO DO CARTÃO:\n${roteiro || '(cartão sem roteiro: proponha a partir do título)'}`, fluxo: 'carrossel' } })
    } catch (e: any) { setErro(e.message) }
  }
  function usar(i: Ideia) {
    const partes = [`Conteúdo: ${i.titulo}.`]
    if (i.origem === 'notion') {
      partes.push(`Cartão do Notion: ${i.notion_url || i.id}.`)
      if (i.url) partes.push(`Material: ${i.url} (se for pasta do Drive ou vídeo do YouTube, me diga qual arquivo usar ou anexe o vídeo aqui).`)
      if (i.roteiro) partes.push('O roteiro já está no cartão do Notion; siga ele.')
      partes.push('Edite com o fluxo reels-padrao e gere o projeto do CapCut.')
    } else {
      if (i.descricao) partes.push(i.descricao)
      if (i.publico) partes.push(`Público: ${i.publico}.`)
      partes.push('Quero o roteiro e, se eu anexar vídeo, a edição com o fluxo reels-padrao.')
    }
    nav('/', { state: { pedido: partes.join(' '), notion_page: i.origem === 'notion' ? i.id : undefined } })
  }
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Ideias</h2>
    <p className="text-nevoa mt-2">"Anotações" são as ideias rápidas suas e do celular (viram pedido só com clique). "Com material" vem do Notion Mídias: cartões com Fila = Edição, Material pronto ou em Arte/Edição, ou seja, vídeo já gravado que só falta editar. As outras abas vêm do banco do GSI. Tudo só leitura.</p>
    <div className="flex flex-wrap gap-2 mt-4 text-sm">{ABAS.map(([v, r]) => <button key={v} onClick={() => setFiltro(v)} className={`rounded-full px-3 py-1 border border-white/15 ${filtro === v ? 'bg-white/10' : 'text-nevoa'}`}>{r}</button>)}</div>
    {erro && <div className="text-red-300 mt-4 text-sm">{erro}</div>}
    {carregando && <div className="text-nevoa mt-4 text-sm">Carregando…</div>}
    {filtro === 'anotacoes' && <div className="mt-5">
      <div className="cartao p-4"><textarea value={notaTexto} onChange={e => setNotaTexto(e.target.value)} rows={2} placeholder="Anotar uma ideia, colar um link…" className="w-full bg-transparent outline-none resize-none placeholder:text-nevoa" /><div className="flex items-center gap-2 mt-2"><span className="text-xs text-nevoa">Do celular: Compartilhar → atalho "Editor GS" → Guardar nas anotações (Ajuda).</span><button onClick={anotar} disabled={!notaTexto.trim()} className="btn-laranja ml-auto px-4 py-1.5 text-sm disabled:opacity-40">Anotar</button></div></div>
      <div className="grid gap-4 mt-4 md:grid-cols-3">{COLUNAS.map(([st, rotulo]) => { const col = notas.filter(n => (n.status || 'a_fazer') === st); return <div key={st} className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-nevoa mb-2">{rotulo} <span className="text-white/50">{col.length}</span></div>
        <div className="grid gap-3">{col.map(n => <div key={n.id} className={`cartao p-3 ${st === 'feita' ? 'opacity-70' : ''}`}><div className="flex items-start gap-2"><div className="flex-1 min-w-0"><div className="font-bold text-sm">{n.titulo}</div>{n.texto && n.texto !== n.titulo && <div className="text-xs text-nevoa mt-1 whitespace-pre-wrap line-clamp-4">{n.texto}</div>}
          <div className="text-[11px] text-nevoa mt-2 flex flex-wrap gap-2"><span>{new Date(n.quando).toLocaleString('pt-BR')}</span><span>{n.origem}</span>{n.arquivos.map(a => <span key={a} className="selo">{a}</span>)}{n.links.map(l => <a key={l} href={l} target="_blank" rel="noreferrer" className="underline text-white/80 truncate max-w-xs">{l}</a>)}{n.pedido && st !== 'a_fazer' && <a href={n.pedido} className="underline text-laranja">pedido ↗</a>}</div></div>
          <button onClick={() => apagarNota(n)} className="text-nevoa hover:text-red-300 shrink-0">✕</button></div>
          <div className="flex flex-wrap gap-2 mt-2 text-xs">{st === 'a_fazer' && <button onClick={() => pedidoDaNota(n)} className="btn-laranja px-3 py-1">Criar pedido</button>}{st === 'a_fazer' && <button onClick={() => mudarStatus(n, 'em_producao')} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Já estou produzindo</button>}{st === 'em_producao' && <button onClick={() => mudarStatus(n, 'feita')} className="rounded-full border border-green-400/50 text-green-300 px-3 py-1 hover:bg-green-400/10">Marcar feita</button>}{st !== 'a_fazer' && <button onClick={() => mudarStatus(n, 'a_fazer')} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Voltar para A fazer</button>}</div></div>)}
        {col.length === 0 && <div className="text-nevoa text-xs">—</div>}</div></div> })}
      </div>
        {notas.length === 0 && !carregando && <div className="text-nevoa mt-3">Nenhuma anotação. Mande do celular ou anote aqui.</div>}
    </div>}
    <div className="grid gap-3 mt-5">{filtro !== 'anotacoes' && ideias.map(i => <div key={i.id} className="cartao p-4">
      <div className="flex items-start gap-3"><div className="flex-1 min-w-0"><div className="font-bold">{i.titulo}</div>
        {i.descricao && <div className="text-sm text-nevoa mt-1">{i.descricao}</div>}
        {i.motivo && i.motivo.length > 0 && <div className="text-sm text-laranja mt-1">{i.motivo.join(' · ')}</div>}
        <div className="text-[11px] text-nevoa mt-2 flex flex-wrap items-center gap-2">
          {i.origem === 'notion' ? <>{i.status && <span className="selo">{i.status}</span>}{i.prioridade && <span>prioridade {i.prioridade}</span>}{i.material && <span>{i.material}</span>}{Array.isArray(i.formato) && i.formato.map(f => <span key={f}>{f}</span>)}{i.roteiro && <span>roteiro no cartão</span>}
            {i.url && <a href={i.url} target="_blank" rel="noreferrer" className="underline text-white/80">material ↗</a>}{i.notion_url && <a href={i.notion_url} target="_blank" rel="noreferrer" className="underline text-white/80">Notion ↗</a>}</>
            : <><span className="selo">{i.id}</span><span>{i.status === 'approved' ? 'aprovada' : 'proposta'}</span>{i.familia && <span>{i.familia}</span>}{typeof i.formato === 'string' && <span>{i.formato}</span>}{(i.reforcos || 0) > 0 && <span>{i.reforcos} reforço(s)</span>}</>}
        </div></div>
        <button onClick={() => (filtro === 'carrosseis' || (Array.isArray(i.formato) ? i.formato : [i.formato]).some(f => String(f || '').toLowerCase().startsWith('carros'))) ? carrossel(i) : usar(i)} className="btn-laranja px-3 py-1.5 text-sm shrink-0">Criar pedido</button></div>
    </div>)}{filtro !== 'anotacoes' && ideias.length === 0 && !erro && !carregando && <div className="text-nevoa">Nenhum item nesse filtro.</div>}</div>
  </div>
}
