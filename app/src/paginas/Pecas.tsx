import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type PecaFicha, type PecaLinha, type PecaOpcoes } from '../api'
import { ChipsEtiquetas, FormEtiquetas, rotulo } from '../Etiquetas'

const ESTADOS = ['postado ou agendado', 'no Drive', 'ainda não usado']

export function PecasLista() {
  const [dados, setDados] = useState<{ itens: PecaLinha[]; resumo: any; opcoes: PecaOpcoes } | null>(null)
  const [f, setF] = useState<Record<string, string>>(() => { const c = new URLSearchParams(window.location.search).get('campanha'); const r: Record<string, string> = {}; if (c) r.campanha = c; return r }); const [erro, setErro] = useState('')
  const nav = useNavigate()
  useEffect(() => { api.pecas(Object.fromEntries(Object.entries(f).filter(([, v]) => v))).then(setDados).catch(e => setErro(e.message)) }, [JSON.stringify(f)])
  if (erro) return <div className="max-w-5xl mx-auto px-4 py-8 text-red-300">{erro}</div>
  if (!dados) return <div className="max-w-5xl mx-auto px-4 py-8 text-nevoa">…</div>
  const Sel = ({ k, lista, rot = (x: string) => x }: { k: string; lista: string[]; rot?: (x: string) => string }) => <select value={f[k] || ''} onChange={e => setF({ ...f, [k]: e.target.value })} className="rounded-full border border-white/15 bg-card px-2 py-1 text-xs"><option value="">{k}: todos</option>{lista.map(x => <option key={x} value={x}>{rot(x)}</option>)}</select>
  const r = dados.resumo
  return <div className="max-w-6xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Peças</h2>
    <p className="text-nevoa mt-2 text-sm">Uma linha por entrega, com as etiquetas (campanha, pilar, gancho, formato, voz, origem), o estado de uso e a última métrica do GSI quando a peça publicada casa com um post. É a base da aba Métricas e Automações.</p>
    <div className="flex flex-wrap gap-2 mt-3 text-xs">
      <span className="selo">{r.total} peças</span><span className="selo">{r.com_metrica} com métrica</span><span className={`selo ${r.sem_etiqueta ? 'text-laranja' : ''}`}>{r.sem_etiqueta} sem campanha ou pilar</span>
      {Object.entries(r.estados as Record<string, number>).map(([k, v]) => <span key={k} className="selo">{k}: {v}</span>)}
    </div>
    <div className="flex flex-wrap items-center gap-2 mt-3">
      <input value={f.q || ''} onChange={e => setF({ ...f, q: e.target.value })} placeholder="buscar título, gancho, campanha" className="rounded-full bg-black/40 px-3 py-1 text-xs outline-none w-56" />
      <Sel k="campanha" lista={dados.opcoes.campanhas} /><Sel k="pilar" lista={dados.opcoes.pilares} /><Sel k="formato" lista={dados.opcoes.formatos} rot={rotulo} /><Sel k="voz" lista={dados.opcoes.vozes} rot={rotulo} /><Sel k="origem" lista={dados.opcoes.origens} rot={rotulo} /><Sel k="estado" lista={ESTADOS} />
      {Object.values(f).some(Boolean) && <button onClick={() => setF({})} className="text-xs text-nevoa hover:text-white">limpar filtros</button>}
    </div>
    <div className="overflow-x-auto mt-4"><table className="w-full text-xs">
      <thead><tr className="text-nevoa text-left border-b border-white/10"><th className="py-2 pr-2">Peça</th><th className="py-2 pr-2">Etiquetas</th><th className="py-2 pr-2">Estado</th><th className="py-2 pr-2 text-right">Views</th><th className="py-2 pr-2 text-right">× mediana</th><th className="py-2">Medido</th></tr></thead>
      <tbody>{dados.itens.map(p => <tr key={p.slug} className="border-b border-white/5 hover:bg-white/5 cursor-pointer" onClick={() => nav(`/pecas/${p.slug}`)}>
        <td className="py-2 pr-2 max-w-[22rem]"><div className="truncate font-bold">{p.alertas ? <span title={`${p.alertas} alerta(s) de licença de ativo`} className="text-laranja mr-1">⚠</span> : null}{p.titulo}</div><div className="text-nevoa">{p.codigo || ''} · {p.modificado.replace('T', ' ')}{p.pasta ? ` · ${p.pasta}` : ''}</div></td>
        <td className="py-2 pr-2"><ChipsEtiquetas e={p.etiquetas} /></td>
        <td className="py-2 pr-2"><span className={`rounded-full px-2 py-0.5 text-[11px] ${p.estado === 'postado ou agendado' ? 'bg-green-500/20 text-green-300' : p.estado === 'no Drive' ? 'bg-azul/30 text-white' : 'bg-white/10 text-nevoa'}`}>{p.estado}</span></td>
        <td className="py-2 pr-2 text-right">{p.views != null ? p.views.toLocaleString('pt-BR') : <span className="text-nevoa">—</span>}</td>
        <td className={`py-2 pr-2 text-right ${p.vs_mediana != null ? (p.vs_mediana >= 1.5 ? 'text-green-300' : p.vs_mediana <= 0.6 ? 'text-red-300' : '') : 'text-nevoa'}`}>{p.vs_mediana != null ? `${p.vs_mediana.toFixed(2)}×` : '—'}</td>
        <td className="py-2 text-nevoa">{p.medido_em ? `${p.plataforma} · ${p.medido_em.slice(0, 10)}` : ''}</td>
      </tr>)}</tbody></table></div>
    {dados.itens.length === 0 && <div className="text-nevoa mt-4 text-sm">Nenhuma peça com esses filtros.</div>}
    <p className="text-nevoa text-[11px] mt-4">× mediana = views da peça divididas pela mediana do formato nos últimos 90 dias (performance-snapshot do GSI). Verde ≥ 1,5; vermelho ≤ 0,6. Não é tempo real: a medição vem do pulso do GSI.</p>
  </div>
}

export function PecaFichaPagina() {
  const { slug = '' } = useParams(); const [f, setF] = useState<PecaFicha | null>(null); const [erro, setErro] = useState('')
  const carregar = () => api.peca(slug).then(setF).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [slug])
  if (erro) return <div className="max-w-4xl mx-auto px-4 py-8 text-red-300">{erro}</div>
  if (!f) return <div className="max-w-4xl mx-auto px-4 py-8 text-nevoa">…</div>
  const videos = f.arquivos.filter(a => a.tipo === 'video'); const imagens = f.arquivos.filter(a => a.tipo === 'imagem')
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><Link to="/pecas" className="text-nevoa text-sm hover:text-white">← Peças</Link><h2 className="text-xl truncate">{f.conversa.titulo || f.slug}</h2>{f.conversa.codigo && <span className="selo">{f.conversa.codigo}</span>}<span className={`rounded-full px-2 py-0.5 text-[11px] ${f.estado === 'postado ou agendado' ? 'bg-green-500/20 text-green-300' : 'bg-white/10 text-nevoa'}`}>{f.estado}</span>{f.conversa.id && <Link to={`/c/${f.conversa.id}`} className="ml-auto text-xs text-laranja hover:underline">abrir conversa</Link>}</div>
    <p className="text-nevoa text-xs mt-1">Ficha única da peça: tudo o que ela é, onde foi e como foi, num lugar só. Etiquetas inferidas podem ser corrigidas aqui.</p>
    <div className="cartao p-4 mt-4"><div className="font-bold text-sm mb-2">Etiquetas</div><FormEtiquetas slug={f.slug} inicial={f} onSalvo={() => carregar()} /></div>
    <div className="grid md:grid-cols-2 gap-4 mt-4 text-sm">
      <div className="cartao p-4"><div className="font-bold">Métricas (GSI)</div>
        {f.metricas.length === 0 ? <div className="text-nevoa text-xs mt-1">{f.ids_publicados.length ? 'Publicada, mas o GSI ainda não casou com um post.' : 'Ainda não publicada por aqui: sem métrica para ligar.'}</div>
          : f.metricas.map((m, i) => <div key={i} className="mt-2 text-xs">{m.views == null ? <span className="text-nevoa">{m.platform} {m.item_id}: {m.aviso}</span> : <>
            <div className="flex flex-wrap gap-3"><span className="font-bold">{m.platform}</span><span>{m.views.toLocaleString('pt-BR')} views</span><span>{m.likes} likes</span><span>{m.comments} com.</span><span className={m.ratio_vs_format_median >= 1.5 ? 'text-green-300' : m.ratio_vs_format_median <= 0.6 ? 'text-red-300' : ''}>{m.ratio_vs_format_median != null ? `${Number(m.ratio_vs_format_median).toFixed(2)}× a mediana do formato ${m.format || ''}` : ''}</span></div>
            <div className="text-nevoa">medido em {String(m.computed_at).slice(0, 16).replace('T', ' ')}{m.age_days != null ? ` · ${Math.round(m.age_days)} dias de vida` : ''}{m.theme ? ` · tema ${m.theme}` : ''}</div></>}</div>)}
        {f.publicacoes.length > 0 && <div className="mt-3 text-xs"><div className="text-nevoa">Publicações registradas</div>{f.publicacoes.map((p: any, i: number) => <div key={i}>{p.tipo} · {String(p.quando || '').replace('T', ' ')}{p.posts?.[0]?.permalink ? <> · <a href={p.posts[0].permalink} target="_blank" className="text-laranja hover:underline">link</a></> : ''}</div>)}</div>}
      </div>
      <div className="cartao p-4"><div className="font-bold">Arquivos</div>
        <div className="grid grid-cols-2 gap-2 mt-2">{videos.slice(0, 2).map(v => <video key={v.caminho} src={v.url} preload="metadata" controls className="w-full rounded-lg bg-black" />)}{imagens.slice(0, 2).map(i => <img key={i.caminho} src={i.url} className="w-full rounded-lg" />)}</div>
        <div className="flex flex-wrap gap-2 mt-2 text-xs">{f.arquivos.map(a => <a key={a.caminho} href={a.url} download className="selo">{a.nome}</a>)}</div>
      </div>
    </div>
    <div className="cartao p-4 mt-4 text-sm"><div className="flex items-center gap-2 flex-wrap"><div className="font-bold">Ativos e licenças</div>{(f.alertas || []).length > 0 && <span className="rounded-full px-2 py-0.5 text-[11px] bg-laranja/20 text-laranja">⚠ {f.alertas.length} alerta{f.alertas.length > 1 ? 's' : ''}</span>}</div>
      {(f.alertas || []).map((a, i) => <div key={i} className="mt-2 text-xs text-laranja">⚠ {a.msg}</div>)}
      {(f.ativos || []).length === 0 ? <div className="text-nevoa text-xs mt-1">Nenhum material de banco ou trilha registrado nesta peça (só o que a entrega cita: banco/… e trilhas/…).</div>
        : <div className="grid gap-1 mt-2 text-xs">{f.ativos.map(a => <div key={a.arquivo} className="flex items-center gap-2 flex-wrap rounded-lg bg-black/30 px-2 py-1">
          <span className={a.licenca === 'nc' || (a.licenca === 'cc-by' && !a.atribuicao) || a.licenca === 'desconhecida' ? 'text-laranja' : 'text-green-300'}>{a.licenca === 'nc' || (a.licenca === 'cc-by' && !a.atribuicao) || a.licenca === 'desconhecida' ? '⚠' : '✓'}</span>
          <span className="font-medium truncate max-w-[18rem]" title={a.arquivo}>{a.arquivo.split('/').pop()}</span>
          <span className="rounded-full px-2 py-0.5 bg-white/10 text-nevoa">{a.licenca}</span>
          <span className="text-nevoa">{a.origem}{a.atribuicao ? ` · crédito: ${a.atribuicao}` : ''}</span>
          {a.url && <a href={a.url} target="_blank" rel="noreferrer" className="text-laranja hover:underline">origem ↗</a>}
        </div>)}</div>}
      <div className="text-nevoa text-[11px] mt-2">Licenças: proprio, cc0, pexels, pixabay, cc-by (precisa de crédito), nc (só não comercial: não usar), desconhecida. Fonte: o .licenca.json que o motor grava ao baixar do banco e a tabela de trilhas/README.md.</div>
    </div>
    {Object.keys(f.textos).length > 0 && <div className="cartao p-4 mt-4 text-sm"><div className="font-bold">Textos da entrega</div>
      {(['gancho', 'titulo', 'descricao', 'hashtags', 'roteiro', 'gravar', 'resumo', 'pendencias'] as const).filter(k => f.textos[k]).map(k => <details key={k} className="mt-2" open={k === 'gancho' || k === 'descricao'}><summary className="cursor-pointer text-xs text-laranja uppercase tracking-wide">{k}</summary><pre className="whitespace-pre-wrap text-xs text-white/90 mt-1 font-sans">{f.textos[k]}</pre></details>)}</div>}
  </div>
}
