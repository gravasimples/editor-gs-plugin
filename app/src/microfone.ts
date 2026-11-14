import { useEffect, useRef, useState } from 'react'
// Ditado em pt-BR pela Web Speech API (Chrome/Android; Safari parcial). Sem suporte, o botão não aparece.
export function useMicrofone(onTexto: (t: string) => void) {
  const [gravando, setGravando] = useState(false)
  const [suportado, setSuportado] = useState(false)
  const rec = useRef<any>(null)
  useEffect(() => { const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition; setSuportado(!!SR) }, [])
  function alternar() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return
    if (gravando) { rec.current?.stop(); setGravando(false); return }
    const r = new SR(); r.lang = 'pt-BR'; r.continuous = true; r.interimResults = false
    r.onresult = (e: any) => { let t = ''; for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) t += e.results[i][0].transcript + ' '; if (t.trim()) onTexto(t.trim()) }
    r.onend = () => setGravando(false); r.onerror = () => setGravando(false)
    rec.current = r; r.start(); setGravando(true)
  }
  return { gravando, suportado, alternar }
}
