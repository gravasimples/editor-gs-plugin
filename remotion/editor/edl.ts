// Editor manual fase 2 (12/11/2026): EDL editável. A EDL é a lista de trechos do bruto que ficam, na ordem do vídeo (podem estar fora da ordem
// do bruto). As props da Montagem ficam no tempo do vídeo cortado; quando a EDL muda, tudo que tem tempo é levado do tempo velho para o novo
// passando pelo bruto: o que caiu num trecho apagado/aparado some, o que vem depois se desloca. Planos da câmera seguem o trecho a que pertencem.
import type { MontagemProps, Plano } from '../src/tipos'

export type Trecho = { id: number; inicio: number; fim: number }
const r3 = (x: number) => Math.round(x * 1000) / 1000
export const durTrecho = (m: Trecho) => m.fim - m.inicio
export const totalEdl = (ms: Trecho[]) => ms.reduce((a, m) => a + durTrecho(m), 0)
export function offsets(ms: Trecho[]): number[] { const o: number[] = []; let acc = 0; for (const m of ms) { o.push(acc); acc += durTrecho(m) } return o }
export const mesmaEdl = (a: Trecho[] | null | undefined, b: Trecho[] | null | undefined) =>
  !!a && !!b && a.length === b.length && a.every((x, i) => x.id === b[i].id && Math.abs(x.inicio - b[i].inicio) < 1e-3 && Math.abs(x.fim - b[i].fim) < 1e-3)

/** tempo do vídeo cortado (EDL velha) → {id do trecho, tempo no bruto}; `fimInclusivo` = um fim de intervalo exatamente no corte fica no trecho da esquerda */
function paraBruto(t: number, ms: Trecho[], fimInclusivo = false): { id: number; r: number } | null {
  const off = offsets(ms)
  for (let k = 0; k < ms.length; k++) {
    const a = off[k], z = a + durTrecho(ms[k])
    if ((t >= a && t < z) || (fimInclusivo && t > a && t <= z + 1e-6) || (k === ms.length - 1 && Math.abs(t - z) < 1e-6)) return { id: ms[k].id, r: ms[k].inicio + (t - a) }
  }
  return null
}
function doBruto(b: { id: number; r: number }, ms: Trecho[]): number | null {
  const off = offsets(ms); const k = ms.findIndex(m => m.id === b.id)
  if (k < 0) return null
  const m = ms[k]; if (b.r < m.inicio - 1e-6 || b.r > m.fim + 1e-6) return null
  return r3(off[k] + Math.min(Math.max(b.r, m.inicio), m.fim) - m.inicio)
}
export function mapaPonto(t: number, velha: Trecho[], nova: Trecho[]): number | null {
  const b = paraBruto(t, velha); return b ? doBruto(b, nova) : null
}
/** intervalo [a,b] do tempo velho → pedaços que sobrevivem na EDL nova; devolve início do 1º pedaço e a duração somada (ou null) */
export function mapaIntervalo(a: number, b: number, velha: Trecho[], nova: Trecho[]): { inicio: number; fim: number } | null {
  const off = offsets(velha); let ini: number | null = null; let dur = 0
  for (let k = 0; k < velha.length; k++) {
    const sa = off[k], sz = sa + durTrecho(velha[k]); const x = Math.max(a, sa), y = Math.min(b, sz)
    if (y - x <= 1e-6) continue
    const m = velha[k]; const n = nova.find(q => q.id === m.id); if (!n) continue
    const ra = Math.max(m.inicio + (x - sa), n.inicio), rz = Math.min(m.inicio + (y - sa), n.fim)
    if (rz - ra <= 1e-6) continue
    const p = doBruto({ id: m.id, r: ra }, nova)!
    if (ini === null) ini = p
    dur += rz - ra
  }
  if (ini === null) return null
  return { inicio: r3(ini), fim: r3(ini + dur) }
}

function planosNovos(planos: Plano[], velha: Trecho[], nova: Trecho[]): Plano[] {
  const offV = offsets(velha), offN = offsets(nova); const out: Plano[] = []
  nova.forEach((n, kn) => {
    const kv = velha.findIndex(m => m.id === n.id); if (kv < 0) return
    const m = velha[kv]; const sa = offV[kv], sz = sa + durTrecho(m); const meus: Plano[] = []
    for (const p of planos) {
      const x = Math.max(p.inicio, sa), y = Math.min(p.fim, sz); if (y - x <= 1e-6) continue
      const ra = Math.max(m.inicio + (x - sa), n.inicio), rz = Math.min(m.inicio + (y - sa), n.fim); if (rz - ra <= 1e-6) continue
      meus.push({ ...p, inicio: r3(offN[kn] + ra - n.inicio), fim: r3(offN[kn] + rz - n.inicio) })
    }
    const fimN = r3(offN[kn] + durTrecho(n))
    if (!meus.length) {  // trecho sem plano (não acontece com o motor): herda o plano mais próximo
      const base = planos[Math.min(planos.length - 1, kn)] || { z0: 1, z1: 1, entrada: 'seco', dur: 0 } as Plano
      meus.push({ ...base, inicio: r3(offN[kn]), fim: fimN })
    }
    meus[0].inicio = r3(offN[kn]); meus[meus.length - 1].fim = fimN   // a sobra do bruto puxada para dentro fica no plano da borda
    out.push(...meus)
  })
  return out
}

/** Leva as props do tempo da EDL `velha` para o da `nova`. Não mexe em vídeo/legenda: isso o servidor refaz no render (e a prévia pede ao servidor). */
export function remapearProps(p0: MontagemProps, velha: Trecho[], nova: Trecho[]): MontagemProps {
  const p: MontagemProps = JSON.parse(JSON.stringify(p0))
  const ponto = (t: number) => mapaPonto(t, velha, nova)
  const iv = (a: number, b: number) => mapaIntervalo(a, b, velha, nova)
  p.duracao_s = r3(totalEdl(nova))
  if (p.grafismos) p.grafismos = p.grafismos.flatMap(g => {
    const n = iv(g.inicio, g.fim); if (!n) return []
    const d = { ...g, inicio: n.inicio, fim: Math.max(n.fim, r3(n.inicio + 0.3)) }
    if (g.troca_em !== undefined) { const q = ponto(g.troca_em); if (q === null) delete d.troca_em; else d.troca_em = q }
    return [d]
  })
  if (p.sfx) p.sfx = p.sfx.flatMap(s => { const q = ponto(s.inicio); return q === null ? [] : [{ ...s, inicio: q }] }).sort((a, b) => a.inicio - b.inicio)
  if (p.palavras_chave) p.palavras_chave = p.palavras_chave.flatMap(k => { const n = iv(k.inicio, k.fim); return n ? [{ ...k, ...n }] : [] })
  if (p.capitulos) p.capitulos = p.capitulos.flatMap(c => { const q = ponto(c.inicio); return q === null ? [] : [{ ...c, inicio: q }] })
  if (p.broll) p.broll = p.broll.flatMap(b => { const n = iv(b.inicio, b.inicio + b.duracao_s); return n ? [{ ...b, inicio: n.inicio, duracao_s: r3(n.fim - n.inicio) }] : [] })
  if (p.segmentos) p.segmentos = p.segmentos.flatMap(s => { const n = iv(s.inicio, s.fim); return n ? [{ ...s, ...n }] : [] }).sort((a, b) => a.inicio - b.inicio)
  if (p.terco) { const q = ponto(p.terco.inicio_s); if (q === null) p.terco = null; else p.terco.inicio_s = q }
  if (p.camera?.planos?.length) p.camera.planos = planosNovos(p.camera.planos, velha, nova)
  if (!p.camera && p.cortes_s) p.cortes_s = offsets(nova).slice(1).map(r3)
  if (p.legenda_cinetica) p.legenda_cinetica = {
    ...p.legenda_cinetica, linhas: p.legenda_cinetica.linhas.flatMap(l => {
      const ws = l.palavras.flatMap(w => { const n = iv(w.inicio, w.fim); return n ? [{ ...w, ...n }] : [] }); if (!ws.length) return []
      return [{ inicio: ws[0].inicio, fim: Math.max(ws[ws.length - 1].fim, ws[0].inicio + 0.05), palavras: ws }]
    })
  }
  return p
}

/** limites para aparar o trecho k: a sobra do bruto até o trecho vizinho (no bruto), sem repetir fala de outro trecho */
export function limites(ms: Trecho[], k: number, durBruto: number): { min: number; max: number } {
  const m = ms[k]; let min = 0, max = durBruto
  for (const o of ms) { if (o === m) continue; if (o.fim <= m.inicio + 1e-6) min = Math.max(min, o.fim); if (o.inicio >= m.fim - 1e-6) max = Math.min(max, o.inicio) }
  return { min: r3(min), max: r3(max) }
}
