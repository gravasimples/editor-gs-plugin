import { useEffect, useState } from 'react'
import { api, type Dissecacao, type PecaFila, type SkillInstalada, type SkillsEstado } from '../api'

// Curadoria das skills (13/11/2026): instaladas ficam em quarentena (skills_biblioteca/, o agente não carrega), com raio-x sem modelo;
// "Dissecar" separa cada skill em peças (regra, ativo, código, descartar) e o Raphael marca o que o Editor absorve. O aproveitado vai para a fila.
const CX: Record<string, { rot: string; cor: string }> = {
  regra: { rot: '📏 Regras e números', cor: 'border-azul/50' }, ativo: { rot: '🎁 Ativos', cor: 'border-green-400/40' },
  codigo: { rot: '🧩 Código', cor: 'border-laranja/50' }, descartar: { rot: '🗑 Descartar', cor: 'border-white/10' },
}
const ALERTA: Record<string, string> = { custo: '💰', telemetria: '📡', publica: '📤', mandona: '⚠', licenca: '⚖', sistema: '🖥', idioma: '🗣', peso: '💾' }

type Agir = (rotulo: string, fn: () => Promise<any>, ok?: (r: any) => string) => Promise<void>

export function Pecas({ id, agir, ocupado }: { id: string; agir: Agir; ocupado: string }) {
  const [d, setD] = useState<Dissecacao | null>(null)
  const carregar = () => api.skillDissecacao(id).then(setD).catch(() => setD({ id, pecas: [] }))
  useEffect(() => { carregar() }, [id])
  if (!d) return <div className="text-nevoa text-xs mt-2">carregando peças…</div>
  if (!d.pecas.length) return <div className="text-nevoa text-xs mt-2">Ainda sem peças. Clique em “🔬 Dissecar”: o Editor lê a skill e separa o que dá para aproveitar.</div>
  const marcar = (n: number, dec: string) => agir(id + 'p' + n, () => api.skillPeca(id, n, dec)).then(carregar)
  const aproveitadas = d.pecas.filter(p => p.decisao === 'aproveitar').length, pendentes = d.pecas.filter(p => !p.decisao).length
  return <div className="mt-3 border-t border-white/10 pt-2">
    {d.resumo && <div className="text-xs text-nevoa mb-2">{d.resumo}</div>}
    <div className="text-[11px] text-nevoa mb-2">{d.pecas.length} peças · {aproveitadas} aproveitada(s) · {pendentes} sem decisão{d.por ? ` · dissecada por ${d.por} em ${d.quando?.slice(0, 16).replace('T', ' ')}` : ''}</div>
    <div className="grid gap-2 md:grid-cols-2">
      {Object.entries(CX).map(([cx, c]) => {
        const ps = d.pecas.filter(p => p.caixa === cx); if (!ps.length) return null
        return <div key={cx} className={`rounded-xl border ${c.cor} p-2`}>
          <div className="text-xs font-bold mb-1">{c.rot} · {ps.length}</div>
          {ps.map(p => <div key={p.n} className={`text-xs py-1.5 border-t border-white/5 ${p.decisao === 'descartar' ? 'opacity-50' : ''}`}>
            <div className="flex items-start gap-2">
              <div className="flex-1"><b>{p.titulo}</b>{p.destino && p.destino !== 'nenhum' && <span className="ml-1 rounded-full bg-white/5 px-1.5 text-[10px] text-nevoa">→ {p.destino}</span>}
                {p.detalhe && <div className="text-nevoa">{p.detalhe}</div>}
                {(p.fonte || p.custo) && <div className="text-[10px] text-nevoa">{p.fonte}{p.custo ? ` · ${p.custo}` : ''}</div>}</div>
              {p.decisao && <span className={`rounded-full px-2 py-0.5 text-[10px] ${p.decisao === 'aproveitar' ? 'bg-green-500/20 text-green-300' : 'bg-white/5 text-nevoa'}`}>{p.decisao}</span>}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {p.decisao !== 'aproveitar' && <button disabled={!!ocupado} onClick={() => marcar(p.n, 'aproveitar')} className="rounded-full border border-green-400/50 text-green-300 px-2 py-0.5 hover:bg-green-400/10">✓ aproveitar</button>}
              {p.caixa === 'regra' && <button disabled={!!ocupado} onClick={() => agir(id + 'k' + p.n, () => api.skillPecaConhecimento(id, p.n), r => `Virou conhecimento do Editor: ${r.arquivo}.`).then(carregar)} className="rounded-full border border-laranja/50 text-laranja px-2 py-0.5 hover:bg-laranja/10">🎓 ensinar ao Editor</button>}
              {p.decisao !== 'descartar' && <button disabled={!!ocupado} onClick={() => marcar(p.n, 'descartar')} className="rounded-full border border-white/15 px-2 py-0.5 text-nevoa hover:bg-white/5">descartar</button>}
              {p.decisao && <button disabled={!!ocupado} onClick={() => marcar(p.n, '')} className="rounded-full border border-white/10 px-2 py-0.5 text-nevoa hover:bg-white/5">desfazer</button>}
            </div>
          </div>)}
        </div>
      })}
    </div>
  </div>
}

function Alertas({ s }: { s: SkillInstalada }) {
  const rx = s.raiox
  if (!rx) return <span className="text-[10px] text-nevoa">sem raio-x</span>
  return <span className="flex flex-wrap gap-1">
    <span className={`rounded-full px-2 py-0.5 text-[10px] ${rx.sugestao === 'descartar' ? 'bg-red-500/15 text-red-300' : 'bg-azul/30 text-white'}`}>{rx.sugestao === 'descartar' ? 'sugestão: descartar' : 'sugestão: dissecar'}</span>
    {rx.alertas.filter(a => a.tipo !== 'licenca' || !rx.licenca.startsWith('MIT')).map((a, i) => <span key={i} title={a.texto} className="rounded-full bg-black/30 px-2 py-0.5 text-[10px]">{ALERTA[a.tipo] || '•'} {a.texto}</span>)}
    {Object.keys(rx.citados || {}).length > 0 && <span className="rounded-full bg-black/20 px-2 py-0.5 text-[10px] text-nevoa" title="só no texto (alternativa opcional ou aviso)">cita {Object.keys(rx.citados).join(', ')}</span>}
    <span className="text-[10px] text-nevoa">{rx.licenca} · {rx.peso_mb} MB</span>
  </span>
}

export function Instaladas({ est, agir, ocupado }: { est: SkillsEstado; agir: Agir; ocupado: string }) {
  const [verTodas, setVerTodas] = useState(false)
  const ativas = est.instaladas.filter(s => s.ativa), bib = est.instaladas.filter(s => !s.ativa)
  const terceiras = ativas.filter(s => !s.pasta.startsWith('gs-'))
  const recriavel = bib.reduce((t, s) => t + (s.raiox?.recriavel_mb || 0), 0)
  const linha = (s: SkillInstalada) => <div key={s.pasta} className="py-2 border-t border-white/5 text-xs">
    <div className="flex flex-wrap items-center gap-2"><b>{s.pasta}</b><span className="text-nevoa">{s.arquivos} arq.{s.tokens ? ` · ~${s.tokens} tokens se ativa` : ''}</span>
      <span className="ml-auto flex gap-1">
        {s.ativa ? <button disabled={!!ocupado} onClick={() => agir('d' + s.pasta, () => api.skillDesativar(s.pasta), () => `${s.pasta} saiu do agente (quarentena).`)} className="rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">tirar do agente</button>
          : <button disabled={!!ocupado} onClick={() => { const rx = s.raiox; const aviso = rx?.alertas.filter(a => a.tipo !== 'licenca').map(a => a.texto).join('; '); if (aviso && !confirm(`Ativar ${s.pasta}? O agente vai carregar a skill em todo pedido.\n\nAtenção: ${aviso}`)) return; agir('a' + s.pasta, () => api.skillAtivar(s.pasta), r => `${r.pasta} ativa no agente (~${r.tokens} tokens por pedido).`) }} className="rounded-full border border-laranja/50 text-laranja px-2 py-0.5 hover:bg-laranja/10">ativar no agente</button>}
        <button disabled={!!ocupado} onClick={() => agir('x' + s.pasta, () => api.skillRaioX(s.pasta), () => `Raio-x de ${s.pasta} refeito.`)} className="rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">raio-x</button>
        {!s.ativa && (s.raiox?.recriavel_mb || 0) > 1 && <button disabled={!!ocupado} onClick={() => { if (confirm(`Apagar ${s.raiox!.recriavel_mb} MB de .venv/node_modules de ${s.pasta}? A skill recria se um dia rodar; regras, modelos e ativos ficam.`)) agir('l' + s.pasta, () => api.skillLiberar(s.pasta), r => `${r.liberado_mb} MB liberados.`) }} className="rounded-full border border-white/15 px-2 py-0.5 hover:bg-white/5">liberar {Math.round(s.raiox!.recriavel_mb)} MB</button>}
      </span></div>
    <div className="text-nevoa mt-0.5">{s.descricao}</div>
    <div className="mt-1"><Alertas s={s} /></div>
  </div>
  return <div className="cartao p-4 text-sm mt-8">
    <div className="flex flex-wrap items-center gap-2"><div className="font-bold">🧩 Skills instaladas</div>
      <span className={`rounded-full px-2 py-0.5 text-[11px] ${ativas.length ? 'bg-laranja/20 text-laranja' : 'bg-green-500/20 text-green-300'}`}>{ativas.length} ativa(s) no agente · ~{est.tokens_ativas} tokens em todo pedido</span>
      <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-nevoa">{bib.length} em quarentena</span>
      {terceiras.length > 0 && <button disabled={!!ocupado} onClick={() => { if (confirm(`Tirar ${terceiras.length} skill(s) de terceiros do agente? Elas vão para a quarentena; nada é apagado.`)) agir('quar', () => api.skillsQuarentena(), r => `${r.movidas.length} skill(s) foram para a quarentena.`) }} className="ml-auto btn-laranja px-3 py-1 text-xs">Tirar todas do agente</button>}
    </div>
    <div className="text-nevoa text-xs mt-1">Instalar põe a skill em <b>quarentena</b> (<code>skills_biblioteca/</code>): o agente não carrega, só lê quando o pedido citar. Ativa (<code>.claude/skills/</code>) entra em todo pedido e custa tokens. O raio-x é automático e sem modelo: 💰 serviço pago, 📡 telemetria, 📤 publicação automática, ⚠ instrução que tira as perguntas, ⚖ licença, 🖥 sistema, 🗣 idioma, 💾 peso.{recriavel > 50 ? ` A quarentena tem ${Math.round(recriavel)} MB de .venv/node_modules que dá para liberar.` : ''}</div>
    {ativas.length > 0 && <div className="mt-3"><div className="text-xs font-bold">Ativas no agente</div>{ativas.map(linha)}</div>}
    {bib.length > 0 && <div className="mt-3"><div className="text-xs font-bold">Quarentena</div>{(verTodas ? bib : bib.slice(0, 8)).map(linha)}
      {bib.length > 8 && <button onClick={() => setVerTodas(!verTodas)} className="text-xs text-laranja hover:underline mt-1">{verTodas ? 'mostrar menos' : `mostrar as ${bib.length}`}</button>}</div>}
    {est.instaladas.length === 0 && <div className="text-nevoa text-xs mt-3">Nenhuma ainda.</div>}
  </div>
}

export function Fila({ fila, agir, ocupado }: { fila: PecaFila[]; agir: Agir; ocupado: string }) {
  const [ver, setVer] = useState(false)
  const aberta = fila.filter(f => f.estado === 'na_fila'), feitas = fila.filter(f => f.estado === 'feito')
  if (!fila.length) return null
  return <div className="cartao p-4 text-sm mt-4">
    <div className="flex items-center gap-2"><div className="font-bold">📥 Fila de absorção</div><span className="text-[11px] text-nevoa">{aberta.length} para construir · {feitas.length} feita(s)</span>
      {fila.length > aberta.length && <button onClick={() => setVer(!ver)} className="ml-auto text-xs text-laranja hover:underline">{ver ? 'só as abertas' : 'ver feitas e canceladas'}</button>}</div>
    <div className="text-nevoa text-xs mt-1">Peças que você marcou para o Editor absorver. Entram na ordem de construção (motor, Revisor, estilo, som…) com fonte e licença; “feito” quando já estão no Editor.</div>
    {(ver ? fila : aberta).map(f => <div key={f.chave} className={`py-2 border-t border-white/5 text-xs ${f.estado !== 'na_fila' ? 'opacity-60' : ''}`}>
      <div className="flex flex-wrap items-center gap-2"><b>{f.titulo}</b><span className="rounded-full bg-white/5 px-1.5 text-[10px] text-nevoa">{CX[f.caixa]?.rot || f.caixa} → {f.destino}</span><span className="text-[10px] text-nevoa">{f.nome}{f.licenca ? ` · ${f.licenca}` : ''}</span>
        <span className="ml-auto flex gap-1">{f.estado === 'na_fila' ? <>
          <button disabled={!!ocupado} onClick={() => agir('f' + f.chave, () => api.skillFilaMarcar(f.chave, 'feito'))} className="rounded-full border border-green-400/50 text-green-300 px-2 py-0.5 hover:bg-green-400/10">feito</button>
          <button disabled={!!ocupado} onClick={() => agir('c' + f.chave, () => api.skillFilaMarcar(f.chave, 'cancelado'))} className="rounded-full border border-white/15 px-2 py-0.5 text-nevoa hover:bg-white/5">cancelar</button></>
          : <button disabled={!!ocupado} onClick={() => agir('r' + f.chave, () => api.skillFilaMarcar(f.chave, 'na_fila'))} className="rounded-full border border-white/15 px-2 py-0.5 text-nevoa hover:bg-white/5">voltar para a fila</button>}</span></div>
      {f.detalhe && <div className="text-nevoa">{f.detalhe}</div>}{f.nota && <div className="text-[10px] text-nevoa">{f.nota}</div>}
    </div>)}
  </div>
}
