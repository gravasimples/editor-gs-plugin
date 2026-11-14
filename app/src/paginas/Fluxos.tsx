import { useEffect, useState } from 'react'
import { api, type Fluxo } from '../api'
const FIXOS = ['reels-padrao', 'referencia-analise', 'minha-versao', 'cortes-longos', 'carrossel']
const SUGESTOES = ['corte dinâmico sem erros e pausas', 'legenda karaokê no estilo padrão', 'zoom por frase e clarão nas transições', 'capa com o gancho e tela final com CTA', 'entrega em vertical e 16:9', 'projeto do CapCut', 'só legendar, sem cortar', 'trilha leve por baixo da voz']
export default function Fluxos() {
  const [fluxos, setFluxos] = useState<Fluxo[]>([])
  const [novo, setNovo] = useState(false); const [nome, setNome] = useState(''); const [desc, setDesc] = useState(''); const [passos, setPassos] = useState(''); const [erro, setErro] = useState('')
  const carregar = () => api.fluxos().then(setFluxos).catch(() => {})
  useEffect(() => { carregar() }, [])
  async function salvar() { setErro(''); try { await api.novoFluxo(nome, desc, passos); setNovo(false); setNome(''); setDesc(''); setPassos(''); carregar() } catch (e: any) { setErro(e.message) } }
  async function apagar(n: string) { if (!confirm(`Apagar o fluxo ${n}?`)) return; try { await api.apagarFluxo(n); carregar() } catch (e: any) { setErro(e.message) } }
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <div className="flex items-center gap-3"><h2 className="text-2xl">Fluxos</h2><button onClick={() => setNovo(!novo)} className="btn-laranja ml-auto px-4 py-2 text-sm">{novo ? 'Fechar' : '+ Novo fluxo'}</button></div>
    <p className="text-nevoa mt-2">Um fluxo é um pedido pronto. Se você sempre pede a mesma coisa, salve aqui uma vez e depois é só mandar o vídeo e escolher o fluxo. Na conversa também dá para pedir "salva esse jeito de editar como fluxo".</p>
    {novo && <div className="cartao p-4 mt-5 grid gap-3">
      <input value={nome} onChange={e => setNome(e.target.value)} placeholder="Nome (ex.: Reels do celular)" className="rounded-xl bg-black/40 p-3 outline-none" />
      <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="Uma linha sobre quando usar" className="rounded-xl bg-black/40 p-3 outline-none" />
      <textarea value={passos} onChange={e => setPassos(e.target.value)} rows={6} placeholder={"O que o editor deve fazer, em passos:\n1. …\n2. …"} className="rounded-xl bg-black/40 p-3 outline-none resize-none" />
      <div className="flex flex-wrap gap-2 text-xs">{SUGESTOES.map(s => <button key={s} onClick={() => setPassos(p => (p ? p + '\n' : '') + `${(p.match(/\n/g) || []).length + (p ? 2 : 1)}. ${s}`)} className="selo hover:bg-azul/40">{s}</button>)}</div>
      <div className="flex items-center gap-2"><button onClick={salvar} disabled={!nome.trim() || !passos.trim()} className="btn-laranja px-4 py-2 text-sm">Salvar fluxo</button>{erro && <span className="text-sm text-red-300">{erro}</span>}</div>
    </div>}
    <div className="grid gap-3 mt-6">{fluxos.map(f => <details key={f.nome} className="cartao p-4"><summary className="cursor-pointer font-bold">{f.titulo}<span className="block text-sm text-nevoa font-normal mt-1">{f.descricao}</span></summary><pre className="whitespace-pre-wrap text-sm text-nevoa mt-3">{f.conteudo}</pre>{!FIXOS.includes(f.nome) && <button onClick={() => apagar(f.nome)} className="mt-3 text-xs text-nevoa hover:text-red-300">Apagar fluxo</button>}</details>)}</div>
  </div>
}
