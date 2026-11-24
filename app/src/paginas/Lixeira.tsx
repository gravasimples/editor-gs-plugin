import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Conversa } from '../api'

export default function Lixeira() {
  const [itens, setItens] = useState<Conversa[] | null>(null)
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState('')
  const carregar = () => api.lixeira().then(setItens).catch(e => setErro(e.message))
  useEffect(() => { carregar() }, [])
  async function restaurar(c: Conversa) { setOcupado(c.id); try { await api.restaurar(c.id); await carregar() } catch (e: any) { setErro(e.message) } finally { setOcupado('') } }
  const quando = (s?: string | null) => s ? new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <h1 className="text-2xl">🗑 Lixeira</h1>
    <p className="text-nevoa text-sm mt-2">Conversas excluídas ou canceladas. Os arquivos entregues continuam guardados; Restaurar devolve a conversa à lista (se estava na fila ou editando, volta pausada e o ▶ Retomar continua).</p>
    {erro && <div className="text-red-300 text-sm mt-3">{erro}</div>}
    <div className="grid gap-2 mt-5">
      {itens === null && <div className="text-nevoa text-sm">Carregando…</div>}
      {itens?.length === 0 && <div className="text-nevoa text-sm">A Lixeira está vazia.</div>}
      {itens?.map(c => <div key={c.id} className="cartao px-4 py-3 flex items-center gap-3">
        <div className="min-w-0"><Link to={`/c/${c.id}`} className="truncate block hover:text-laranja">{c.titulo}</Link>
          <div className="text-[11px] text-nevoa">{c.codigo} · {c.excluida ? `excluída em ${quando(c.excluida)}` : `cancelada · ${quando(c.atualizado)}`}{c.pasta ? ` · 📁 ${c.pasta}` : ''}</div></div>
        <button onClick={() => restaurar(c)} disabled={!!ocupado} className="ml-auto rounded-full border border-laranja/60 text-laranja px-3 py-1 text-xs hover:bg-laranja/10 disabled:opacity-40 whitespace-nowrap">{ocupado === c.id ? 'Restaurando…' : '♻ Restaurar'}</button>
      </div>)}
    </div>
  </div>
}
