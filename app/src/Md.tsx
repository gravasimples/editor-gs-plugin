import { type ReactNode } from 'react'

export function Inline({ t }: { t: string }) {
  const partes = t.split(/(`[^`]+`|\*\*[^*]+\*\*|https?:\/\/[^\s)]+)/g)
  return <>{partes.map((p, i) => p.startsWith('`') ? <code key={i} className="bg-white/10 rounded px-1 text-[0.9em]">{p.slice(1, -1)}</code>
    : p.startsWith('**') ? <b key={i}>{p.slice(2, -2)}</b>
    : /^https?:\/\//.test(p) ? <a key={i} href={p} target="_blank" rel="noreferrer" className="text-laranja break-all">{p}</a>
    : <span key={i}>{p}</span>)}</>
}

/** Renderizador mínimo de Markdown: parágrafos, listas, citações, tabelas e títulos ###. Sem HTML, sem dependência. */
export function Md({ texto, className = '' }: { texto: string; className?: string }) {
  const linhas = texto.split('\n'); const blocos: ReactNode[] = []; let i = 0
  while (i < linhas.length) {
    const l = linhas[i]
    if (!l.trim()) { i++; continue }
    if (l.startsWith('|')) {
      const tab: string[] = []; while (i < linhas.length && linhas[i].startsWith('|')) { tab.push(linhas[i]); i++ }
      const celulas = (s: string) => s.split('|').slice(1, -1).map(x => x.trim())
      const [cab, ...corpo] = tab.filter(r => !/^\|\s*:?-+/.test(r))
      blocos.push(<div key={i} className="overflow-x-auto my-2"><table className="text-sm w-full"><thead><tr>{celulas(cab || '').map((c, k) => <th key={k} className="text-left text-nevoa font-normal pr-4 pb-1 border-b border-white/10"><Inline t={c} /></th>)}</tr></thead>
        <tbody>{corpo.map((r, k) => <tr key={k}>{celulas(r).map((c, j) => <td key={j} className="pr-4 py-1 align-top border-b border-white/5"><Inline t={c} /></td>)}</tr>)}</tbody></table></div>)
      continue
    }
    if (/^(\s*[-*•]|\s*\d+[.)])\s/.test(l)) {
      const itens: string[] = []; const num = /^\s*\d+[.)]\s/.test(l)
      while (i < linhas.length && /^(\s*[-*•]|\s*\d+[.)])\s/.test(linhas[i])) { itens.push(linhas[i].replace(/^(\s*[-*•]|\s*\d+[.)])\s/, '')); i++ }
      const Tag = num ? 'ol' : 'ul'
      blocos.push(<Tag key={i} className={`${num ? 'list-decimal' : 'list-disc'} pl-5 my-2 grid gap-1`}>{itens.map((x, k) => <li key={k}><Inline t={x} /></li>)}</Tag>); continue
    }
    if (l.startsWith('>')) {
      const q: string[] = []; while (i < linhas.length && linhas[i].startsWith('>')) { q.push(linhas[i].replace(/^>\s?/, '')); i++ }
      blocos.push(<blockquote key={i} className="border-l-2 border-laranja/60 pl-3 my-2 text-nevoa"><Inline t={q.join(' ')} /></blockquote>); continue
    }
    if (l.startsWith('```')) {
      const c: string[] = []; i++; while (i < linhas.length && !linhas[i].startsWith('```')) { c.push(linhas[i]); i++ } i++
      blocos.push(<pre key={i} className="whitespace-pre-wrap text-xs bg-black/40 rounded-xl p-3 my-2">{c.join('\n')}</pre>); continue
    }
    if (/^#{1,4}\s/.test(l)) { blocos.push(<h4 key={i} className="font-bold mt-3 mb-1">{l.replace(/^#+\s/, '')}</h4>); i++; continue }
    // Parágrafo: só para nos inícios de bloco que os ramos acima realmente tratam (`#` sem espaço, como em hashtags, é texto comum).
    const p: string[] = []; while (i < linhas.length && linhas[i].trim() && !/^(\||>|#{1,4}\s|```|\s*[-*•]\s|\s*\d+[.)]\s)/.test(linhas[i])) { p.push(linhas[i]); i++ }
    if (p.length === 0) { p.push(l); i++ }  // garantia: nunca ficar parado na mesma linha (antes isso travava o app com Out of Memory)
    blocos.push(<p key={i} className="my-2 leading-relaxed whitespace-pre-wrap"><Inline t={p.join('\n')} /></p>)
  }
  return <div className={className}>{blocos}</div>
}

export type SecaoTexto = { chave: string; titulo: string; conteudo: string }

/** Separa um Markdown por `## ` (mesma regra do gateway, servico/textos.py). */
export function secoesDe(texto: string): { intro: string; secoes: SecaoTexto[] } {
  if (!/^##\s+\S/m.test(texto)) return { intro: texto, secoes: [] }
  const secoes: SecaoTexto[] = []; let intro: string[] = []; let atual: SecaoTexto | null = null
  for (const l of texto.split('\n')) {
    const m = /^##\s+(.+?)\s*#*\s*$/.exec(l)
    if (m && !l.startsWith('###')) { atual = { chave: m[1].toLowerCase(), titulo: m[1].trim(), conteudo: '' }; secoes.push(atual) }
    else if (atual) atual.conteudo += (atual.conteudo ? '\n' : '') + l
    else intro.push(l)
  }
  return { intro: intro.join('\n').trim(), secoes: secoes.map(s => ({ ...s, conteudo: s.conteudo.trim() })).filter(s => s.conteudo) }
}

export function copiar(t: string) { try { navigator.clipboard?.writeText(t) } catch {} }
