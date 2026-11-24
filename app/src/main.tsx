import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { registerSW } from 'virtual:pwa-register'

// autoUpdate: o service worker novo assume e a página recarrega sozinha; aqui só garantimos que a checagem
// aconteça a cada minuto e sempre que o app volta para a frente (o PWA do celular ficava preso na versão antiga)
registerSW({ immediate: true, onRegisteredSW(_url, r) { if (!r) return; const checar = () => r.update().catch(() => {}); setInterval(checar, 60_000); document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') checar() }) } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
