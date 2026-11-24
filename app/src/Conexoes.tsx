import { useEffect, useState } from 'react'
import { api, type YoutubeEstado } from './api'

// Conexões do Canva e do YouTube (saíram da página Estilos em 03/11/2026; mesmo comportamento).
export function Conexoes() {
  const [canva, setCanva] = useState<{ configurado: boolean; conectado: boolean; redirect_uri: string; pendencias: string[] } | null>(null)
  const [yt, setYt] = useState<YoutubeEstado | null>(null)
  useEffect(() => { api.canvaEstado().then(setCanva).catch(() => {}); api.youtubeEstado().then(setYt).catch(() => {}) }, [])
  if (!canva && !yt) return null
  return <details className="cartao mt-4 p-4 text-sm">
    <summary className="cursor-pointer font-bold">Conexões: Canva e YouTube <span className="font-normal text-nevoa">{[canva?.conectado && 'Canva ok', yt?.conectado && 'YouTube ok'].filter(Boolean).join(' · ') || 'nada conectado'}</span></summary>
    {canva && <div className="mt-3 flex flex-wrap items-center gap-3"><div><div className="font-bold">Canva</div><div className="text-nevoa text-xs">{canva.conectado ? 'Conectado: o botão "Abrir no Canva" importa o editável e abre direto.' : canva.configurado ? 'Credenciais no lugar. Conecte uma vez (abre a tela do Canva).' : canva.pendencias.join('; ')}</div>{!canva.configurado && <div className="text-nevoa text-xs mt-1">URL de redirecionamento para cadastrar na integração: <code>{canva.redirect_uri}</code></div>}</div>{canva.configurado && <a href="/api/gs/canva/conectar" className="btn-laranja ml-auto px-4 py-1.5">{canva.conectado ? 'Reconectar' : 'Conectar Canva'}</a>}</div>}
    {yt && <div className="mt-3 flex flex-wrap items-center gap-3"><div><div className="font-bold">YouTube (direto, sem Publora)</div><div className="text-nevoa text-xs">{yt.conectado ? `Conectado: canal ${yt.canal?.titulo || ''} ${yt.canal?.handle || ''}. No cartão da entrega, “YouTube” sobe o vídeo privado, não listado, público ou agendado.` : yt.configurado ? 'Credenciais no .env. Clique para autorizar o canal uma vez (login do Google).' : yt.pendencias.join('; ')}</div></div>{yt.configurado && <a href="/api/gs/youtube/conectar" className="ml-auto rounded-full border border-laranja/60 text-laranja px-4 py-1.5 hover:bg-laranja/10">{yt.conectado ? 'Reconectar' : 'Conectar YouTube'}</a>}</div>}
  </details>
}
