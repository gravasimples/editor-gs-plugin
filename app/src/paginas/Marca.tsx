import { useEffect, useState } from 'react'
import { api, type Marca } from '../api'

function Inline({ t }: { t: string }) {
  const partes = t.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return <>{partes.map((p, i) => p.startsWith('`') ? <code key={i} className="bg-white/10 rounded px-1 text-[0.9em]">{p.slice(1, -1)}</code> : p.startsWith('**') ? <b key={i}>{p.slice(2, -2)}</b> : <span key={i}>{p}</span>)}</>
}

/** Renderizador mínimo de Markdown: parágrafos, listas, citações e tabelas. Suficiente para os arquivos de contexto do GSI. */
function Md({ texto }: { texto: string }) {
  const linhas = texto.split('\n'); const blocos: JSX.Element[] = []; let i = 0
  while (i < linhas.length) {
    const l = linhas[i]
    if (!l.trim()) { i++; continue }
    if (l.startsWith('|')) {
      const tab: string[] = []; while (i < linhas.length && linhas[i].startsWith('|')) { tab.push(linhas[i]); i++ }
      const celulas = (s: string) => s.split('|').slice(1, -1).map(x => x.trim())
      const [cab, ...corpo] = tab.filter(r => !/^\|\s*-+/.test(r))
      blocos.push(<div key={i} className="overflow-x-auto my-2"><table className="text-sm w-full"><thead><tr>{celulas(cab).map((c, k) => <th key={k} className="text-left text-nevoa font-normal pr-4 pb-1 border-b border-white/10"><Inline t={c} /></th>)}</tr></thead>
        <tbody>{corpo.map((r, k) => <tr key={k}>{celulas(r).map((c, j) => <td key={j} className="pr-4 py-1 align-top border-b border-white/5"><Inline t={c} /></td>)}</tr>)}</tbody></table></div>)
      continue
    }
    if (/^(\s*[-*]|\s*\d+\.)\s/.test(l)) {
      const itens: string[] = []; while (i < linhas.length && /^(\s*[-*]|\s*\d+\.)\s/.test(linhas[i])) { itens.push(linhas[i].replace(/^(\s*[-*]|\s*\d+\.)\s/, '')); i++ }
      blocos.push(<ul key={i} className="list-disc pl-5 my-2 grid gap-1 text-sm">{itens.map((x, k) => <li key={k}><Inline t={x} /></li>)}</ul>); continue
    }
    if (l.startsWith('>')) {
      const q: string[] = []; while (i < linhas.length && linhas[i].startsWith('>')) { q.push(linhas[i].replace(/^>\s?/, '')); i++ }
      blocos.push(<blockquote key={i} className="border-l-2 border-laranja/60 pl-3 my-2 text-sm text-nevoa"><Inline t={q.join(' ')} /></blockquote>); continue
    }
    if (l.startsWith('### ')) { blocos.push(<h4 key={i} className="font-bold mt-3 mb-1">{l.slice(4)}</h4>); i++; continue }
    const p: string[] = []; while (i < linhas.length && linhas[i].trim() && !/^(\||>|#|\s*[-*]\s|\s*\d+\.\s)/.test(linhas[i])) { p.push(linhas[i]); i++ }
    blocos.push(<p key={i} className="text-sm my-2 leading-relaxed"><Inline t={p.join(' ')} /></p>)
  }
  return <div>{blocos}</div>
}

const ESTADO: Record<string, [string, string]> = { validated: ['validado', 'text-green-300'], observed: ['observado', 'text-nevoa'], hypothesis: ['hipótese', 'text-yellow-300'], pending_validation: ['pendente de validação', 'text-red-300'], outdated: ['desatualizado', 'text-red-300'] }
const CAT: Record<string, string> = { course: 'curso', bundle: 'combo', service: 'serviço', community: 'comunidade', digital_asset: 'ativo digital', checklist: 'checklist', program: 'programa', upgrade: 'upgrade', unknown: '?' }
const preco = (o: any) => o.preco == null ? 'preço não registrado' : `R$ ${Number(o.preco).toFixed(2).replace('.', ',')}${o.parcelas && o.valor_parcela ? ` ou ${o.parcelas}× R$ ${Number(o.valor_parcela).toFixed(2).replace('.', ',')}` : ''}`

export default function MarcaPagina() {
  const [d, setD] = useState<Marca | null>(null)
  const [aba, setAba] = useState<'manual' | 'voz' | 'produtos'>('manual')
  const [erro, setErro] = useState(''); const [gravando, setGravando] = useState(false); const [aviso, setAviso] = useState('')
  useEffect(() => { api.marca().then(setD).catch(e => setErro(e.message)) }, [])
  async function atualizarCopia() { setGravando(true); setAviso(''); try { const r = await api.marca(true); setD(r); setAviso(`Cópia do Editor atualizada: ${(r.arquivos || []).join(', ')} em ${r.destino}`) } catch (e: any) { setErro(e.message) } finally { setGravando(false) } }
  if (erro) return <div className="p-8 text-red-300">{erro}</div>
  if (!d) return <div className="p-8 text-nevoa">Carregando…</div>
  const abas: [typeof aba, string][] = [['manual', 'Manual da marca'], ['voz', 'Tom de voz'], ['produtos', 'Produtos e ofertas']]
  const fonte = aba === 'manual' ? d.manual : aba === 'voz' ? d.voz : null
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Marca</h2>
      <button onClick={atualizarCopia} disabled={gravando} className="ml-auto rounded-full border border-laranja/60 text-laranja px-4 py-1.5 text-sm hover:bg-laranja/10">{gravando ? 'Gravando…' : 'Atualizar cópia do Editor'}</button></div>
    <p className="text-nevoa mt-2 text-sm">Lido do GSI (contexto/ e gs.db), só leitura: para mudar, edite na fonte. O Editor recebe uma cópia em <code className="bg-white/10 rounded px-1">marca/</code> (manual.md, voz.md, produtos.md), refeita a cada subida do gateway e por este botão. No Novo pedido, o chip “Ficha de marca” manda o Editor consultá-la.</p>
    {aviso && <div className="mt-2 text-xs text-green-300">{aviso}</div>}
    <div className="flex gap-2 mt-5 flex-wrap">{abas.map(([k, r]) => <button key={k} onClick={() => setAba(k)} className={`rounded-full px-4 py-1.5 text-sm border ${aba === k ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 text-nevoa hover:bg-white/5'}`}>{r}</button>)}</div>
    {fonte && <div className="mt-5 grid gap-3">
      {!fonte.existe && <div className="cartao p-4 text-sm text-red-300">Arquivo não encontrado: {fonte.arquivo}</div>}
      {fonte.existe && <div className="text-xs text-nevoa">{fonte.arquivo} · atualizado em {fonte.atualizado ? new Date(fonte.atualizado).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</div>}
      {fonte.secoes.map((s, i) => <details key={i} open={i < 2} className="cartao p-4"><summary className="cursor-pointer font-bold">{s.titulo}</summary><div className="mt-2 text-white/90"><Md texto={s.conteudo} /></div></details>)}
    </div>}
    {aba === 'produtos' && <div className="mt-5 grid gap-3">
      <div className="rounded-xl bg-laranja/10 border border-laranja/40 p-3 text-sm">{d.produtos.aviso}</div>
      {d.produtos.erro && <div className="cartao p-4 text-sm text-red-300">{d.produtos.erro}</div>}
      {d.produtos.itens.map(p => <details key={p.slug} className="cartao p-4"><summary className="cursor-pointer"><span className="font-bold">{p.nome}</span> <span className="text-xs text-nevoa">· {CAT[p.categoria || ''] || p.categoria} · <span className={ESTADO[p.status]?.[1] || ''}>{ESTADO[p.status]?.[0] || p.status}</span>{p.ofertas.length ? ` · ${p.ofertas.length} oferta(s)` : ''}</span></summary>
        <div className="mt-3 grid gap-1 text-sm">
          {p.apelidos.length > 0 && <div><span className="text-nevoa">Também chamado:</span> {p.apelidos.join(', ')}</div>}
          {p.publico && <div><span className="text-nevoa">Público:</span> {p.publico}</div>}
          {p.problema && <div><span className="text-nevoa">Problema que resolve:</span> {p.problema}</div>}
          {p.promessa && <div><span className="text-nevoa">Promessa (texto da página):</span> {p.promessa}</div>}
          {p.entregaveis.length > 0 && <div><span className="text-nevoa">Entregáveis:</span> {p.entregaveis.join(', ')}</div>}
          {p.componentes.length > 0 && <div><span className="text-nevoa">Inclui:</span> {p.componentes.join(', ')}</div>}
          {p.ofertas.length > 0 && <div className="mt-2 grid gap-1">{p.ofertas.map(o => <div key={o.id} className="rounded-xl bg-black/30 p-2 text-xs flex flex-wrap gap-x-3 gap-y-1"><span className="font-bold text-white">{preco(o)}</span>{o.acesso && <span>{o.acesso}</span>}<span className="text-nevoa">visto em {o.visto_em}</span><span className={ESTADO[o.status]?.[1] || ''}>{ESTADO[o.status]?.[0] || o.status}</span>{o.url && <a href={o.url} target="_blank" rel="noreferrer" className="text-laranja">{o.url}</a>}{o.notas && <span className="text-nevoa w-full">{o.notas}</span>}</div>)}</div>}
          {p.pendencias.length > 0 && <div className="text-xs text-red-300 mt-1">Pendências (não afirmar): {p.pendencias.join('; ')}</div>}
          <div className="text-xs text-nevoa mt-1">Fonte: {p.fonte}</div>
        </div></details>)}
      {d.produtos_md.existe && <details className="cartao p-4"><summary className="cursor-pointer font-bold">Escada de ofertas e regras (contexto/produtos.md)</summary><div className="mt-2">{d.produtos_md.secoes.map((s, i) => <div key={i}><h4 className="font-bold mt-3 mb-1">{s.titulo}</h4><Md texto={s.conteudo} /></div>)}</div></details>}
    </div>}
  </div>
}
