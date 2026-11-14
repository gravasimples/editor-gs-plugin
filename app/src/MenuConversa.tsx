import { useRef, useState } from 'react'
import { api, type Conversa, type Pasta } from './api'
import { pedirNovaPasta } from './Pastas'

/** Menu ⋯ de uma conversa (como no Máquina): mover para pasta (projeto), marcar como concluída e excluir (vai para a Lixeira, dá para restaurar). */
export function MenuConversa({ c, onMudou, onExcluida, className = '' }: { c: Pick<Conversa, 'id' | 'titulo' | 'status' | 'pasta'>; onMudou?: () => void; onExcluida?: () => void; className?: string }) {
  const [aberto, setAberto] = useState(false)
  const [pos, setPos] = useState<React.CSSProperties>({})
  const botao = useRef<HTMLButtonElement>(null)
  function abrir() {  // fixed pela posição do botão: as listas da barra lateral e do celular têm rolagem e cortariam um menu absoluto
    const r = botao.current?.getBoundingClientRect(); if (r) { const larg = 240, cima = r.bottom > window.innerHeight - 280; setPos({ left: Math.max(8, Math.min(r.right - larg, window.innerWidth - larg - 8)), ...(cima ? { bottom: window.innerHeight - r.top + 4 } : { top: r.bottom + 4 }) }) }
    carregar(); setAberto(true)
  }
  const [pastasAberto, setPastasAberto] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [pastas, setPastas] = useState<Pasta[]>([])  // só carrega ao abrir: a barra lateral tem dezenas de menus
  const carregar = () => api.pastas().then(r => setPastas(r.pastas)).catch(() => {})
  const fechar = () => { setAberto(false); setPastasAberto(false) }
  async function fazer(f: () => Promise<any>) { setOcupado(true); try { await f(); onMudou?.() } catch (e: any) { alert(e.message || 'Falhou') } finally { setOcupado(false); fechar() } }
  const mover = (p: string) => fazer(() => api.moverPasta(c.id, p))
  async function novaEMover() { const n = await pedirNovaPasta(); if (n) { await carregar(); await mover(n) } }
  const concluir = () => fazer(() => api.concluir(c.id))
  async function excluir() {
    if (!confirm(`Excluir a conversa “${c.titulo}”?\n\nEla vai para a Lixeira (dá para restaurar). Os arquivos entregues continuam guardados.`)) return
    await fazer(async () => { await api.excluir(c.id); onExcluida?.() })
  }
  const parar = (e: React.MouseEvent) => { e.preventDefault(); e.stopPropagation() }
  return <span className={`inline-block ${className}`} onClick={parar}>
    <button ref={botao} type="button" onClick={() => aberto ? fechar() : abrir()} disabled={ocupado} title="Mais opções" aria-label="Mais opções da conversa" className="rounded-lg px-1.5 py-0.5 text-nevoa hover:text-white hover:bg-white/10 leading-none">{ocupado ? '…' : '⋯'}</button>
    {aberto && <>
      <div className="fixed inset-0 z-40" onClick={fechar} />
      <div style={pos} className="fixed z-50 w-60 rounded-xl border border-white/10 bg-[#0B193D] shadow-xl py-1 text-sm text-white">
        <button onClick={() => setPastasAberto(v => !v)} className="w-full text-left px-3 py-2 hover:bg-white/5 flex items-center">📁 Mover para pasta<span className="ml-auto text-nevoa">{pastasAberto ? '▾' : '›'}</span></button>
        {pastasAberto && <div className="max-h-56 overflow-y-auto border-y border-white/10 bg-black/20 py-1">
          {pastas.map(p => <button key={p.nome} disabled={p.nome === c.pasta} onClick={() => mover(p.nome)} className="w-full text-left pl-7 pr-3 py-1.5 hover:bg-white/5 disabled:text-laranja truncate">{p.nome === c.pasta ? '✓ ' : ''}{p.nome}</button>)}
          {c.pasta && <button onClick={() => mover('')} className="w-full text-left pl-7 pr-3 py-1.5 hover:bg-white/5 text-nevoa">Tirar da pasta</button>}
          <button onClick={novaEMover} className="w-full text-left pl-7 pr-3 py-1.5 hover:bg-white/5 text-laranja">+ Nova pasta…</button>
        </div>}
        {c.status !== 'done' && <button onClick={concluir} className="w-full text-left px-3 py-2 hover:bg-white/5" title="Fecha a conversa sem aprovar a entrega (não mexe no Notion). Se o Editor estiver trabalhando, ele para.">✔ Marcar como concluída</button>}
        <button onClick={excluir} className="w-full text-left px-3 py-2 hover:bg-white/5 text-red-300">🗑 Excluir conversa</button>
      </div>
    </>}
  </span>
}
