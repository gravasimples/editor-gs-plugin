export type Segmento = { inicio: number; fim: number; texto: string }
export type Estilo = {
  cor_destaque: string; cor_fundo: string; cor_texto: string; fonte_titulo: string; fonte_texto: string
}
// Fase B (07/11/2026): grafismos semânticos (editor_video/grafismos.py normaliza; Grafismos.tsx desenha)
export type Midia = { tipo: 'svg' | 'img'; svg?: string; cor?: string; arquivo?: string; nome?: string; marca?: boolean }
export type GrafismoItem = { texto?: string; em: number; midia?: Midia; rotulo?: string; sinal?: 'ok' | 'nao'; icone?: string }
export type Grafismo = {
  tipo: 'kicker' | 'manchete' | 'pilula' | 'riscado' | 'checklist' | 'pilulas' | 'fluxo' | 'cartoes' | 'numero' | 'logos' | 'ondas' | 'cta' | 'serie'
  inicio: number; fim: number; posicao: 'peito' | 'topo' | 'centro'; tela_cheia?: boolean
  texto?: string; destaque?: string; rotulo?: string; caixa?: boolean; ondas?: boolean; troca?: string; troca_em?: number; sub?: string
  entrada?: 'mola' | 'mascara' | 'desfoque' | 'deslize' | 'elastico' | 'cair' | 'subir'; saida?: 'some' | 'sobe' | 'mascara' | 'encolhe' | 'desfoque' | 'deslize'   // fase E
  antes?: { texto: string; em: number }[]; itens?: GrafismoItem[]; midia?: Midia; handle?: string; botao?: string; parte?: number; kicker?: string
}
// Fase C (07/11/2026): layouts (editor_video/layouts.py normaliza; Layout.tsx desenha)
export type Bloco = { modo: 'cheio' | 'painel' | 'moldura' | 'tutorial' | 'tela' | 'aula' | 'composto'; inicio: number; fim: number }
// 09/11/2026: vídeo vertical composto (tela em cima, rosto embaixo) → no 16:9 tela à esquerda e rosto à direita (editor_video/layouts.py: detectar_composto)
export type Composto = { divisor: number; trechos: { inicio: number; fim: number; composto: boolean }[]; rosto_baixo: { x: number; y: number } | null; rosto_cima: { x: number; y: number } | null }
export type Foco = { inicio: number; fim: number; x: number; y: number; zoom: number; caixa?: number[] }
export type LayoutCfg = {
  blocos: Bloco[]; cortinas_s: number[]
  tela?: string; tela_largura?: number; tela_altura?: number   // gravação de tela em public/render/ (já com os cortes do rosto)
  rosto_recortado?: string                                      // .webm com transparência (aula)
  focos?: Foco[]; passos?: { texto: string; inicio: number }[]
  rosto_pos?: { x: number; y: number }; rosto_largura?: number; rosto_altura?: number  // onde o rosto costuma ficar (0 a 1), para enquadrar as caixas
  composto?: Composto | null                                    // modo composto: linha divisória e trechos (precisa de rosto_largura/rosto_altura)
}
// Fase E (08/11/2026): planos da câmera (editor_video/transicoes.py)
export type Plano = { inicio: number; fim: number; z0: number; z1: number; entrada: string; dur: number; intensidade?: number; virtual?: boolean }
// 10/11/2026: legenda cinética (GSAP SplitText + CustomWiggle dentro do Remotion; acabamento.py monta a partir do palavras_json e do bloco `legenda` do estilo)
export type PalavraLegenda = { texto: string; inicio: number; fim: number; enfase?: boolean }
export type LinhaLegenda = { inicio: number; fim: number; palavras: PalavraLegenda[] }
export type LegendaCineticaCfg = {
  animacao: 'tipografica' | 'maquina' | 'onda'
  tremor: boolean                 // CustomWiggle na palavra de ênfase de cada linha
  linhas: LinhaLegenda[]          // tempos do vídeo cortado (sem a vinheta)
  fonte: string; peso: number; tamanho: number   // px na resolução do render
  cor_texto: string; cor_destaque: string; contorno: string; contorno_px: number
  posicao: 'baixa' | 'centro' | 'alta'; altura_pct?: number | null
  maiusculas: boolean; caixa: boolean; cor_caixa?: string
}
export type MontagemProps = {
  video: string            // nome do arquivo em public/render/
  video_fundo?: string     // fundo desfocado pronto (ffmpeg, tamanho mínimo) quando a orientação muda; sem ele o fundo é desfocado no navegador
  duracao_s: number        // duração do vídeo cortado
  fps: number
  largura: number
  altura: number
  largura_origem?: number
  altura_origem?: number
  segmentos: Segmento[]    // tempos do vídeo cortado (para o zoom por frase)
  cortes_s: number[]       // instantes (s) dos pontos de corte (para o clarão)
  zoom: { ativo: boolean; fator: number; alternar: boolean }
  clarao: { ativo: boolean; duracao_s: number; opacidade: number }
  frase_impacto: { texto: string; destaque: string; duracao_s: number; animacao?: 'bloco' | 'palavra' } | null
  tela_final: { ativo: boolean; duracao_s: number; titulo: string; destaque: string; cta: string; marca: string; selo?: string; ondas?: boolean; chamada?: string } | null  // selo/ondas/chamada: cartela da série
  vinheta?: { ativo: boolean; duracao_s: number; titulo: string; destaque: string } | null   // abertura de marca (cartão marinho + barra laranja) antes do vídeo
  terco?: { texto: string; sub: string; inicio_s: number; duracao_s: number } | null          // terço inferior animado (nome + descrição), em cima do vídeo
  // Nível profissional (02/11/2026)
  palavras_chave?: { texto: string; inicio: number; fim: number }[]                          // palavra-chave animada na tela, sincronizada com a fala (tempos do vídeo cortado)
  capitulos?: { texto: string; inicio: number; numero?: number; total?: number }[]           // "1/3 · Áudio": pílula no alto por ~2,5 s a partir de `inicio`
  barra_progresso?: boolean                                                                   // linha laranja na base que cresce com o tempo
  broll?: { arquivo: string; inicio: number; duracao_s: number; modo: 'cheio' | 'janela'; video?: boolean }[]  // cutaway (imagem ou vídeo em public/render/) com zoom lento
  sfx?: { arquivo: string; inicio: number; volume: number }[]                                 // efeitos sonoros (public/sfx/) nos tempos do vídeo cortado
  grafismos?: Grafismo[]                                                                      // plano semântico (substitui palavras_chave quando presente)
  layout?: LayoutCfg | null                                                                   // blocos de layout, câmera virtual, passos e cortina
  camera?: { planos: Plano[]; origem?: { x: number; y: number } } | null                      // fase E: substitui zoom/clarão/ritmo quando presente
  ritmo_zoom_s?: number                                                                       // pattern interrupt: troca o enquadramento a cada N s mesmo sem fim de frase
  legenda_cinetica?: LegendaCineticaCfg | null                                                // 10/11/2026: legenda animada no Remotion (sem legenda_ass); some nos trechos de tela cheia
  previa_trechos?: { src: string; trechos: { inicio: number; fim: number }[] } | null              // 12/11/2026: só no editor manual (prévia da EDL editada direto do bruto); o render nunca recebe
  camada?: 'tudo' | 'base' | 'graficos' | 'legenda'                                           // 12/11/2026: exportação para o CapCut (capcut.py): só o vídeo, só os grafismos (fundo transparente) ou só a legenda
  estilo: Estilo
}
export type CenaTextoProps = {
  duracao_s: number; fps: number; largura: number; altura: number
  titulo: string; destaque: string; apoio: string[]
  fundo: 'marinho' | 'papel'          // marinho (padrão) ou papel (claro), como os slides do carrossel
  animacao: 'palavras' | 'linhas' | 'nenhuma'
  selo?: string
  estilo: Estilo
}
