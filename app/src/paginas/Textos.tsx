import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type TextoGuardado, type TextoItem } from '../api'
import { Md, copiar } from '../Md'
import { usePastas } from '../Pastas'

const quando = (s: string) => s ? new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''

/** Textos entregues pelo Editor (roteiro, legenda do post, análise, respostas, transcrição): vêm da mensagem final de cada conversa,
 *  não de arquivos. "Guardar como referência" é o único jeito de um texto virar .md (referencias/_textos/), por pedido do Raphael. */
export default function Textos() {
  const [d, setD] = useState<{ itens: TextoItem[]; tipos: { chave: string; rotulo: string }[] } | null>(null)
  const [q, setQ] = useState(''); const [tipo, setTipo] = useState(''); const [pasta, setPasta] = useState('')
  const [aba, setAba] = useState<'entregues' | 'guardados'>('entregues')
  const [guardados, setGuardados] = useState<TextoGuardado[]>([])
  const [aberto, setAberto] = useState<string | null>(null)
  const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState('')
  const { pastas } = usePastas()
  const carregar = () => api.textos(q, tipo, pasta).then(setD).catch(e => setErro(e.message))
  useEffect(() => { const t = setTimeout(carregar, q ? 350 : 0); return () => clearTimeout(t) }, [q, tipo, pasta])
  useEffect(() => { api.textosGuardados().then(setGuardados).catch(() => {}) }, [aba])
  async function guardar(it: TextoItem, chave: string) {
    setOcupado(it.id + chave); setErro('')
    try { await api.guardarTexto(it.id, chave); await carregar(); setGuardados(await api.textosGuardados()) } catch (e: any) { setErro(e.message) } finally { setOcupado('') }
  }
  async function apagar(nome: string) {
    if (!confirm(`Apagar “${nome}” das referências? O texto continua na conversa.`)) return
    try { await api.apagarTextoGuardado(nome); setGuardados(await api.textosGuardados()); await carregar() } catch (e: any) { setErro(e.message) }
  }
  const chip = (ativo: boolean) => `rounded-full px-3 py-1 text-xs border ${ativo ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 text-nevoa hover:bg-white/5'}`
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Textos</h2>
      <div className="ml-auto flex gap-2">{(['entregues', 'guardados'] as const).map(a => <button key={a} onClick={() => setAba(a)} className={chip(aba === a)}>{a === 'entregues' ? `Entregues${d ? ` · ${d.itens.length}` : ''}` : `Guardados como referência · ${guardados.length}`}</button>)}</div></div>
    <p className="text-nevoa mt-2 text-sm">Roteiros, legendas de post, análises, respostas e transcrições que o Editor entregou, direto da mensagem de cada conversa (nada fica em arquivo). Copie daqui ou abra a conversa. Gostou de um texto? <b className="text-white">Guardar como referência</b> grava um .md em <code className="bg-white/10 rounded px-1">referencias/_textos/</code>, que o Editor passa a usar como exemplo de voz e estrutura.</p>
    {erro && <div className="mt-3 text-xs text-red-300">{erro}</div>}

    {aba === 'entregues' && <>
      <div className="flex flex-wrap items-center gap-2 mt-5">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="🔍 Buscar nos textos" className="rounded-full bg-black/30 px-4 py-1.5 text-sm outline-none placeholder:text-nevoa flex-1 min-w-[180px]" />
        <select value={pasta} onChange={e => setPasta(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm"><option value="">📁 Todas as pastas</option>{pastas.map(p => <option key={p.nome} value={p.nome}>📁 {p.nome}</option>)}</select>
      </div>
      <div className="flex flex-wrap gap-2 mt-3"><button onClick={() => setTipo('')} className={chip(tipo === '')}>Tudo</button>{(d?.tipos || []).map(t => <button key={t.chave} onClick={() => setTipo(tipo === t.chave ? '' : t.chave)} className={chip(tipo === t.chave)}>{t.rotulo}</button>)}</div>
      <div className="grid gap-3 mt-5">
        {!d && <div className="text-nevoa text-sm">Carregando…</div>}
        {d && d.itens.length === 0 && <div className="cartao p-4 text-sm text-nevoa">Nenhum texto ainda{q || tipo || pasta ? ' com esse filtro' : ''}. As próximas entregas do Editor já vêm com as seções Resumo, Legenda do post, Roteiro etc. na mensagem final; as antigas ficaram em post.md/relatorio.md e aparecem só na conversa.</div>}
        {d?.itens.map(it => <div key={it.id} className="cartao p-4">
          <div className="flex items-center gap-2 flex-wrap text-sm"><span className="selo">{it.codigo}</span><Link to={`/c/${it.id}`} className="font-bold hover:text-laranja truncate">{it.titulo}</Link>
            <span className="text-xs text-nevoa ml-auto">{quando(it.quando)}{it.pasta ? ` · 📁 ${it.pasta}` : ''}</span></div>
          <div className="grid gap-2 mt-3">{it.secoes.map(s => { const ja = it.guardadas.includes(s.chave); const curto = s.conteudo.length < 700 || aberto === it.id + s.chave
            return <div key={s.chave} className="rounded-xl bg-black/30 p-3">
              <div className="flex items-center gap-2 mb-1 flex-wrap"><span className="text-[11px] uppercase tracking-wide text-laranja">{s.titulo}</span>
                <button onClick={() => copiar(s.conteudo)} className="ml-auto text-xs rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">Copiar</button>
                <button onClick={() => !ja && guardar(it, s.chave)} disabled={ocupado === it.id + s.chave} className={`text-xs rounded-full border px-2 py-0.5 ${ja ? 'border-green-400/40 text-green-300' : 'border-white/15 hover:bg-white/5'}`}>{ja ? 'Guardado ✓' : ocupado === it.id + s.chave ? 'Guardando…' : 'Guardar como referência'}</button></div>
              <Md texto={curto ? s.conteudo : s.conteudo.slice(0, 700) + '…'} className="text-sm" />
              {!curto && <button onClick={() => setAberto(it.id + s.chave)} className="text-xs text-laranja mt-1">Ler tudo</button>}
            </div> })}</div>
        </div>)}
      </div>
    </>}

    {aba === 'guardados' && <div className="grid gap-3 mt-5">
      {guardados.length === 0 && <div className="cartao p-4 text-sm text-nevoa">Nenhum texto guardado. Use “Guardar como referência” numa entrega (aqui ou na conversa).</div>}
      {guardados.map(g => <details key={g.nome} className="cartao p-4"><summary className="cursor-pointer flex items-center gap-2 flex-wrap text-sm"><span className="font-bold">{g.titulo}</span>{g.codigo && <span className="selo">{g.codigo}</span>}<span className="text-xs text-nevoa ml-auto">{quando(g.quando)}</span></summary>
        <div className="mt-3"><Md texto={g.conteudo.split('\n').slice(1).join('\n')} className="text-sm" /></div>
        <div className="mt-3 flex gap-2 text-xs"><button onClick={() => copiar(g.conteudo)} className="rounded-full border border-white/15 px-3 py-1 hover:bg-white/5">Copiar</button><button onClick={() => apagar(g.nome)} className="rounded-full border border-white/15 px-3 py-1 hover:text-red-300">Apagar das referências</button><span className="text-nevoa self-center">referencias/_textos/{g.nome}</span></div>
      </details>)}
    </div>}
  </div>
}
