import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

type Op = { quando: string; gateway: { no_ar_desde: string; no_ar_min: number }; gpu: { nome: string; vram_usada_mb: number; vram_total_mb: number; vram_pct: number; uso_pct: number | null; temperatura_c: number | null } | null
  disco: { total_gb: number; livre_gb: number; usado_pct: number } | null; carga_1m?: number; nucleos?: number; ram_total_gb?: number; ram_livre_gb?: number; ram_usada_pct?: number
  processos: Record<string, number>; claude: { versao: string | null; caminho?: string; erro?: string }
  paperclip: { status: string; versao?: string; agentes?: { nome: string; status: string; modelo: string; id_app: string | null }[]; erro?: string } | null
  pedidos: { em_andamento: { id: string; codigo: string; titulo: string; desde: string | null }[]; na_fila: number; aguardando_voce: number; hoje: { criados: number; concluidos: number } } | null; avisos: string[] }

// Atualização automática (13/11/2026): no modo plugin o gateway confere o GitHub a cada 30 min e se atualiza sozinho com a fila livre.
type Atz = { versao: string; remota?: string; modo_plugin: boolean; ligado: boolean; checado_em?: string; disponivel?: boolean; aguardando?: string | null; erro?: string | null; historico?: { de: string; para: string; subiu_em: string; ok: boolean }[] }
function Versao() {
  const [a, setA] = useState<Atz | null>(null); const [ocupado, setOcupado] = useState(false)
  const carregar = () => fetch('/api/gs/atualizacao').then(r => r.json()).then(setA).catch(() => {})
  useEffect(() => { carregar() }, [])
  if (!a) return null
  const procurar = () => { setOcupado(true); fetch('/api/gs/atualizacao/agora', { method: 'POST' }).then(r => r.json()).finally(() => { setOcupado(false); carregar() }) }
  const ult = a.historico?.[a.historico.length - 1]
  return <div className="cartao p-4 mt-4 text-sm">
    <div className="flex flex-wrap items-center gap-2"><div className="font-bold">Versão do Editor</div><span className="rounded-full bg-white/5 px-2 py-0.5 text-xs">{a.versao || '?'}</span>
      {a.disponivel && <span className="rounded-full bg-laranja/20 text-laranja px-2 py-0.5 text-xs">nova versão {a.remota}</span>}
      {a.modo_plugin && <button disabled={ocupado} onClick={procurar} className="ml-auto rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5 disabled:opacity-50">{ocupado ? 'procurando…' : 'Procurar atualização'}</button>}</div>
    <div className="text-nevoa text-xs mt-1">{!a.modo_plugin ? 'Instalação de desenvolvimento: atualiza pelo git, não sozinha.'
      : a.ligado ? `Atualiza sozinho: confere a cada 30 min e instala quando nenhum pedido estiver rodando${a.checado_em ? ` · última olhada ${a.checado_em.slice(11, 16)}` : ''}.` : 'Atualização automática desligada (atualizar_sozinho = false).'}</div>
    {a.aguardando && <div className="text-xs mt-1">⏳ {a.aguardando}</div>}
    {a.erro && <div className="text-xs mt-1 text-red-300">{a.erro}</div>}
    {ult && <div className="text-xs mt-1 text-nevoa">Última atualização: {ult.de} → {ult.para} em {ult.subiu_em.slice(0, 16).replace('T', ' ')}{ult.ok ? '' : ' (com problema)'}</div>}
  </div>
}

function Barra({ pct, cor = 'bg-laranja' }: { pct: number; cor?: string }) { return <div className="h-2 rounded-full bg-white/10 overflow-hidden"><div className={`h-full ${pct >= 90 ? 'bg-red-400' : cor}`} style={{ width: `${Math.min(100, pct)}%` }} /></div> }
const PROC: Record<string, string> = { voz_qwen: 'voz do Thiago (Qwen) carregada', voz_chatterbox: 'voz (Chatterbox) carregada', mcp_editor: 'MCP editor-de-video', paperclip: 'Paperclip', ffmpeg: 'ffmpeg renderizando', remotion: 'Remotion renderizando' }

export default function Operacao() {
  const [op, setOp] = useState<Op | null>(null); const [erro, setErro] = useState('')
  const carregar = () => fetch('/api/gs/operacao').then(r => r.json()).then(setOp).catch(e => setErro(e.message))
  useEffect(() => { carregar(); const t = window.setInterval(carregar, 15000); return () => window.clearInterval(t) }, [])
  if (erro) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-300">{erro}</div>
  if (!op) return <div className="max-w-3xl mx-auto px-4 py-8"><h2 className="text-2xl">Operação</h2><p className="text-nevoa mt-2 animate-pulse">Carregando… (lendo placa de vídeo, disco e processos)</p></div>
  const min = (s: string | null) => { if (!s) return ''; const m = Math.round((Date.now() - new Date(s).getTime()) / 60000); return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min` }
  return <div className="max-w-4xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Operação</h2><span className="text-nevoa text-xs">atualiza a cada 15 s · {op.quando.slice(11, 19)}</span></div>
    <p className="text-nevoa mt-2 text-sm">O que está rodando neste computador e no executor do Editor. Só leitura: nada aqui muda estado.</p>
    {op.avisos.length > 0 && <div className="cartao p-3 mt-3 text-sm text-laranja border border-laranja/40">{op.avisos.map((a, i) => <div key={i}>⚠ {a}</div>)}</div>}
    <Versao />

    <div className="grid md:grid-cols-2 gap-4 mt-5 text-sm">
      <div className="cartao p-4">
        <div className="font-bold">Placa de vídeo</div>
        {op.gpu ? <>
          <div className="text-nevoa text-xs mt-1">{op.gpu.nome}{op.gpu.temperatura_c != null ? ` · ${op.gpu.temperatura_c} °C` : ''}{op.gpu.uso_pct != null ? ` · uso ${op.gpu.uso_pct}%` : ''}</div>
          <div className="mt-2 text-xs">VRAM {op.gpu.vram_usada_mb} / {op.gpu.vram_total_mb} MB ({op.gpu.vram_pct}%)</div><Barra pct={op.gpu.vram_pct} />
          <div className="text-nevoa text-[11px] mt-2">A voz do Thiago (Qwen) ocupa ~3,9 GB enquanto carregada e descarrega sozinha após 10 min sem uso. Com ela carregada, nada mais cabe na placa.</div>
        </> : <div className="text-nevoa text-xs mt-1">sem placa NVIDIA visível</div>}
      </div>
      <div className="cartao p-4">
        <div className="font-bold">Computador</div>
        {op.disco && <><div className="mt-2 text-xs">Disco: {op.disco.livre_gb} GB livres de {op.disco.total_gb} GB</div><Barra pct={op.disco.usado_pct} cor="bg-azul" /></>}
        {op.ram_usada_pct != null && <><div className="mt-2 text-xs">Memória: {op.ram_usada_pct}% usada ({op.ram_livre_gb} GB livres de {op.ram_total_gb} GB)</div><Barra pct={op.ram_usada_pct} cor="bg-azul" /></>}
        {op.carga_1m != null && <div className="text-nevoa text-xs mt-2">Carga do processador: {op.carga_1m} em {op.nucleos} núcleos</div>}
        <div className="text-nevoa text-xs mt-2">Gateway no ar desde {op.gateway.no_ar_desde.replace('T', ' ')} ({op.gateway.no_ar_min} min) · Claude Code {op.claude.versao || op.claude.erro}</div>
      </div>
      <div className="cartao p-4">
        <div className="font-bold">Processos</div>
        <div className="grid gap-1 mt-2 text-xs">{Object.entries(op.processos).map(([k, n]) => <div key={k} className="flex items-center gap-2"><span className={`inline-block w-2 h-2 rounded-full ${n > 0 ? 'bg-green-400' : 'bg-white/20'}`} />{PROC[k] || k}{n > 1 ? ` ×${n}` : ''}</div>)}</div>
      </div>
      <div className="cartao p-4">
        <div className="font-bold">Executor e agentes</div>
        {op.paperclip ? <>
          <div className="text-nevoa text-xs mt-1">{op.paperclip.status}{op.paperclip.versao ? ` · v${op.paperclip.versao}` : ''}{op.paperclip.erro ? ` · ${op.paperclip.erro}` : ''}</div>
          <div className="grid gap-1 mt-2 text-xs">{(op.paperclip.agentes || []).map(a => <div key={a.nome} className="flex items-center gap-2"><span className={`inline-block w-2 h-2 rounded-full ${a.status === 'active' || a.status === 'idle' ? 'bg-green-400' : a.status === 'running' ? 'bg-laranja' : 'bg-white/20'}`} />{a.nome}<span className="text-nevoa">· {a.status}{a.modelo ? ` · ${a.modelo}` : ''}</span></div>)}</div>
        </> : <div className="text-nevoa text-xs mt-1">offline</div>}
      </div>
    </div>

    {op.pedidos && <div className="cartao p-4 mt-4 text-sm">
      <div className="flex items-center gap-3 flex-wrap"><div className="font-bold">Pedidos</div><span className="text-nevoa text-xs">hoje: {op.pedidos.hoje.criados} criados · {op.pedidos.hoje.concluidos} concluídos · {op.pedidos.na_fila} na fila · {op.pedidos.aguardando_voce} aguardando você</span></div>
      {op.pedidos.em_andamento.length > 0 ? <div className="grid gap-1 mt-2 text-xs">{op.pedidos.em_andamento.map(p => <Link key={p.id} to={`/c/${p.id}`} className="flex items-center gap-2 rounded-lg bg-white/5 px-2 py-1.5 hover:bg-white/10"><span className="selo">{p.codigo}</span><span className="flex-1 truncate">{p.titulo}</span><span className="text-nevoa">{min(p.desde)}</span></Link>)}</div>
        : <div className="text-nevoa text-xs mt-2">Nenhum pedido em andamento.</div>}
    </div>}
  </div>
}
