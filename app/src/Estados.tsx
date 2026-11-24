import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Icone } from './Icones'

// Estados de carregamento, vazio e erro (design fase 2, 17/11/2026): um componente só para todas as páginas, no lugar de "Carregando…" e "…" soltos.

/** Esqueleto que imita a página: grade de cartões (com prévia), lista de linhas ou um bloco. */
export function Esqueleto({ tipo = 'cartoes', n = 6, className = '' }: { tipo?: 'cartoes' | 'lista' | 'faixa' | 'bloco'; n?: number; className?: string }) {
  const b = 'rounded-xl bg-white/[.06] animate-pulse'
  if (tipo === 'bloco') return <div aria-busy className={`cartao p-4 ${className}`}><div className={`${b} h-4 w-1/3`} /><div className={`${b} mt-3 h-3 w-2/3`} /><div className={`${b} mt-2 h-3 w-1/2`} /></div>
  if (tipo === 'lista') return <div aria-busy className={`grid gap-2 ${className}`}>{Array.from({ length: n }, (_, i) => <div key={i} className="cartao flex items-center gap-3 p-3"><div className={`${b} h-10 w-10 shrink-0`} /><div className="flex-1"><div className={`${b} h-3.5`} style={{ width: `${70 - (i % 3) * 12}%` }} /><div className={`${b} mt-2 h-2.5 w-1/3`} /></div></div>)}</div>
  const cartao = (i: number) => <div key={i} className="cartao overflow-hidden"><div className={`${b} aspect-[4/5] rounded-none`} /><div className="p-3"><div className={`${b} h-3.5`} style={{ width: `${80 - (i % 3) * 15}%` }} /><div className={`${b} mt-2 h-2.5 w-1/2`} /><div className={`${b} mt-3 h-7 w-24 rounded-full`} /></div></div>
  if (tipo === 'faixa') return <div aria-busy className={`-mx-4 flex gap-3 overflow-hidden px-4 ${className}`}>{Array.from({ length: n }, (_, i) => <div key={i} className="w-56 shrink-0">{cartao(i)}</div>)}</div>
  return <div aria-busy className={`grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 ${className}`}>{Array.from({ length: n }, (_, i) => cartao(i))}</div>
}

type Acao = { rotulo: string; to?: string; onClick?: () => void }
/** Vazio com motivo e próximo passo (nunca só "Nada aqui"). */
export function Vazio({ icone = 'biblioteca', titulo, texto, acao, className = '' }: { icone?: string; titulo: string; texto?: ReactNode; acao?: Acao; className?: string }) {
  const btn = 'btn-laranja mt-4 inline-flex px-4 py-1.5 text-sm'
  return <div className={`flex flex-col items-center rounded-[20px] border border-dashed border-white/10 px-6 py-10 text-center ${className}`}>
    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-laranja/10 text-laranja"><Icone nome={icone} className="h-6 w-6" /></div>
    <div className="mt-3 font-[Unbounded] text-[15px]">{titulo}</div>
    {texto && <div className="mt-1 max-w-md text-sm text-nevoa">{texto}</div>}
    {acao && (acao.to ? <Link to={acao.to} className={btn}>{acao.rotulo}</Link> : <button onClick={acao.onClick} className={btn}>{acao.rotulo}</button>)}
  </div>
}

/** Erro de carga com "Tentar de novo". */
export function ErroCarga({ erro, onTentar, className = '' }: { erro: string; onTentar?: () => void; className?: string }) {
  return <div role="alert" className={`flex flex-wrap items-center gap-3 rounded-[20px] border border-red-400/30 bg-red-400/5 px-4 py-3 text-sm ${className}`}>
    <span className="text-red-300"><Icone nome="alerta" /></span>
    <div className="min-w-0 flex-1"><div className="text-red-200">Não deu para carregar.</div><div className="truncate text-xs text-nevoa" title={erro}>{erro.slice(0, 300)}</div></div>
    {onTentar && <button onClick={onTentar} className="inline-flex items-center gap-1.5 rounded-full border border-white/15 px-3 py-1.5 text-xs hover:bg-white/5"><Icone nome="recarregar" className="h-4 w-4" />Tentar de novo</button>}
  </div>
}

/** Junta os três: erro → ErroCarga; sem dados → esqueleto; vazio → Vazio; senão os filhos. */
export function Carga({ carregando, erro, vazio, onTentar, esqueleto, semDados, children }: { carregando: boolean; erro?: string; vazio?: { icone?: string; titulo: string; texto?: ReactNode; acao?: Acao } | null; onTentar?: () => void; esqueleto?: ReactNode; semDados?: boolean; children?: ReactNode }) {
  if (erro && (semDados ?? true)) return <ErroCarga erro={erro} onTentar={onTentar} className="mt-4" />
  if (carregando && (semDados ?? true)) return <>{esqueleto ?? <Esqueleto className="mt-4" />}</>
  return <>{erro && <ErroCarga erro={erro} onTentar={onTentar} className="mt-4" />}{vazio ? <Vazio {...vazio} className="mt-4" /> : children}</>
}

/** Carga de uma rota: dados, erro, carregando e recarregar (recarregar mantém os dados na tela e só troca se vier resposta). */
export function useCarga<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [dados, setDados] = useState<T | null>(null); const [erro, setErro] = useState(''); const [carregando, setCarregando] = useState(true)
  const fnRef = useRef(fn); fnRef.current = fn
  const vez = useRef(0)
  const recarregar = useCallback(() => {
    const n = ++vez.current; setCarregando(true); setErro('')
    return fnRef.current().then(d => { if (n === vez.current) setDados(d) }).catch(e => { if (n === vez.current) setErro(String(e?.message || e)) }).finally(() => { if (n === vez.current) setCarregando(false) })
  }, [])
  useEffect(() => { recarregar() }, deps)  // eslint-disable-line react-hooks/exhaustive-deps
  return { dados, setDados, erro, carregando, recarregar }
}

/** "há 5 min", "há 3 h", "ontem", "há 4 dias". */
export function ha(iso?: string | null) {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (!isFinite(s)) return ''
  if (s < 60) return 'agora'
  if (s < 3600) return `há ${Math.round(s / 60)} min`
  if (s < 86400) return `há ${Math.round(s / 3600)} h`
  const d = Math.floor(s / 86400); return d === 1 ? 'ontem' : d < 30 ? `há ${d} dias` : new Date(iso).toLocaleDateString('pt-BR')
}
