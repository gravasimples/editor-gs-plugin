/** Inscrição deste aparelho nas notificações push do gateway (Web Push, chave VAPID própria). */
function b64ToU8(b64: string) { const p = '='.repeat((4 - (b64.length % 4)) % 4); const s = (b64 + p).replace(/-/g, '+').replace(/_/g, '/'); const raw = atob(s); return Uint8Array.from([...raw].map(c => c.charCodeAt(0))) }

export function pushSuportado() { return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window }

export async function pushEstado(): Promise<'sem-suporte' | 'negado' | 'inscrito' | 'nao-inscrito'> {
  if (!pushSuportado()) return 'sem-suporte'
  if (Notification.permission === 'denied') return 'negado'
  const reg = await navigator.serviceWorker.getRegistration(); const sub = await reg?.pushManager.getSubscription()
  return sub ? 'inscrito' : 'nao-inscrito'
}

export async function pushInscrever(): Promise<string> {
  if (!pushSuportado()) throw new Error('Este navegador não aceita notificações (no iPhone, instale o app na Tela de Início primeiro).')
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('Permissão de notificação negada.')
  const reg = await navigator.serviceWorker.ready
  const { chave } = await fetch('/api/gs/push/chave').then(r => r.json())
  let sub = await reg.pushManager.getSubscription()
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToU8(chave) })
  const r = await fetch('/api/gs/push/inscrever', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inscricao: sub.toJSON(), aparelho: navigator.userAgent.slice(0, 120) }) })
  if (!r.ok) throw new Error('O gateway não aceitou a inscrição.')
  return 'Notificações ligadas neste aparelho.'
}

export async function pushSair() {
  const reg = await navigator.serviceWorker.getRegistration(); const sub = await reg?.pushManager.getSubscription()
  if (sub) { await fetch('/api/gs/push/sair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint: sub.endpoint }) }); await sub.unsubscribe() }
}

export async function pushTeste() { return fetch('/api/gs/push/teste', { method: 'POST' }).then(r => r.json()) }
