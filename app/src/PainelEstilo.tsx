import { useEffect, useState } from 'react'
import { api, type EstiloCfg, type EstiloCriativo } from './api'

// Painel "Estilo do criativo" (fase D, 07/11/2026), no jeito do Máquina: energia do vídeo, chaves, legenda, "Salvar como meu padrão"
// e as memórias ("Também no seu padrão") que o Raphael escreveu ou o Editor aprendeu nas conversas, visíveis e removíveis.
// No Novo pedido a escolha vai junto do pedido; na conversa, `onAplicar` manda "refaça com este estilo".
export function PainelEstilo({ valor, onChange, onAplicar, rotuloAplicar = 'Refazer com este estilo', className = '' }:
  { valor: EstiloCfg | null; onChange: (c: EstiloCfg) => void; onAplicar?: (c: EstiloCfg) => Promise<void> | void; rotuloAplicar?: string; className?: string }) {
  const [aberto, setAberto] = useState(false)
  const [dados, setDados] = useState<EstiloCriativo | null>(null)
  const [nova, setNova] = useState('')
  const [aviso, setAviso] = useState('')
  const [ocupado, setOcupado] = useState(false)
  useEffect(() => { api.estiloCriativo().then(d => { setDados(d); if (!valor) onChange(d.padrao) }).catch(() => {}) }, [])
  const cfg = valor || dados?.padrao
  if (!dados || !cfg) return null
  const igualPadrao = JSON.stringify(cfg) === JSON.stringify(dados.padrao)
  const set = (m: Partial<EstiloCfg>) => onChange({ ...cfg, ...m })
  const rotEnergia = dados.opcoes.energias.find(e => e.id === cfg.energia)?.rotulo || cfg.energia
  async function salvarPadrao() { setOcupado(true); try { setDados(await api.estiloCriativoPadrao(cfg!)); setAviso('Salvo como seu padrão: os próximos pedidos já vêm assim.') } catch (e: any) { setAviso(e.message) } finally { setOcupado(false) } }
  async function lembrar() { if (!nova.trim()) return; try { const m = await api.lembrar(nova); setDados(d => d && ({ ...d, memorias: d.memorias.some(x => x.id === m.id) ? d.memorias : [...d.memorias, m] })); setNova('') } catch (e: any) { setAviso(e.message) } }
  async function esquecer(id: string) { try { await api.esquecer(id); setDados(d => d && ({ ...d, memorias: d.memorias.filter(m => m.id !== id) })) } catch (e: any) { setAviso(e.message) } }
  const pill = (on: boolean) => `rounded-full border px-3 py-1 text-xs ${on ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`
  return (
    <span className={`relative ${className}`}>
      <button type="button" onClick={() => setAberto(!aberto)} title="Energia do vídeo, cortes, zoom, grafismos, legenda e as preferências que o Editor guarda (como o painel Estilo do Máquina)"
        className={`rounded-full border px-3 py-1.5 text-sm ${aberto || !igualPadrao ? 'border-laranja text-laranja bg-laranja/10' : 'border-white/15 hover:bg-white/5'}`}>🎛 Estilo: {rotEnergia}{igualPadrao ? '' : ' •'}</button>
      {aberto && <div className="absolute z-30 bottom-full mb-2 left-0 w-[min(92vw,26rem)] cartao p-4 shadow-2xl text-sm space-y-3 max-h-[70vh] overflow-y-auto">
        <div className="flex items-center"><b>Estilo do criativo</b><button onClick={() => setAberto(false)} className="ml-auto text-nevoa">✕</button></div>
        <div><div className="text-xs text-nevoa mb-1">Energia do vídeo</div>
          <div className="flex flex-wrap gap-2">{dados.opcoes.energias.map(e => <button key={e.id} type="button" onClick={() => set({ energia: e.id })} className={pill(cfg.energia === e.id)}>{e.rotulo}{e.id === 'dinamico' ? ' (padrão)' : ''}</button>)}</div></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1.5">{dados.opcoes.chaves.map(k => <label key={k.id} className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={!!cfg.chaves[k.id]} onChange={e => set({ chaves: { ...cfg.chaves, [k.id]: e.target.checked } })} className="accent-[#F79615]" />{k.rotulo}</label>)}</div>
        <div className="flex items-center gap-2"><span className="text-xs text-nevoa">Legenda:</span>{dados.opcoes.legendas.map(l => <button key={l.id} type="button" onClick={() => set({ legenda: l.id })} className={pill(cfg.legenda === l.id)}>{l.rotulo}</button>)}</div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={salvarPadrao} disabled={ocupado || igualPadrao} className="rounded-full border border-laranja/60 text-laranja px-3 py-1 text-xs hover:bg-laranja/10 disabled:opacity-40">{igualPadrao ? '✓ É o seu padrão' : 'Salvar como meu padrão'}</button>
          {!igualPadrao && <button type="button" onClick={() => onChange(dados.padrao)} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">Voltar ao padrão</button>}
          {onAplicar && <button type="button" disabled={ocupado} onClick={async () => { setOcupado(true); try { await onAplicar(cfg); setAberto(false) } finally { setOcupado(false) } }} className="btn-laranja px-3 py-1 text-xs ml-auto">{rotuloAplicar}</button>}
        </div>
        <div className="border-t border-white/10 pt-3"><div className="text-xs text-nevoa mb-1">Também no seu padrão <span title="Preferências que valem em toda edição: as que você escreve aqui e as que o Editor guarda quando você diz 'sempre…' numa conversa. Apague as que não valem mais.">ⓘ</span></div>
          {dados.memorias.length === 0 && <div className="text-xs text-nevoa">Nada ainda. Escreva abaixo, ou diga "sempre…" numa conversa que o Editor guarda.</div>}
          <ul className="space-y-1">{dados.memorias.map(m => <li key={m.id} className="flex items-start gap-2 text-xs"><span className="flex-1">{m.texto} <span className="text-nevoa">· {m.origem.startsWith('Editor') ? 'aprendida' : 'você'}</span></span><button onClick={() => esquecer(m.id)} title="Esquecer" className="text-nevoa hover:text-red-300">✕</button></li>)}</ul>
          <div className="flex gap-2 mt-2"><input value={nova} onChange={e => setNova(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); lembrar() } }} placeholder="Ex.: usar as logos reais de Zoom, Meet e OBS" className="flex-1 bg-transparent border border-white/15 rounded-full px-3 py-1 text-xs outline-none" />
            <button type="button" onClick={lembrar} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">+ Lembrar</button></div></div>
        {aviso && <div className="text-xs text-laranja">{aviso}</div>}
      </div>}
    </span>
  )
}
