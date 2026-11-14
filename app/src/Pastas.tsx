import { useEffect, useState } from 'react'
import { api, type Pasta } from './api'

export function usePastas() {
  const [pastas, setPastas] = useState<Pasta[]>([])
  const carregar = () => api.pastas().then(r => setPastas(r.pastas)).catch(() => {})
  useEffect(() => { carregar() }, [])
  return { pastas, carregar }
}

export async function pedirNovaPasta(): Promise<string | null> {
  const n = prompt('Nome da nova pasta (campanha, semana, cliente…):')
  if (!n?.trim()) return null
  try { const r = await api.novaPasta(n); return r.nome } catch (e: any) { alert(e.message); return null }
}

export function SeletorPasta({ valor, onChange, className = '' }: { valor: string; onChange: (p: string) => void; className?: string }) {
  const { pastas, carregar } = usePastas()
  async function mudar(v: string) {
    if (v === '__nova') { const n = await pedirNovaPasta(); if (n) { await carregar(); onChange(n) } return }
    onChange(v)
  }
  const opcoes = pastas.map(p => p.nome); if (valor && !opcoes.includes(valor)) opcoes.unshift(valor)
  return <select value={valor} onChange={e => mudar(e.target.value)} title="Pasta (projeto) deste pedido" className={`rounded-full border border-white/15 bg-card px-3 py-1.5 text-sm ${className}`}>
    <option value="">📁 Sem pasta</option>{opcoes.map(p => <option key={p} value={p}>📁 {p}</option>)}<option value="__nova">+ Nova pasta…</option>
  </select>
}
