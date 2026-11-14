// Editor manual (12/11/2026): pacote separado do app porque usa o React 19 do motor (remotion/). O app abre em /editor/?c=<conversa>&p=<projeto>.
import { createRoot } from 'react-dom/client'
import './editor.css'
import { Editor } from './Editor'

const q = new URLSearchParams(location.search)
createRoot(document.getElementById('raiz')!).render(<Editor conversa={q.get('c') || ''} projeto={q.get('p') || ''} />)
