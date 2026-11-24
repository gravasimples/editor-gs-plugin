/* Notificações push do Editor GS (importado pelo service worker gerado pelo Workbox). */
self.addEventListener('push', (e) => {
  let d = {}
  try { d = e.data ? e.data.json() : {} } catch { d = { titulo: 'Editor GS', corpo: e.data ? e.data.text() : '' } }
  const titulo = d.titulo || 'Editor GS'
  e.waitUntil(self.registration.showNotification(titulo, { body: d.corpo || '', icon: '/icone-192.png', badge: '/icone-192.png', tag: d.tag || 'editor-gs', renotify: true, data: { url: d.url || '/' } }))
})
self.addEventListener('notificationclick', (e) => {
  e.notification.close()
  const url = (e.notification.data && e.notification.data.url) || '/'
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((lista) => {
    for (const c of lista) { if ('focus' in c) { c.navigate(url); return c.focus() } }
    return self.clients.openWindow(url)
  }))
})
