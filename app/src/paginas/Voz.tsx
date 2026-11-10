import { useEffect, useRef, useState } from 'react'
import { api, type Voz, type VozAmostra, type VozGeracao } from '../api'

function seg(s: number | null | undefined) { return s == null ? '' : `${s.toFixed(1)} s` }

function Player({ url }: { url: string }) {
  return <audio controls preload="none" src={url} className="w-full h-9" />
}

export default function VozPagina() {
  const [vozes, setVozes] = useState<Voz[]>([])
  const [disponivel, setDisponivel] = useState(true)
  const [motores, setMotores] = useState<Record<string, boolean>>({})
  const [motorNovo, setMotorNovo] = useState(''); const [refText, setRefText] = useState(''); const [semente, setSemente] = useState('')
  const [qwenNovo, setQwenNovo] = useState<{ temperatura: string; top_p: string; repeticao: string }>({ temperatura: '', top_p: '', repeticao: '' })
  const [maisOpcoes, setMaisOpcoes] = useState(false)
  const [ger, setGer] = useState<VozGeracao | null>(null)
  const [textoPadrao, setTextoPadrao] = useState('')
  const [erro, setErro] = useState(''); const [aviso, setAviso] = useState('')
  const [texto, setTexto] = useState(''); const [refNova, setRefNova] = useState('')
  const [form, setForm] = useState<{ referencia: string; motor: 'qwen' | 'chatterbox'; aprovada: boolean; padrao_locucao: boolean; nota: string; exagero: number; cfg: number; qwen: { temperatura: number; top_p: number; repeticao: number } } | null>(null)
  const [avancado, setAvancado] = useState(false)
  const timer = useRef<number | null>(null)

  const carregar = () => api.voz().then(r => {
    setVozes(r.vozes); setDisponivel(r.disponivel); setMotores(r.motores || {}); setGer(r.geracao); setTextoPadrao(r.texto_padrao)
    const v = r.vozes[0]
    if (v && !form) { setForm({ referencia: v.referencia || '', motor: v.motor || 'chatterbox', aprovada: v.aprovada, padrao_locucao: v.padrao_locucao, nota: v.nota || '', exagero: v.exagero, cfg: v.cfg, qwen: v.qwen || { temperatura: 0.9, top_p: 0.9, repeticao: 1.05 } }); setRefNova(v.referencia || ''); setMotorNovo(v.motor || 'chatterbox') }
    if (!texto) setTexto(r.texto_padrao)
  }).catch(e => setErro(e.message))
  useEffect(() => { carregar(); return () => { if (timer.current) window.clearInterval(timer.current) } }, [])
  useEffect(() => {
    if (ger?.status === 'rodando' && !timer.current) {
      timer.current = window.setInterval(() => api.vozGeracao().then(g => { setGer(g); if (g.status !== 'rodando') { if (timer.current) window.clearInterval(timer.current); timer.current = null; carregar() } }).catch(() => {}), 4000)
    }
  }, [ger?.status])

  const v = vozes[0]
  if (erro && !v) return <div className="max-w-3xl mx-auto px-4 py-8 text-red-300">{erro}</div>
  if (!v) return <div className="max-w-3xl mx-auto px-4 py-8"><h2 className="text-2xl">Voz clonada</h2><p className="text-nevoa mt-2">Nenhuma voz clonada em <code>workspace/voz/</code>. Veja <code>docs/VOZ-CLONADA.md</code>.</p></div>

  async function salvar() {
    if (!form) return
    setErro(''); setAviso('')
    try {
      const r = await api.vozDecidir(v.nome, { referencia: form.referencia, motor: form.motor, aprovada: form.aprovada ? 'sim' : 'nao', padrao_locucao: form.padrao_locucao ? 'sim' : 'nao', nota: form.nota, exagero: String(form.exagero), cfg: String(form.cfg), qwen_temperatura: String(form.qwen.temperatura), qwen_top_p: String(form.qwen.top_p), qwen_repeticao: String(form.qwen.repeticao) })
      setAviso(`Decisão gravada em voz.json (${r.decidido_em}). Motor: ${r.motor_nome}. Referência padrão: ${r.referencia}.`); carregar()
    } catch (e: any) { setErro(e.message) }
  }
  async function gerar() {
    setErro(''); setAviso('')
    const m = motorNovo || form?.motor || v.motor
    try {
      await api.vozAmostra(v.nome, texto, refNova || form?.referencia || '', { motor: m, ref_text: m === 'qwen' ? refText.trim() : '', semente: semente.trim(), qwen_temperatura: m === 'qwen' ? qwenNovo.temperatura : '', qwen_top_p: m === 'qwen' ? qwenNovo.top_p : '', qwen_repeticao: m === 'qwen' ? qwenNovo.repeticao : '' })
      setGer({ status: 'rodando', etapa: m === 'qwen' ? 'carregando o Qwen3-TTS (~2 min)…' : 'carregando o Chatterbox (~40 s)…' } as VozGeracao)
    } catch (e: any) { setErro(e.message) }
  }
  async function apagar(a: VozAmostra) {
    if (!confirm(`Apagar a amostra ${a.nome}?`)) return
    try { await api.vozApagarAmostra(v.nome, a.nome); carregar() } catch (e: any) { setErro(e.message) }
  }
  const refNome = (n: string | null | undefined) => { const r = v.referencias.find(x => x.nome === n); return r ? `${n} (${r.origem === 'aula_1' ? 'Aula 1' : r.origem === 'obs_blade' ? 'OBS Blade' : r.origem || '?'})` : n || '' }
  const nomeMotor = (m: string | undefined) => m === 'qwen' ? 'Qwen3-TTS' : m === 'chatterbox' ? 'Chatterbox pt-BR' : m || '?'
  const motorAtivo = motorNovo || form?.motor || v.motor
  const refTextoDe = (n: string) => v.referencias.find(x => x.nome === n)?.texto || ''
  const salvarPendente = form && form.motor !== v.motor

  return <div className="max-w-3xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3 flex-wrap"><h2 className="text-2xl">Voz clonada do Thiago</h2><span className="rounded-full px-3 py-1 text-xs bg-laranja/20 text-laranja">Motor: {v.motor_nome}</span><span className={`ml-auto rounded-full px-3 py-1 text-xs ${v.aprovada ? 'bg-green-500/20 text-green-300' : 'bg-white/10 text-nevoa'}`}>{v.aprovada ? 'Aprovada' : 'Aguardando sua decisão'}</span></div>
    <p className="text-nevoa mt-2 text-sm">Voz sintética clonada, roda neste computador, de graça. Motor em uso: <b>{v.motor_nome}</b>{v.motor === 'qwen' ? ' (escolhido por você em 31/10; o Chatterbox fica de reserva)' : ''}. Nunca é apresentada como gravação do Thiago e nunca entra em depoimento, oferta ou preço. Ouça aqui, compare as referências e decida; a decisão vale para <code>narrar</code>, <code>montar_locucao</code> e <code>dublar</code>.</p>
    {!v.disponivel && <div className="cartao p-3 mt-3 text-sm text-red-300">O ambiente do motor {v.motor_nome} (<code>{v.motor === 'qwen' ? '~/.venvs/editor-gs-qwen' : '~/.venvs/editor-gs-voz'}</code>) não está neste computador: dá para ouvir as amostras, mas não gerar novas com ele.</div>}
    {v.motor === 'qwen' && <div className="cartao p-3 mt-3 text-xs text-nevoa">O Qwen é mais lento na sua placa: cerca de 11 s de processamento por segundo de fala (uma narração de 40 s leva uns 8 min). Em pedido longo, o agente avisa o tempo.{!v.ref_text && <span className="text-red-300"> A referência padrão não tem transcrição em <code>referencias/transcricoes.json</code>; o Qwen vai usar só o timbre e a entonação piora.</span>}</div>}
    {aviso && <div className="cartao p-3 mt-3 text-sm text-green-300">{aviso}</div>}
    {erro && <div className="cartao p-3 mt-3 text-sm text-red-300">{erro}</div>}

    <h3 className="text-lg mt-8">1. Ouça as amostras (voz sintética)</h3>
    <p className="text-nevoa text-xs mt-1">Cada amostra diz o modelo, o trecho original que serviu de referência e, quando medido, o quanto o timbre e a prosódia chegam perto do Thiago real. Ouça e marque a que soa mais com ele.</p>
    <div className="grid gap-3 mt-3">{v.amostras.map(a => <div key={a.nome} className="cartao p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2"><span className="font-bold">{a.nome}</span><span className={`rounded-full px-2 py-0.5 text-[10px] ${a.motor === 'qwen' ? 'bg-laranja/20 text-laranja' : 'bg-white/10 text-nevoa'}`}>{nomeMotor(a.motor)}</span><span className="text-nevoa text-xs">{a.modelo} · ref. {refNome(a.referencia)} · {seg(a.duracao_s)} · {a.quando?.replace('T', ' ')}</span>{a.origem === 'pagina-voz' && <button onClick={() => apagar(a)} className="ml-auto text-xs text-nevoa hover:text-red-300">Apagar</button>}</div>
      <div className="mt-2"><Player url={a.url} /></div>
      {a.nota && <div className="text-nevoa text-xs mt-2">{a.nota}</div>}
      {a.medidas?.ve != null && <div className="text-nevoa text-xs mt-2">Medidas: timbre {a.medidas.ve.toFixed(2)}{a.medidas.teto_ve != null ? ` (Thiago×Thiago ${a.medidas.teto_ve.toFixed(2)})` : ''}{a.medidas.f0_hz != null ? ` · tom ${Math.round(a.medidas.f0_hz)} Hz${a.medidas.alvo_f0_hz != null ? ` (real ${Math.round(a.medidas.alvo_f0_hz)})` : ''}` : ''}{a.medidas.f0_desvio_st != null ? ` · variação ${a.medidas.f0_desvio_st.toFixed(1)} st${a.medidas.alvo_f0_desvio_st != null ? ` (real ${a.medidas.alvo_f0_desvio_st.toFixed(1)})` : ''}` : ''}{a.medidas.ritmo_pps != null ? ` · ritmo ${a.medidas.ritmo_pps.toFixed(1)}/s${a.medidas.alvo_ritmo_pps != null ? ` (real ${a.medidas.alvo_ritmo_pps.toFixed(1)})` : ''}` : ''}. Timbre e prosódia medidos por máquina; sotaque e naturalidade só o ouvido julga.</div>}
      {a.texto && <div className="text-xs mt-2 text-white/80">“{a.texto}”</div>}
    </div>)}</div>

    <h3 className="text-lg mt-8">2. Referências (Thiago de verdade, trechos das aulas)</h3>
    <p className="text-nevoa text-xs mt-1">O clone imita o trecho escolhido: timbre, ritmo e energia. Marque a que soa mais com ele; a padrão hoje é <b>{v.referencia}</b>.</p>
    <div className="grid gap-3 mt-3">{v.referencias.map(r => <label key={r.nome} className={`cartao p-4 text-sm block cursor-pointer border ${form?.referencia === r.nome ? 'border-laranja' : 'border-transparent'}`}>
      <div className="flex flex-wrap items-center gap-2"><input type="radio" name="ref" checked={form?.referencia === r.nome} onChange={() => form && setForm({ ...form, referencia: r.nome })} className="accent-[#F79615]" /><span className="font-bold">{r.nome}</span><span className="text-nevoa text-xs">{r.origem === 'aula_1' ? 'Aula 1' : r.origem === 'obs_blade' ? 'OBS Blade' : r.origem} · {seg(r.duracao_s)}{r.nivel_db != null ? ` · ${r.nivel_db} dBFS` : ''}</span>{v.referencia === r.nome && <span className="ml-auto text-xs text-laranja">padrão atual</span>}</div>
      <div className="mt-2"><Player url={r.url} /></div>
      {r.texto && <div className="text-nevoa text-xs mt-2">“{r.texto}”</div>}
    </label>)}</div>

    <h3 className="text-lg mt-8">3. Gerar uma amostra nova</h3>
    <p className="text-nevoa text-xs mt-1">Escreva a frase e escolha a referência e o motor. Qwen: ~2 min para carregar mais ~11 s por segundo de fala; Chatterbox: ~40 s mais ~3 s por segundo. Uma por vez (a placa de vídeo só cabe uma). Para afinar a entonação: vírgula e reticências dão pausa, ponto final fecha a frase, MAIÚSCULA numa palavra dá ênfase; gere 2 ou 3 variantes da mesma frase (semente diferente) e marque a melhor.</p>
    <div className="cartao p-4 mt-3 grid gap-3 text-sm">
      <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={3} className="rounded-xl bg-black/40 p-3 outline-none" placeholder={textoPadrao} />
      <div className="flex flex-wrap items-center gap-2"><span className="text-nevoa">Referência:</span><select value={refNova} onChange={e => setRefNova(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5">{v.referencias.map(r => <option key={r.nome} value={r.nome}>{refNome(r.nome)}</option>)}</select>
        <span className="text-nevoa">Motor:</span><select value={motorAtivo} onChange={e => setMotorNovo(e.target.value)} className="rounded-full border border-white/15 bg-card px-3 py-1.5"><option value="qwen" disabled={motores.qwen === false}>Qwen3-TTS{motores.qwen === false ? ' (sem ambiente)' : ''}</option><option value="chatterbox" disabled={motores.chatterbox === false}>Chatterbox pt-BR{motores.chatterbox === false ? ' (sem ambiente)' : ''}</option></select>
        <button onClick={gerar} disabled={!disponivel || motores[motorAtivo] === false || ger?.status === 'rodando' || texto.trim().length < 10} className="btn-laranja ml-auto px-4 py-2">{ger?.status === 'rodando' ? 'Gerando…' : 'Gerar amostra'}</button></div>
      <button onClick={() => setMaisOpcoes(!maisOpcoes)} className="text-xs text-nevoa text-left hover:text-white">{maisOpcoes ? '▾' : '▸'} Mais opções (semente{motorAtivo === 'qwen' ? ', texto da referência e parâmetros do Qwen' : ''})</button>
      {maisOpcoes && <div className="grid gap-2 text-xs text-nevoa">
        <label className="flex items-center gap-2">Semente (número; a mesma semente repete o resultado, outra dá uma variante) <input value={semente} onChange={e => setSemente(e.target.value.replace(/[^0-9]/g, ''))} className="rounded-full bg-black/40 px-3 py-1 w-28 outline-none" placeholder="vazio = aleatória" /></label>
        {motorAtivo === 'qwen' && <>
          <label>Texto exato da referência (o Qwen precisa saber o que o Thiago diz no trecho; vazio = usa a transcrição salva{refTextoDe(refNova || form?.referencia || '') ? '' : ' — esta referência não tem transcrição salva'})
            <textarea value={refText} onChange={e => setRefText(e.target.value)} rows={2} className="rounded-xl bg-black/40 p-2 w-full outline-none mt-1" placeholder={refTextoDe(refNova || form?.referencia || '') || 'transcreva aqui o trecho da referência'} /></label>
          <label>Temperatura (padrão {form?.qwen.temperatura ?? 0.9}; mais baixa = mais estável, mais alta = mais variada) <input value={qwenNovo.temperatura} onChange={e => setQwenNovo({ ...qwenNovo, temperatura: e.target.value })} className="rounded-full bg-black/40 px-3 py-1 w-20 outline-none" placeholder="0,1–1,5" /></label>
          <label>Top-p (padrão {form?.qwen.top_p ?? 0.9}) <input value={qwenNovo.top_p} onChange={e => setQwenNovo({ ...qwenNovo, top_p: e.target.value })} className="rounded-full bg-black/40 px-3 py-1 w-20 outline-none" placeholder="0,1–1,0" /></label>
          <label>Penalidade de repetição (padrão {form?.qwen.repeticao ?? 1.05}; mais alta evita palavra arrastada) <input value={qwenNovo.repeticao} onChange={e => setQwenNovo({ ...qwenNovo, repeticao: e.target.value })} className="rounded-full bg-black/40 px-3 py-1 w-20 outline-none" placeholder="1,0–1,5" /></label>
        </>}
      </div>}
      {ger?.status === 'rodando' && <div className="text-nevoa text-xs animate-pulse">{ger.etapa || 'gerando…'} (desde {ger.inicio?.slice(11, 19)})</div>}
      {ger?.status === 'erro' && <div className="text-red-300 text-xs">Falhou: {ger.erro}</div>}
      {ger?.status === 'pronto' && ger.amostra && <div className="text-green-300 text-xs">Pronta: {ger.amostra.nome} ({seg(ger.amostra.duracao_s)} em {ger.amostra.tempo_s} s). Ela aparece no topo da lista 1.</div>}
    </div>

    <h3 className="text-lg mt-8">4. Sua decisão</h3>
    {form && <div className="cartao p-4 mt-3 grid gap-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><span className="text-nevoa">Motor da voz do Thiago:</span>
        <label className="flex items-center gap-1"><input type="radio" name="motor" checked={form.motor === 'qwen'} onChange={() => setForm({ ...form, motor: 'qwen' })} className="accent-[#F79615]" />Qwen3-TTS (mais parecido; lento)</label>
        <label className="flex items-center gap-1"><input type="radio" name="motor" checked={form.motor === 'chatterbox'} onChange={() => setForm({ ...form, motor: 'chatterbox' })} className="accent-[#F79615]" />Chatterbox pt-BR (reserva; rápido)</label>
        {salvarPendente && <span className="text-xs text-laranja">mudança ainda não gravada</span>}</div>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.aprovada} onChange={e => setForm({ ...form, aprovada: e.target.checked })} className="accent-[#F79615]" />Aprovo a voz clonada como está (motor <b>{nomeMotor(form.motor)}</b>, referência marcada acima: <b>{form.referencia}</b>)</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.padrao_locucao} onChange={e => setForm({ ...form, padrao_locucao: e.target.checked })} className="accent-[#F79615]" />Usar por padrão nos pedidos de locução e dublagem (o chip “Voz do Thiago” já vem ligado no Novo pedido; dá para desligar em cada pedido)</label>
      <div className="text-nevoa text-xs">Hoje a voz clonada só entra quando o pedido pede (“na voz do Thiago” ou <code>voz_nome="thiago"</code>). Com a opção acima, o Novo pedido manda essa instrução sozinho; a entrega continua dizendo que é voz sintética.</div>
      <textarea value={form.nota} onChange={e => setForm({ ...form, nota: e.target.value })} rows={2} className="rounded-xl bg-black/40 p-3 outline-none" placeholder="Observações (ex.: ficou rápido demais, prefiro mais grave, trocar a referência…)" />
      <button onClick={() => setAvancado(!avancado)} className="text-xs text-nevoa text-left hover:text-white">{avancado ? '▾' : '▸'} Ajuste fino ({form.motor === 'qwen' ? 'parâmetros do Qwen' : 'exagero e cfg do Chatterbox'})</button>
      {avancado && form.motor === 'chatterbox' && <div className="grid gap-2 text-xs text-nevoa">
        <label>Exagero (emoção; 0,5 é o padrão, mais alto = mais expressivo) <input type="range" min={0} max={1} step={0.05} value={form.exagero} onChange={e => setForm({ ...form, exagero: Number(e.target.value) })} className="w-full accent-[#F79615]" /> {form.exagero.toFixed(2)}</label>
        <label>CFG (fidelidade ao texto; 0,5 padrão, mais baixo = mais solto e natural) <input type="range" min={0} max={1} step={0.05} value={form.cfg} onChange={e => setForm({ ...form, cfg: Number(e.target.value) })} className="w-full accent-[#F79615]" /> {form.cfg.toFixed(2)}</label>
      </div>}
      {avancado && form.motor === 'qwen' && <div className="grid gap-2 text-xs text-nevoa">
        <label>Temperatura (0,9 padrão; mais baixa = mais estável e monótona, mais alta = mais viva e arriscada) <input type="range" min={0.1} max={1.5} step={0.05} value={form.qwen.temperatura} onChange={e => setForm({ ...form, qwen: { ...form.qwen, temperatura: Number(e.target.value) } })} className="w-full accent-[#F79615]" /> {form.qwen.temperatura.toFixed(2)}</label>
        <label>Top-p (0,9 padrão) <input type="range" min={0.1} max={1} step={0.05} value={form.qwen.top_p} onChange={e => setForm({ ...form, qwen: { ...form.qwen, top_p: Number(e.target.value) } })} className="w-full accent-[#F79615]" /> {form.qwen.top_p.toFixed(2)}</label>
        <label>Penalidade de repetição (1,05 padrão; mais alta evita sílaba arrastada, alta demais engole palavra) <input type="range" min={1} max={1.5} step={0.01} value={form.qwen.repeticao} onChange={e => setForm({ ...form, qwen: { ...form.qwen, repeticao: Number(e.target.value) } })} className="w-full accent-[#F79615]" /> {form.qwen.repeticao.toFixed(2)}</label>
        <div>Esses valores valem para <code>narrar</code>, <code>montar_locucao</code> e <code>dublar</code> depois de gravar a decisão. Teste antes em “Gerar uma amostra nova”.</div>
      </div>}
      <div className="flex items-center gap-3"><button onClick={salvar} className="btn-laranja px-4 py-2">Gravar decisão</button>{v.decidido_em && <span className="text-nevoa text-xs">última decisão: {v.decidido_em.replace('T', ' ')}</span>}</div>
    </div>}
    <p className="text-nevoa text-xs mt-6">Arquivos: <code>workspace/voz/{v.nome}/</code> (referências, amostras e <code>voz.json</code>; fora do git). Cópia das amostras do piloto também em <code>Claude Code/editor-gs-entregas/2026-10-31-voz-thiago/</code>.</p>
  </div>
}
