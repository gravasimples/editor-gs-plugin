import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type PastaVigiada as D } from './api'

// Pasta vigiada do Drive (03/11/2026): gravação nova vira pedido sozinha. A chave fica na lista "Editor GS" abaixo.
const MODO: Record<string, string> = { kit: 'Kit de derivação', clipador: 'Clipador (propor cortes)', reel: 'Reel', legendar: 'Só legendar' }

export function PastaVigiada() {
  const [d, setD] = useState<D | null>(null); const [ocupado, setOcupado] = useState(false); const [aviso, setAviso] = useState('')
  const carregar = () => api.pastaVigiada().then(setD).catch(e => setAviso(e.message))
  useEffect(() => { carregar() }, [])
  async function rodar() {
    setOcupado(true); setAviso('')
    try {
      const r = await api.pastaVigiadaRodar()
      setAviso(r.erro ? `Drive: ${r.erro}` : r.pedidos?.length ? `Pedido ${r.pedidos.join(', ')} aberto.` : `Nada novo pronto (${r.na_pasta ?? 0} vídeo(s) na pasta; arquivo recém-subido entra na leitura seguinte).`)
      carregar()
    } catch (e: any) { setAviso(e.message) } finally { setOcupado(false) }
  }
  if (!d) return null
  const pasta = d.origem.split(':').slice(1).join(':')
  return <div className="cartao p-3 mt-4">
    <div className="flex flex-wrap items-center gap-2">
      <span className={`inline-block w-2 h-2 rounded-full ${d.ligada ? 'bg-green-400' : 'bg-white/20'}`} />
      <span className="font-bold">Pasta vigiada do Drive</span>
      <span className="text-xs text-nevoa flex-1 min-w-[14rem]">Solte a gravação na pasta e ela vira pedido sozinha. Ligue na lista "Editor GS" abaixo; "Ler agora" funciona mesmo desligada.</span>
      {d.lido_em && <span className="text-xs text-nevoa">lida: {d.lido_em.replace('T', ' ').slice(0, 16)}</span>}
      <button onClick={rodar} disabled={ocupado} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 text-xs hover:bg-laranja/10 disabled:opacity-40">{ocupado ? '…' : 'Ler agora'}</button>
    </div>
    <div className="text-xs mt-2"><span className="text-nevoa">Pasta:</span> <span className="font-mono">{pasta}</span>{d.n_arquivos != null && <span className="text-nevoa"> · {d.n_arquivos} vídeo(s)</span>}{d.ja_estavam > 0 && <span className="text-nevoa"> · {d.ja_estavam} já estavam lá antes (ignorados)</span>}</div>
    {d.erro && <div className="text-xs text-red-300 mt-1">{/not found|directory not found/i.test(d.erro) ? 'A pasta ainda não existe no Drive. Crie "Materiais para Editar" dentro de 10. Mídias.' : d.erro}</div>}
    <div className="text-xs text-nevoa mt-2">Subpastas escolhem o tipo: <b>Kit</b> → kit de derivação · <b>Cortes</b> ou <b>Live</b> → Clipador · <b>Profissional</b>, <b>Lista</b>, <b>Tutorial</b>, <b>Bastidor</b>, <b>POV</b>, <b>Opinião</b> → Reel nesse estilo · <b>Legendar</b> → só legenda · solto na pasta → Reel padrão (acima de 8 min vai para o Clipador). Um .txt com o mesmo nome do vídeo vira a instrução do pedido. O app só lê o Drive: não move nem apaga nada.</div>
    {d.itens.length > 0 && <div className="grid gap-1 mt-3">{d.itens.slice(0, 10).map(i => <div key={i.chave} className="flex flex-wrap gap-2 text-xs">
      <span className="truncate flex-1">{i.caminho}</span>
      <span className="text-nevoa">{i.estado === 'pedido' ? `${MODO[i.modo || ''] || i.modo}${i.estilo && i.modo === 'reel' ? ` · ${i.estilo}` : ''}` : i.estado === 'erro' ? `erro: ${i.erro}` : i.estado}</span>
      {i.conversa && <Link to={`/c/${i.conversa}`} className="text-laranja hover:underline">{i.codigo || 'abrir'}</Link>}
    </div>)}</div>}
    {aviso && <div className="text-xs text-green-300 mt-2">{aviso}</div>}
  </div>
}
