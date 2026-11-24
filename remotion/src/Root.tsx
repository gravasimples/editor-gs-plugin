import { Composition } from 'remotion'
import { Montagem } from './Montagem'
import { CenaTexto } from './CenaTexto'
import type { CenaTextoProps, MontagemProps } from './tipos'

const estilo = { cor_destaque: '#F79615', cor_fundo: '#000921', cor_texto: '#FFFFFF', fonte_titulo: 'InterGS', fonte_texto: 'InterGS' }

const padrao: MontagemProps = {
  video: 'amostra.mp4', duracao_s: 10, fps: 30, largura: 720, altura: 1280, segmentos: [], cortes_s: [],
  zoom: { ativo: true, fator: 1.08, alternar: true }, clarao: { ativo: true, duracao_s: 0.22, opacidade: 0.85 },
  frase_impacto: { texto: 'O óbvio precisa ser dito', destaque: 'óbvio', duracao_s: 2.6 },
  tela_final: { ativo: true, duracao_s: 3, titulo: 'Aprenda a gravar de forma simples', destaque: 'simples', cta: 'Siga o perfil', marca: 'GRAVA SIMPLES' },
  estilo,
}

const cenaPadrao: CenaTextoProps = {
  duracao_s: 5, fps: 30, largura: 720, altura: 1280, titulo: 'Sua webcam trava no OBS?', destaque: 'trava',
  apoio: ['Desliga o driver antigo', 'Liga de novo e pronto'], fundo: 'marinho', animacao: 'palavras', selo: '', estilo,
}

export const Root = () => (
  <>
    <Composition id="Montagem" component={Montagem} defaultProps={padrao} fps={30} width={720} height={1280} durationInFrames={300}
      calculateMetadata={async ({ props }) => {
        const extra = (props.tela_final && props.tela_final.ativo ? props.tela_final.duracao_s : 0) + (props.vinheta && props.vinheta.ativo ? props.vinheta.duracao_s : 0)
        return { fps: props.fps, width: props.largura, height: props.altura, durationInFrames: Math.ceil((props.duracao_s + extra) * props.fps) }
      }} />
    <Composition id="CenaTexto" component={CenaTexto} defaultProps={cenaPadrao} fps={30} width={720} height={1280} durationInFrames={150}
      calculateMetadata={async ({ props }) => ({ fps: props.fps, width: props.largura, height: props.altura, durationInFrames: Math.max(1, Math.ceil(props.duracao_s * props.fps)) })} />
  </>
)
