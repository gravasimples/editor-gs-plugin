import { useEffect, useState } from 'react'
import { pushEstado, pushInscrever, pushSair, pushTeste } from '../push'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'

type Celular = { disponivel: boolean; aparelhos: { nome: string; online: boolean; visto: string | null; os: string }[]; serve: string | null; erro?: string }

export default function Ajuda() {
  const [guias, setGuias] = useState<{ nome: string; titulo: string; conteudo: string }[]>([])
  const [atalho, setAtalho] = useState<{ url: string; base: string; app: string } | null>(null); const [copiado, setCopiado] = useState('')
  const [cel, setCel] = useState<Celular | null>(null)
  const [params] = useSearchParams(); const deAtalho = params.get('de') === 'atalho'
  useEffect(() => { api.ajuda().then(setGuias).catch(() => {}); api.atalho().then(setAtalho).catch(() => {}); api.celular().then(setCel).catch(() => {}) }, [])
  async function copiar(t: string, k: string) { try { await navigator.clipboard.writeText(t); setCopiado(k); setTimeout(() => setCopiado(''), 2000) } catch {} }
  async function novo() { if (!confirm('Gerar um link novo? O atalho antigo do celular para de funcionar.')) return; setAtalho(await api.atalhoNovo()) }
  const app = atalho?.app || window.location.origin
  const fone = cel?.aparelhos.filter(a => a.os !== 'windows') || []
  const [pushSt, setPushSt] = useState<string>('…'); const [pushMsg, setPushMsg] = useState('')
  useEffect(() => { pushEstado().then(setPushSt).catch(() => setPushSt('sem-suporte')) }, [])
  async function ligarPush() { setPushMsg(''); try { setPushMsg(await pushInscrever()); setPushSt(await pushEstado()) } catch (e: any) { setPushMsg(e.message) } }
  async function desligarPush() { await pushSair(); setPushSt(await pushEstado()); setPushMsg('Notificações desligadas neste aparelho.') }
  return <div className="max-w-3xl mx-auto px-4 py-8">
    <h2 className="text-2xl">Ajuda</h2><p className="text-nevoa mt-2">Como abrir o app no celular, o atalho de compartilhar e os guias de configuração (texto de <code>docs/*.md</code>).</p>

    <div className="cartao p-4 mt-6 text-sm">
      <div className="font-bold text-base">🔔 Avisos no celular (notificações)</div>
      <p className="text-nevoa mt-1">O app avisa quando uma entrega fica pronta, quando o Editor precisa da sua decisão (plano de cenas, cortes) e quando um pedido trava. Ligue em cada aparelho; no iPhone só funciona com o app instalado na Tela de Início.</p>
      <div className="flex flex-wrap items-center gap-2 mt-3">
        {pushSt === 'inscrito' ? <><span className="rounded-full bg-green-500/20 text-green-300 px-3 py-1 text-xs">ligadas neste aparelho</span><button onClick={() => pushTeste().then(r => setPushMsg(`Teste enviado para ${r.enviadas} aparelho(s).`))} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">Mandar um teste</button><button onClick={desligarPush} className="rounded-full border border-white/15 px-3 py-1.5 hover:bg-white/5">Desligar aqui</button></>
          : pushSt === 'negado' ? <span className="text-red-300">Você negou notificações para este site; libere nas configurações do navegador e volte aqui.</span>
          : pushSt === 'sem-suporte' ? <span className="text-nevoa">Este navegador não aceita notificações (no iPhone, instale o app primeiro).</span>
          : <button onClick={ligarPush} className="btn-laranja px-4 py-2">Ligar notificações neste aparelho</button>}
      </div>
      {pushMsg && <div className="text-xs mt-2 text-laranja">{pushMsg}</div>}
    </div>

    <div className="cartao p-4 mt-6 text-sm border border-laranja/40">
      {deAtalho && <div className="rounded-xl bg-laranja/15 border border-laranja/40 p-3 mb-3 text-sm">Você abriu no navegador o <b>link secreto do atalho</b>. Ele não é o app: só recebe material do Atalho do iPhone ou do HTTP Shortcuts (POST). O endereço do app é o de baixo.</div>}
      <div className="font-bold text-base">Abrir o Editor GS no celular</div>
      <div className="flex flex-wrap gap-4 mt-3 items-start">
        <img src={`/api/gs/qr?texto=${encodeURIComponent(app)}`} alt="QR code do endereço do app" className="w-40 h-40 rounded-xl bg-white p-1" />
        <div className="flex-1 min-w-[220px]">
          <div className="flex flex-wrap items-center gap-2"><code className="rounded-lg bg-black/30 px-2 py-1 text-sm break-all">{app}</code><button onClick={() => copiar(app, 'app')} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">{copiado === 'app' ? 'Copiado' : 'Copiar'}</button></div>
          <ol className="list-decimal pl-5 mt-3 grid gap-1 text-nevoa">
            <li><b className="text-white">Tailscale ligado no celular</b>, na conta <code>raphaelpullig@</code> (a mesma do notebook). O ícone de VPN fica na barra. No Android, deixe o Tailscale sem otimização de bateria e com “VPN sempre ativa”, senão ele cai em segundo plano.</li>
            <li>Aponte a câmera para o QR (ou digite o endereço) e abra no Chrome ou Safari. Esse endereço só funciona com o Tailscale ligado; sem ele dá “site não encontrado”.</li>
            <li>Instale: Chrome → menu ⋮ → <b className="text-white">Instalar app</b>; iPhone → Compartilhar → <b className="text-white">Adicionar à Tela de Início</b>.</li>
            <li>Se abrir uma versão antiga, aparece a faixa laranja <b className="text-white">Nova versão → Atualizar</b> no topo. Se não aparecer, feche o app e abra de novo (a checagem roda a cada minuto e ao voltar para o app).</li>
          </ol>
          {cel && <div className="mt-3 text-xs rounded-xl bg-black/30 p-2">
            {!cel.disponivel ? <span className="text-nevoa">Estado do Tailscale indisponível{cel.erro ? ` (${cel.erro})` : ''}.</span> : <>
              <div>Tailscale no notebook: {cel.serve ? <span className="text-green-300">servindo o app em {cel.serve}</span> : <span className="text-red-300">sem `tailscale serve` para a porta 3200</span>}</div>
              {fone.length === 0 ? <div className="text-red-300">Nenhum celular na conta Tailscale ainda: instale o app Tailscale no celular e entre com a mesma conta.</div>
                : fone.map(a => <div key={a.nome}>Celular <b>{a.nome}</b> ({a.os}): {a.online ? <span className="text-green-300">conectado agora</span> : <span className="text-red-300">desconectado{a.visto ? ` (visto ${new Date(a.visto).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })})` : ''} → ligue o Tailscale no celular</span>}</div>)}
            </>}</div>}
        </div>
      </div>
    </div>

    <div className="cartao p-4 mt-4 text-sm">
      <div className="font-bold">Atalho do celular (link secreto, só para mandar material)</div>
      <div className="text-nevoa text-xs mt-1">Para o Atalho do iPhone ou o HTTP Shortcuts do Android mandarem vídeo, foto ou link sem abrir o app. Não é para abrir no navegador. POST com formulário: <code>acao</code> = <code>pedido</code> (abre o Novo pedido com o material) ou <code>anotacao</code> (guarda em Ideias → Anotações), <code>texto</code> e <code>arquivos</code>. Quem tiver o link consegue mandar material; só funciona com o Tailscale ligado.</div>
      {atalho ? <div className="flex flex-wrap items-center gap-2 mt-3"><code className="rounded-lg bg-black/30 px-2 py-1 text-xs break-all">{atalho.url}</code><button onClick={() => copiar(atalho.url, 'atalho')} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">{copiado === 'atalho' ? 'Copiado' : 'Copiar'}</button><button onClick={novo} className="rounded-full border border-white/15 px-3 py-1 text-xs hover:bg-white/5">Gerar novo link</button>{!atalho.base && <span className="text-red-300 text-xs">EDITOR_GS_URL_PUBLICA vazio no .env</span>}</div> : <div className="text-nevoa text-xs mt-2">…</div>}
    </div>
    <div className="grid gap-3 mt-6">{guias.map(g => <details key={g.nome} className="cartao p-4"><summary className="cursor-pointer font-bold">{g.titulo}</summary><pre className="whitespace-pre-wrap text-sm text-nevoa mt-3 font-[Inter]">{g.conteudo}</pre></details>)}</div>
    {guias.length === 0 && <p className="text-nevoa mt-6">Nenhum guia encontrado (o gateway precisa estar no ar).</p>}
  </div>
}
