export type Conversa = { id: string; codigo: string; titulo: string; status: string; atualizado: string; criado: string; slug: string | null; executando: boolean; pasta?: string | null; notion_page?: string | null; modelo?: { id: string; rotulo: string }; reservas?: { de: string; para: string; quando: string; motivo: string }[]; drive?: { estado: 'baixando' | 'pronto' | 'erro'; nomes: string[]; erro?: string; quando: string } | null; excluida?: string | null }
export type CartaoNotion = { id: string; titulo: string; status: string | null; formato: string[]; url: string | null }
export type DriveItem = { raiz: string; caminho: string; nome: string; tipo: string; tamanho_mb: number }
export type DrivePasta = { raiz: string; rotulo: string; caminho: string; pastas: { nome: string; caminho: string }[]; arquivos: { nome: string; caminho: string; tipo: string; tamanho_mb: number; modificado: string | null; baixavel: boolean }[] }
export type Pasta = { nome: string; criada: string | null; n: number }
export type Secao = { titulo: string; conteudo: string }
export type FonteMd = { arquivo: string; existe: boolean; atualizado: string | null; secoes: Secao[] }
export type Oferta = { id: string; nome: string | null; preco: number | null; moeda: string; parcelas: number | null; valor_parcela: number | null; acesso: string | null; url: string | null; visto_em: string; status: string; confianca: number | null; notas: string | null }
export type Produto = { slug: string; nome: string; apelidos: string[]; categoria: string | null; componentes: string[]; publico: string | null; problema: string | null; promessa: string | null; entregaveis: string[]; status: string; confianca: number | null; fonte: string; pendencias: string[]; notas: string | null; ofertas: Oferta[] }
export type Marca = { manual: FonteMd; voz: FonteMd; produtos_md: FonteMd; produtos: { itens: Produto[]; n_ofertas?: number; aviso?: string; erro?: string }; gerado_em: string; arquivos?: string[]; destino?: string }
export type Mensagem = { id: string; autor: 'editor' | 'voce' | 'app'; texto: string; quando: string }
export type SecaoTexto = { chave: string; titulo: string; conteudo: string }
export type TextoItem = { id: string; codigo: string; titulo: string; slug: string | null; pasta: string | null; status: string; quando: string; secoes: SecaoTexto[]; guardadas: string[] }
export type TextoGuardado = { nome: string; titulo: string; codigo: string | null; chave: string | null; quando: string; conteudo: string }
export type Entrega = { nome: string; caminho: string; url: string; tipo: string; tamanho_mb: number; modificado: string; principal: boolean }
export type ConversaDetalhe = Conversa & { trabalho?: { minutos: number; rodadas: number; em_andamento: boolean } | null; peca?: PecaEtiquetas | null; editor_status: string; mensagens: Mensagem[]; entregas: Entrega[]; relatorio: string | null; post: Record<string, string> | null; post_origem: 'arquivo' | 'mensagem' | null; textos: SecaoTexto[]; interacoes: Interacao[]; capcut: { nome: string; projeto: string; n_segmentos: number; n_legendas: number; criado_em: string } | null; economia?: Economia | null }
export type Interacao = { id: string; tipo: string; titulo: string; resumo: string; pergunta: string | null; opcoes: any[]; status: string }
export type Ideia = { id: string; titulo: string; descricao?: string | null; status: string; zona?: string; familia?: string; formato?: string | string[] | null; publico?: string | null; novidade?: number; saturacao?: string; reforcos?: number; atualizado: string; origem?: 'notion'; fila?: string[]; material?: string | null; prioridade?: string | null; url?: string | null; roteiro?: boolean; motivo?: string[]; notion_url?: string }
export type Recebido = { token: string; texto: string; quando: string | null; arquivos: { nome: string; tipo: string; tamanho_mb: number }[] }
export type Conta = { platformId: string; plataforma: string; usuario: string | null; nome: string | null; status: string | null; token: string | null }
export type YoutubeEstado = { configurado: boolean; conectado: boolean; canal: { id: string; titulo: string; handle: string | null; inscritos: string | null } | null; redirect_uri: string; pendencias: string[]; cota: string }
export type PublicarEstado = { publora: { configurado: boolean; contas: Conta[]; pendencias: string[] }; drive: { configurado: boolean; destino: string; pendencias: string[] }; youtube: YoutubeEstado }
export type Destaque = { video_id: string; titulo: string; url: string; canal: string; handle: string; tipo_fonte: string; categoria: string | null; publicado: string; duracao_s: number | null; formato: string | null; views: number; mediana_canal: number; razao: number }
export type Publicacao = { quando: string; tipo: 'publora' | 'drive' | 'youtube'; video_id?: string; url?: string; privacidade?: string; publishAt?: string | null; views?: string; capa_erro?: string; erro_status?: string; titulo?: string; arquivo?: string; capa?: string | null; capa_arquivo?: string; plataformas?: string[]; postGroupId?: string; status?: string; scheduledTime?: string | null; posts?: { plataforma: string; status: string; permalink: string | null; erro?: string | null }[]; destino?: string; arquivos?: string[]; link?: string | null }
export type Referencia = { id: string; criado: string; nota: string; url: string; plataforma: string; status: 'baixando' | 'pronto' | 'erro'; titulo: string; autor: string | null; duracao_s: number | null; video: string | null; capa: string | null; erro: string | null; analise: string | null; arquivos: string[]; pedidos: { tipo: string; issue_id: string; codigo: string; quando: string }[]; visualizacoes?: number | null; curtidas?: number | null; publicado?: string | null; descricao_origem?: string }
export type Concorrente = { id: string; plataforma: string; handle: string | null; nome: string | null; tipo: string | null; categoria: string | null; notas: string | null; ativo: boolean; itens: number; ultimo: string | null; url: string | null }
export type Corte = { id: string; inicio: number; fim: number; duracao: number; titulo?: string; gancho?: string; destaque?: string; motivo?: string; tema?: string; tipo?: string; nota?: number; pessoas?: string; editado?: { issue_id: string; codigo: string; slug: string; quando: string } | null }
export type Cortes = { slug: string; pronto: boolean; origem?: string; tipo_origem?: string; duracao_s?: number; cortes: Corte[] }
export type CalendarioItem = { dia: string; hora?: string | null; tipo: string; titulo: string; origem: 'publora' | 'youtube' | 'instagram' | 'notion'; plataformas?: string[]; url?: string; notion_url?: string; status?: string | null; formato?: string | string[] | null; slug?: string }
export type Comentario = { id: string; plataforma: string; texto: string; autor: string; likes: number; quando: string; conteudo: string; item_id: string; url: string; respondido: boolean }
export type ResumoRes = { conteudos: number; views: number; likes: number; comentarios: number; views_mediana: number; engajamento_medio: number | null }
export type ItemRes = { plataforma: string; id: string; titulo: string; url: string; publicado: string; views: number; likes: number; comentarios: number; engajamento: number | null; formato: string | null; tema: string | null; vs_mediana_formato: number | null }
export type Resultados = { dias: number; inicio: string; fim: string; ultima_medicao: string | null; total: ResumoRes; anterior: ResumoRes; formatos: (ResumoRes & { formato: string })[]; top: ItemRes[]; itens: ItemRes[]; nota?: string }
export type Armazenamento = { pastas_mb: Record<string, number>; total_mb: number; trabalho_mb: number; anteriores_mb: number; limpeza: { dias: number; candidatos: { slug: string; pasta: string; mb: number; ultimo_uso: string }[]; mb: number }; disco: { livre_gb: number; total_gb: number } }
export type Economia = { minutos: number; fluxo: string; video_s: number | null; itens: number | null; base: string }
export type EconomiaTotal = { periodos_min: Record<string, number>; total_min: number; n_entregas: number; por_fluxo: Record<string, number>; nota: string }
export type UsoEntrega = { publora: number; youtube: number; drive: number; rotulo: string; ultimo: string | null }
export type UsoAgente = { pedidos_30d: number; concluidos_30d: number; em_andamento: number; duracao_media_min: number | null }
export type Uso = { periodos: Record<string, { criados: number; concluidos: number }>; por_agente?: Record<string, UsoAgente>; em_andamento: number; na_fila: number; aguardando_voce: number; duracao_media_min: number | null; n_medidos: number; nota: string; economia?: EconomiaTotal }
export function horas(min: number): string { const h = Math.floor(min / 60), m = Math.round(min % 60); return h ? `${h} h${m ? ` ${m} min` : ''}` : `${m} min` }
export type Avulso = { nome: string; caminho: string; tipo: string; tamanho_mb: number; modificado: string }
export type Anotacao = { id: string; quando: string; texto: string; links: string[]; arquivos: string[]; origem: string; titulo: string; status?: 'a_fazer' | 'em_producao' | 'feita'; pedido?: string | null; mudou_em?: string }
export type VozReferencia = { nome: string; url: string; duracao_s: number | null; origem: string | null; texto: string | null; nivel_db: number | null; cobertura: number | null }
export type VozAmostra = { nome: string; url: string; duracao_s: number | null; texto: string | null; referencia: string | null; motor?: string; modelo: string; quando: string; tempo_s: number | null; origem: string; nota: string | null; medidas?: { ve?: number; teto_ve?: number; f0_hz?: number; f0_desvio_st?: number; ritmo_pps?: number; alvo_f0_hz?: number; alvo_f0_desvio_st?: number; alvo_ritmo_pps?: number } | null }
export type Voz = { nome: string; referencia: string | null; motor: 'qwen' | 'chatterbox'; motor_nome: string; qwen: { temperatura: number; top_p: number; repeticao: number }; ref_text: string | null; exagero: number; cfg: number; temperatura: number; rotulo: string; aprovada: boolean; padrao_locucao: boolean; nota: string; decidido_em: string | null; referencias: VozReferencia[]; amostras: VozAmostra[]; disponivel: boolean }
export type Etiquetas = { campanha?: string; pilar?: string; gancho?: string; formato?: string; cta?: string; voz?: string; origem?: string; redes?: string[]; nota?: string }
export type PecaEtiquetas = { etiquetas: Etiquetas; auto: Etiquetas; humanas: Etiquetas; atualizado: string | null; por: string | null }
export type PecaLinha = { slug: string; titulo: string; conversa: string | null; codigo: string | null; pasta: string | null; modificado: string; etiquetas: Etiquetas; estado: string; publicado_em: string | null; views: number | null; vs_mediana: number | null; plataforma: string | null; medido_em: string | null; alertas?: number }
export type PecaOpcoes = { campanhas: string[]; pilares: string[]; ctas: string[]; formatos: string[]; vozes: string[]; origens: string[]; redes: string[] }
export type Ativo = { arquivo: string; origem: string; licenca: 'proprio' | 'cc0' | 'pexels' | 'pixabay' | 'cc-by' | 'nc' | 'desconhecida'; atribuicao: string | null; url: string | null; autor?: string | null }
export type AlertaAtivo = { arquivo: string; tipo: 'cc-by-sem-credito' | 'nc' | 'desconhecida'; msg: string }
export type PecaFicha = PecaEtiquetas & { slug: string; conversa: { id: string | null; codigo: string | null; titulo: string | null; pasta: string | null; status: string | null; notion_page: string | null }; textos: Record<string, string>; arquivos: Entrega[]; publicacoes: any[]; ids_publicados: { plataforma: string; id: string }[]; metricas: any[]; estado: string; ativos: Ativo[]; alertas: AlertaAtivo[] }
export type Checkpoint = { n: number; quando: string; rodada: number | null; motivo: string | null; arquivos: number; bytes: number; resumo: string; pasta: string }
export type Desfeito = { n: number; quando: string; rodada: number | null; restaurados: string[]; apagados: string[]; iguais: string[]; faltando: string[]; checkpoint_novo: Checkpoint | null; slug: string; mensagem: string }
export type Posmortem = { slug: string; titulo: string | null; codigo: string | null; publicado_em: string | null; idade_dias: number | null; gerado_em: string; plataforma: string; views: number; likes: number; comentarios: number; mediana_formato: number | null; razao: number | null; formato_gsi: string | null; etiquetas: Etiquetas; veredito: string; hipotese: string; status_aprendizado: string }
export type Automacao = { id: string; grupo: string; nome: string; ligada: boolean; estado: string; detalhe: string; ultima: string | null; ultimo_arquivo: string | null; onde: string; precisa?: string; tamanho?: string; decidido_em?: string | null; existe?: boolean; config?: StoriesConfig }
export type StoriesConfig = { serie: string; dia_semana: number; hora: number; contas: string[]; plataformas: string[] }
export type SkillItem = { id: string; nome: string; tipo: string; url: string; autor: string; licenca: string; preco: string; resumo: string; o_que_aproveitar: string[]; como_reproduzir: string; evidencia: string; estado: string; achado_em: string; achado_por: string; fonte: string; notas: { quando: string; por: string; texto: string }[]; tags: string[]; decidido_por?: string; decidido_em?: string; instalacao?: { pasta: string; skill: string; quando: string } }
export type SkillsEstado = { n: number; por_estado: Record<string, number>; rodadas: { id: string; quando: string; por: string; foco?: string; codigo?: string; issue?: string; estado: string; novos?: number }[]; pesquisa_devida: boolean; pesquisa_motivo: string; instaladas: { pasta: string; descricao: string; arquivos: number }[]; conhecimento: { arquivo: string; titulo: string; tamanho: number; quando: string }[]; tipos: Record<string, string>; estados: string[] }
export type AcervoFonte = { id: string; origem: 'gsi' | 'app'; plataforma: string; titulo: string; url: string | null; data: string; formato: string | null; duracao_s: number | null; slug: string | null; conversa: string | null; codigo?: string | null }
export type AcervoHit = { fonte: AcervoFonte; video_local: boolean; inicio: number; fim: number; trecho: string; antes: string; depois: string; pontos: number; link: string | null; corte_sugerido: { inicio: number; fim: number }; instante?: number; instante_tipo?: 'exato' | 'aproximado' | 'inicio_da_frase'; embed?: string | null }
export type AcervoBusca = { q: string; resultados: AcervoHit[]; fontes: { total: number; gsi: number; app: number; youtube: number; instagram: number; com_video_local: number }; nota: string }
export type Gancho = { gancho: string; origem: 'app' | 'experimento' | 'youtube' | 'instagram'; plataforma: string | null; formato: string | null; fonte: string | null; codigo: string | null; slug: string | null; url: string | null; data: string; views: number | null; razao: number | null; estado: string; pilar?: string; campanha?: string; papel?: string; pedido: string }
export type TipoGancho = { tipo: string; rotulo: string; n: number; medidos: number; razao_media: number | null; razao_mediana: number | null; melhor: string | null; melhor_razao: number | null; pouca_amostra: boolean }
export type Ganchos = { tipos: TipoGancho[]; itens: (Gancho & { tipo?: string })[]; resumo: { total: number; medidos: number; acima: number; abaixo: number; por_origem: Record<string, number> }; nota: string }
export type RecicladoConfig = { cada_dias: number; hora: number; min_razao: number; min_idade_dias: number; min_duracao_s: number; max_duracao_s: number; plataformas: string[]; contas: string[]; voz_clonada: boolean; tentativas: number; temas: string[] }
export type Candidato = { plataforma: string; id: string; url: string | null; titulo: string; legenda: string; gancho: string | null; publicado: string; idade_dias: number | null; duracao_s: number | null; views: number | null; razao: number | null; mediana: number | null; origem: 'gsi' | 'app'; arquivo: string | null; slug_origem: string | null; codigo_origem: string | null }
export type Rodada = { id: string; automacao: string; serie?: string; quando: string; semana?: string; por?: string; fonte: ({ plataforma: string; id: string; texto: string; topicos: string[]; likes: number; quando: string; contexto?: string } & Partial<Candidato>) | null; arquivo?: string; gancho_novo?: string; gancho_original?: string; issue?: string | null; codigo?: string | null; slug?: string | null; estado: string; publora?: { postGroupId?: string; status?: string; contas?: string[] } | null; legenda?: string; historico?: { quando: string; estado: string; nota?: string }[] }
export type Rodadas = { rodadas: Rodada[]; config: StoriesConfig; dias: string[]; proxima: string; devida: boolean; motivo: string; series: Record<string, { nome: string; descricao: string }>; publora: boolean; reciclado: { config: RecicladoConfig; proxima: string; devida: boolean; motivo: string; candidatos: Candidato[] } }
export type Revisao = { avisos: { gravidade: 'alta' | 'media' | 'baixa'; regra: string; campo: string; trecho: string; msg: string }[]; resumo: { alta: number; media: number; baixa: number }; ok: boolean; nota?: string }
export type AprovacaoEntrega = { tipo: 'entrega'; id: string; codigo: string | null; titulo: string; slug: string; status: string; atualizado: string; pasta?: string | null; video: Entrega | null; capa: Entrega | null; imagens: Entrega[]; n_arquivos: number; textos: Record<string, string>; etiquetas: Etiquetas; revisao: Revisao; mensagem_final: string }
export type AprovacaoDecisao = { tipo: 'decisao'; id: string; codigo: string | null; titulo: string; slug: string | null; status: string; atualizado: string; interacao: Interacao & { pergunta: string | null } }
export type VozGeracao = { status: 'parado' | 'rodando' | 'pronto' | 'erro'; voz: string | null; inicio: string | null; fim: string | null; amostra: VozAmostra | null; erro: string | null; etapa: string | null }
export type Fluxo = { nome: string; titulo: string; descricao: string; conteudo: string }
export type Estilo = { nome: string; legenda: Record<string, any>; montagem: Record<string, any>; saida: Record<string, any>; descricao?: string; temas?: string[]; casa?: boolean; montado?: Record<string, any> }
export type FaixaHorario = { dia: string; faixa: string; n: number; mediana: number; pouca_amostra: boolean }
export type AlertaAuto = { chave: string; tipo: 'tracao' | 'queda' | 'risco'; plataforma: string; titulo: string; razao?: number; views?: number; idade_dias?: number; negativos?: number; url: string }
export type Campanha = { id: string; nome: string; inicio?: string | null; fim?: string | null; objetivo?: string; mensagem?: string; meta_pecas?: number | null; redes?: string[]; notas?: string; situacao: string;
  n_pecas: number; n_publicadas: number; n_medidas: number; views: number | null; razao_mediana: number | null; progresso: number | null; formatos: Record<string, number>;
  melhor: { slug: string; titulo: string; views: number; vs_mediana: number | null } | null; pecas: { slug: string; titulo: string; codigo?: string; conversa?: string; formato?: string; estado: string; publicado_em?: string; views?: number | null; vs_mediana?: number | null }[];
  sugestoes: { slug: string; titulo: string; publicado_em?: string }[] }
type FaixaRende = { faixa: string; n: number; mediana: number; pouca_amostra: boolean }
export type PerfilRende = { erro?: string; gerado_em: string; n_pecas: number; nota: string; pistas: string[]; avisos: string[]; duracao: { reels: FaixaRende[]; shorts: FaixaRende[]; youtube_longo: FaixaRende[] }; ganchos: { tipo: string; rotulo: string; medidos: number; razao_mediana: number | null; melhor?: string; pouca_amostra: boolean }[] }
export type PastaVigiada = { origem: string; ligada: boolean; lido_em?: string; erro?: string; n_arquivos?: number; ja_estavam: number; itens: { chave: string; caminho: string; estado: string; modo?: string; estilo?: string; conversa?: string; codigo?: string; quando?: string; erro?: string }[]; regras: { subpasta: string; modo: string; estilo?: string }[] }
export type AutomacoesDados = { posmortem: { quando: string; gerados: string[]; por: string } | null; variacoes: Record<string, { quando: string; estado: string; conversa?: string; codigo?: string; razao?: number; por?: string }>;
  alertas: AlertaAuto[]; alertas_quando: string | null; melhor_horario: { calculado_em: string; janela_dias: number; min_n: number; redes: Record<string, { posts: number; melhores: FaixaHorario[]; piores: FaixaHorario[]; todas: FaixaHorario[]; nota: string }> } | null;
  config: Record<string, Record<string, number>>; ligadas: Record<string, boolean> }
export type Previa = { estado: 'pronta' | 'fila' | 'gerando' | 'erro' | 'sem' | 'indisponivel'; url?: string; poster?: string | null; erro?: string }
export type EstiloBib = Estilo & { previa: Previa }
export type LegendaModelo = { id: string; nome: string; descricao: string; temas: string[]; fora_da_marca?: boolean; legenda: Record<string, any>; previa: Previa }
export type ElementoBib = { id: string; categoria: 'animacao' | 'transicao' | 'elemento' | 'formato'; nome: string; descricao: string; temas: string[]; como_pedir: string; parametro: string; previa: Previa }
export type BibliotecaEstilos = { estilos: EstiloBib[]; legendas: LegendaModelo[]; elementos: ElementoBib[]; temas: { id: string; rotulo: string }[]; fila: number; amostra: string }

async function j<T>(r: Response): Promise<T> {
  if (r.status === 401 && !location.pathname.startsWith('/entrar')) { location.replace('/entrar'); throw new Error('Sem acesso: abra o link de entrada.') }
  if (!r.ok) throw new Error((await r.text()) || r.statusText)
  return r.json()
}
export const api = {
  estado: () => fetch('/api/gs/estado').then(j<any>),
  fluxos: () => fetch('/api/gs/fluxos').then(j<Fluxo[]>),
  ideias: (status = 'approved,proposed') => fetch(`/api/gs/ideias?status=${status}`).then(j<Ideia[]>),
  estilos: () => fetch('/api/gs/estilos').then(j<Estilo[]>),
  conversas: () => fetch('/api/gs/conversas').then(j<Conversa[]>),
  conversa: (id: string) => fetch(`/api/gs/conversas/${id}`).then(j<ConversaDetalhe>),
  ajuda: () => fetch('/api/gs/ajuda').then(j<{ nome: string; titulo: string; conteudo: string }[]>),
  recebido: (token: string) => fetch(`/api/gs/recebidos/${encodeURIComponent(token)}`).then(j<Recebido>),
  biblioteca: () => fetch('/api/gs/biblioteca').then(j<{ slug: string; itens: Entrega[]; uso?: UsoEntrega; conversa?: string | null; pasta?: string | null }[]>),
  novaConversa: (fd: FormData, onProgresso?: (p: number) => void) => new Promise<Conversa>((res, rej) => {
    const x = new XMLHttpRequest(); x.open('POST', '/api/gs/conversas')
    x.upload.onprogress = e => { if (e.lengthComputable && onProgresso) onProgresso(Math.round(100 * e.loaded / e.total)) }
    x.onload = () => { try { x.status < 300 ? res(JSON.parse(x.responseText)) : rej(new Error(x.responseText || x.statusText)) } catch (e) { rej(e as Error) } }
    x.onerror = () => rej(new Error('Falha de rede no envio')); x.send(fd)
  }),
  decidir: (id: string, iid: string, acao: 'aceitar' | 'recusar' | 'responder', comentario = '') => { const fd = new FormData(); fd.append('comentario', comentario); return fetch(`/api/gs/conversas/${id}/interacoes/${iid}/${acao}`, { method: 'POST', body: fd }).then(j<any>) },
  referencias: () => fetch('/api/gs/referencias').then(j<Referencia[]>),
  referencia: (id: string) => fetch(`/api/gs/referencias/${id}`).then(j<Referencia>),
  concorrentes: () => fetch('/api/gs/referencias/concorrentes').then(j<Concorrente[]>),
  novaReferencia: (fd: FormData) => fetch('/api/gs/referencias', { method: 'POST', body: fd }).then(j<Referencia>),
  referenciaNota: (id: string, nota: string, titulo = '') => { const fd = new FormData(); fd.append('nota', nota); fd.append('titulo', titulo); return fetch(`/api/gs/referencias/${id}/nota`, { method: 'POST', body: fd }).then(j<Referencia>) },
  referenciaBaixar: (id: string) => fetch(`/api/gs/referencias/${id}/baixar`, { method: 'POST' }).then(j<Referencia>),
  referenciaApagar: (id: string) => fetch(`/api/gs/referencias/${id}`, { method: 'DELETE' }).then(j<any>),
  referenciaAnalisar: (id: string) => fetch(`/api/gs/referencias/${id}/analisar`, { method: 'POST' }).then(j<Conversa>),
  novoClipe: (fd: FormData, onProgresso?: (p: number) => void) => new Promise<Conversa>((res, rej) => {
    const x = new XMLHttpRequest(); x.open('POST', '/api/gs/clipes')
    x.upload.onprogress = e => { if (e.lengthComputable && onProgresso) onProgresso(Math.round(100 * e.loaded / e.total)) }
    x.onload = () => { try { x.status < 300 ? res(JSON.parse(x.responseText)) : rej(new Error(x.responseText || x.statusText)) } catch (e) { rej(e as Error) } }
    x.onerror = () => rej(new Error('Falha de rede no envio')); x.send(fd)
  }),
  cortes: (id: string) => fetch(`/api/gs/conversas/${id}/cortes`).then(j<Cortes>),
  editarCortes: (id: string, ids: string[]) => { const fd = new FormData(); fd.append('ids', ids.join(',')); return fetch(`/api/gs/conversas/${id}/cortes/editar`, { method: 'POST', body: fd }).then(j<{ criados: Conversa[] }>) },
  perfil: (gravar = false) => fetch(`/api/gs/referencias/perfil${gravar ? '?gravar=1' : ''}`).then(j<any>),
  notionTexto: (id: string) => fetch(`/api/gs/notion/pagina/${id}/texto`).then(j<{ id: string; titulo: string; formato: string[]; descricao: string; roteiro_pulso: string; corpo: string; url: string }>),
  canvaEstado: () => fetch('/api/gs/canva/estado').then(j<{ configurado: boolean; conectado: boolean; redirect_uri: string; pendencias: string[] }>),
  canvaImportar: (id: string, arquivo: string, titulo = '') => { const fd = new FormData(); fd.append('arquivo', arquivo); fd.append('titulo', titulo); return fetch(`/api/gs/conversas/${id}/canva`, { method: 'POST', body: fd }).then(j<{ design_id: string; edit_url: string; view_url: string; quando: string }>) },
  canvaLista: (id: string) => fetch(`/api/gs/conversas/${id}/canva`).then(j<{ design_id: string; edit_url: string; view_url: string; quando: string; arquivo: string }[]>),
  materiais: () => fetch('/api/gs/materiais').then(j<{ configurado: boolean; origem: string; pendencias: string[]; ultima_sincronizacao: string | null; n_arquivos: number; itens: { caminho: string; tipo: string; tamanho_mb: number; duracao_s: number | null }[] }>),
  materiaisSincronizar: () => fetch('/api/gs/materiais/sincronizar', { method: 'POST' }).then(j<any>),
  aprovar: (id: string, comentario = '') => { const fd = new FormData(); fd.append('comentario', comentario); return fetch(`/api/gs/conversas/${id}/aprovar`, { method: 'POST', body: fd }).then(j<any>) },
  busca: (q: string) => fetch(`/api/gs/busca?q=${encodeURIComponent(q)}`).then(j<(Conversa & { onde: string; trecho: string })[]>),
  novoFluxo: (nome: string, descricao: string, passos: string) => { const fd = new FormData(); fd.append('nome', nome); fd.append('descricao', descricao); fd.append('passos', passos); return fetch('/api/gs/fluxos', { method: 'POST', body: fd }).then(j<Fluxo>) },
  apagarFluxo: (nome: string) => fetch(`/api/gs/fluxos/${nome}`, { method: 'DELETE' }).then(j<any>),
  novoEstilo: (dados: Record<string, string>) => { const fd = new FormData(); Object.entries(dados).forEach(([k, v]) => fd.append(k, v)); return fetch('/api/gs/estilos', { method: 'POST', body: fd }).then(j<Estilo>) },
  apagarEstilo: (nome: string) => fetch(`/api/gs/estilos/${nome}`, { method: 'DELETE' }).then(j<any>),
  campanhas: () => fetch('/api/gs/campanhas').then(j<{ campanhas: Campanha[]; redes: string[] }>),
  campanhaSalvar: (fd: FormData) => fetch('/api/gs/campanhas', { method: 'POST', body: fd }).then(j<Campanha>),
  campanhaApagar: (id: string) => fetch(`/api/gs/campanhas/${encodeURIComponent(id)}`, { method: 'DELETE' }).then(j<{ ok: boolean }>),
  campanhaLigar: (id: string, slugs: string[]) => { const fd = new FormData(); fd.append('slugs', slugs.join(',')); return fetch(`/api/gs/campanhas/${encodeURIComponent(id)}/ligar`, { method: 'POST', body: fd }).then(j<{ ligadas: string[] }>) },
  campanhaAnalise: (id: string) => fetch(`/api/gs/campanhas/${encodeURIComponent(id)}/analise`, { method: 'POST' }).then(j<Conversa>),
  perfilRende: (atualizar = false) => fetch(`/api/gs/perfil/rende${atualizar ? '?atualizar=1' : ''}`).then(j<PerfilRende>),
  pastaVigiada: () => fetch('/api/gs/pasta_vigiada').then(j<PastaVigiada>),
  pastaVigiadaRodar: () => fetch('/api/gs/pasta_vigiada/rodar', { method: 'POST' }).then(j<{ pedidos?: string[]; erro?: string; na_pasta?: number; aguardando?: number }>),
  automacoesDados: () => fetch('/api/gs/automacoes/dados').then(j<AutomacoesDados>),
  automacaoDadosRodar: (id: string) => fetch(`/api/gs/automacoes/${id}/rodar_dados`, { method: 'POST' }).then(j<Record<string, any>>),
  estilosBiblioteca: () => fetch('/api/gs/estilos/biblioteca').then(j<BibliotecaEstilos>),
  pedirPrevias: (itens: string) => { const fd = new FormData(); fd.append('itens', itens); return fetch('/api/gs/estilos/previas', { method: 'POST', body: fd }).then(j<{ enfileiradas: number }>) },
  montarEstilo: (dados: Record<string, any>) => fetch('/api/gs/estilos/montar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) }).then(j<Estilo>),
  publicarEstado: () => fetch('/api/gs/publicar/estado').then(j<PublicarEstado>),
  publicar: (id: string, dados: { arquivo: string; legenda: string; plataformas: string[]; quando: string; titulo: string; capa?: string }) => { const fd = new FormData(); fd.append('arquivo', dados.arquivo); fd.append('legenda', dados.legenda); fd.append('plataformas', dados.plataformas.join(',')); fd.append('quando', dados.quando); fd.append('titulo', dados.titulo); fd.append('capa', dados.capa || ''); return fetch(`/api/gs/conversas/${id}/publicar`, { method: 'POST', body: fd }).then(j<Publicacao>) },
  youtubeEstado: () => fetch('/api/gs/youtube/estado').then(j<YoutubeEstado>),
  youtube: (id: string, dados: { arquivo: string; titulo: string; descricao: string; tags: string; privacidade: string; quando: string; capa: string }) => { const fd = new FormData(); Object.entries(dados).forEach(([k, v]) => fd.append(k, v)); return fetch(`/api/gs/conversas/${id}/youtube`, { method: 'POST', body: fd }).then(j<Publicacao>) },
  destaques: (dias = 120) => fetch(`/api/gs/referencias/concorrentes/destaques?dias=${dias}`).then(j<{ dias: number; minimo: number; itens: Destaque[]; canais: { handle: string; nome: string; tipo: string; videos: number; mediana: number | null }[]; nota?: string; erro?: string }>),
  publicacoes: (id: string, atualizar = false) => fetch(`/api/gs/conversas/${id}/publicacoes${atualizar ? '?atualizar=1' : ''}`).then(j<Publicacao[]>),
  drive: (id: string, arquivos: string[]) => { const fd = new FormData(); fd.append('arquivos', arquivos.join(',')); return fetch(`/api/gs/conversas/${id}/drive`, { method: 'POST', body: fd }).then(j<Publicacao>) },
  abrirCapcut: () => fetch('/api/gs/capcut/abrir', { method: 'POST' }).then(j<any>),
  parar: (id: string) => fetch(`/api/gs/conversas/${id}/parar`, { method: 'POST' }).then(j<{ ok: boolean; run_cancelada: boolean; status: string }>),
  retomar: (id: string) => fetch(`/api/gs/conversas/${id}/retomar`, { method: 'POST' }).then(j<{ ok: boolean; status: string }>),
  checkpoints: (id: string) => fetch(`/api/gs/conversas/${id}/checkpoints`).then(j<{ slug: string | null; itens: Checkpoint[] }>),
  desfazer: (id: string, n?: number) => fetch(`/api/gs/conversas/${id}/desfazer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(n == null ? {} : { n }) }).then(j<Desfeito>),
  cancelar: (id: string) => fetch(`/api/gs/conversas/${id}/cancelar`, { method: 'POST' }).then(j<any>),
  calendario: (antes = 14, depois = 28) => fetch(`/api/gs/redes/calendario?antes=${antes}&depois=${depois}`).then(j<{ hoje: string; inicio: string; fim: string; itens: CalendarioItem[]; aviso?: string | null }>),
  comentarios: (dias = 30, todos = false) => fetch(`/api/gs/redes/comentarios?dias=${dias}&todos=${todos}`).then(j<{ itens: Comentario[]; n: number; sem_resposta: number }>),
  rascunharRespostas: (ids: string[], dias = 30) => { const fd = new FormData(); fd.append('ids', ids.join(',')); fd.append('dias', String(dias)); return fetch('/api/gs/redes/comentarios/rascunhar', { method: 'POST', body: fd }).then(j<Conversa>) },
  resultados: (dias = 30) => fetch(`/api/gs/redes/resultados?dias=${dias}`).then(j<Resultados>),
  analisarResultados: (dias = 30) => { const fd = new FormData(); fd.append('dias', String(dias)); return fetch('/api/gs/redes/resultados/analisar', { method: 'POST', body: fd }).then(j<Conversa>) },
  relatorioMes: (mes: string) => fetch(`/api/gs/redes/relatorio-mes?mes=${mes}`).then(j<{ mes: string; arquivo: string; conteudo: string }>),
  armazenamento: (dias = 30) => fetch(`/api/gs/armazenamento?dias=${dias}`).then(j<Armazenamento>),
  limparTrabalho: (dias = 30) => { const fd = new FormData(); fd.append('dias', String(dias)); return fetch('/api/gs/armazenamento/limpar', { method: 'POST', body: fd }).then(j<{ apagados: any[]; mb: number }>) },
  uso: () => fetch('/api/gs/uso').then(j<Uso>),
  avulsos: () => fetch('/api/gs/biblioteca/avulsos').then(j<Avulso[]>),
  uploadAvulso: (fd: FormData, onProgresso?: (p: number) => void) => new Promise<{ salvos: string[] }>((res, rej) => {
    const x = new XMLHttpRequest(); x.open('POST', '/api/gs/biblioteca/upload')
    x.upload.onprogress = e => { if (e.lengthComputable && onProgresso) onProgresso(Math.round(100 * e.loaded / e.total)) }
    x.onload = () => { try { x.status < 300 ? res(JSON.parse(x.responseText)) : rej(new Error(x.responseText || x.statusText)) } catch (e) { rej(e as Error) } }
    x.onerror = () => rej(new Error('Falha de rede no envio')); x.send(fd)
  }),
  apagarAvulso: (nome: string) => fetch(`/api/gs/biblioteca/avulsos/${encodeURIComponent(nome)}`, { method: 'DELETE' }).then(j<any>),
  anotacoes: () => fetch('/api/gs/anotacoes').then(j<Anotacao[]>),
  novaAnotacao: (texto: string, arquivos: File[] = []) => { const fd = new FormData(); fd.append('texto', texto); arquivos.forEach(a => fd.append('arquivos', a)); return fetch('/api/gs/anotacoes', { method: 'POST', body: fd }).then(j<Anotacao>) },
  apagarAnotacao: (id: string) => fetch(`/api/gs/anotacoes/${id}`, { method: 'DELETE' }).then(j<any>),
  anotacaoPedido: (id: string) => fetch(`/api/gs/anotacoes/${id}/pedido`, { method: 'POST' }).then(j<{ token: string; url: string }>),
  atalho: () => fetch('/api/gs/atalho').then(j<{ token: string; base: string; app: string; url: string }>),
  textos: (q = '', tipo = '', pasta = '') => fetch(`/api/gs/textos?q=${encodeURIComponent(q)}&tipo=${encodeURIComponent(tipo)}&pasta=${encodeURIComponent(pasta)}`).then(j<{ itens: TextoItem[]; tipos: { chave: string; rotulo: string }[] }>),
  anotacaoStatus: (id: string, status: string) => { const fd = new FormData(); fd.append('status', status); return fetch(`/api/gs/anotacoes/${id}/status`, { method: 'POST', body: fd }).then(j<Anotacao>) },
  notionCartoes: (q: string) => fetch(`/api/gs/notion/cartoes?q=${encodeURIComponent(q)}`).then(j<CartaoNotion[]>),
  enviarTextoNotion: (id: string, secao: string, pagina: string, mensagem = '', modo = 'acrescentar') => { const fd = new FormData(); fd.append('secao', secao); fd.append('pagina', pagina); fd.append('mensagem', mensagem); fd.append('modo', modo); return fetch(`/api/gs/conversas/${id}/textos/notion`, { method: 'POST', body: fd }).then(j<{ ok: boolean; url: string | null; titulo: string | null; chars: number }>) },
  guardarTexto: (id: string, chave: string, titulo = '', mensagem = '', secao = '') => { const fd = new FormData(); fd.append('chave', chave); fd.append('titulo', titulo); if (mensagem) { fd.append('mensagem', mensagem); fd.append('secao', secao) } return fetch(`/api/gs/conversas/${id}/textos/guardar`, { method: 'POST', body: fd }).then(j<{ nome: string; chave: string; codigo: string }>) },
  textosGuardados: () => fetch('/api/gs/textos/guardados').then(j<TextoGuardado[]>),
  apagarTextoGuardado: (nome: string) => fetch(`/api/gs/textos/guardados/${encodeURIComponent(nome)}`, { method: 'DELETE' }).then(j<any>),
  versao: () => fetch('/versao.json?t=' + Date.now(), { cache: 'no-store' }).then(j<{ build: string | null; quando?: string }>),
  celular: () => fetch('/api/gs/celular').then(j<{ disponivel: boolean; aparelhos: { nome: string; online: boolean; visto: string | null; os: string }[]; serve: string | null; erro?: string }>),
  atalhoNovo: () => fetch('/api/gs/atalho/novo', { method: 'POST' }).then(j<{ token: string; base: string; app: string; url: string }>),
  pastas: () => fetch('/api/gs/pastas').then(j<{ pastas: Pasta[]; sem_pasta: number }>),
  novaPasta: (nome: string) => { const fd = new FormData(); fd.append('nome', nome); return fetch('/api/gs/pastas', { method: 'POST', body: fd }).then(j<{ nome: string }>) },
  renomearPasta: (nome: string, novo: string) => { const fd = new FormData(); fd.append('novo', novo); return fetch(`/api/gs/pastas/${encodeURIComponent(nome)}/renomear`, { method: 'POST', body: fd }).then(j<{ nome: string; movidas: number }>) },
  apagarPasta: (nome: string) => fetch(`/api/gs/pastas/${encodeURIComponent(nome)}`, { method: 'DELETE' }).then(j<{ apagada: string; liberadas: number }>),
  moverPasta: (id: string, pasta: string) => { const fd = new FormData(); fd.append('pasta', pasta); return fetch(`/api/gs/conversas/${id}/pasta`, { method: 'POST', body: fd }).then(j<{ id: string; pasta: string | null }>) },
  voz: () => fetch('/api/gs/voz').then(j<{ disponivel: boolean; motores: Record<string, boolean>; vozes: Voz[]; geracao: VozGeracao; texto_padrao: string }>),
  vozGeracao: () => fetch('/api/gs/voz/geracao').then(j<VozGeracao>),
  vozDecidir: (nome: string, dados: Record<string, string>) => { const fd = new FormData(); Object.entries(dados).forEach(([k, v]) => fd.append(k, v)); return fetch(`/api/gs/voz/${nome}/decisao`, { method: 'POST', body: fd }).then(j<Voz>) },
  vozAmostra: (nome: string, texto: string, referencia = '', extra: Record<string, string> = {}) => { const fd = new FormData(); fd.append('texto', texto); fd.append('referencia', referencia); Object.entries(extra).forEach(([k, v]) => { if (v !== '') fd.append(k, v) }); return fetch(`/api/gs/voz/${nome}/amostra`, { method: 'POST', body: fd }).then(j<{ status: string; arquivo: string; motor: string }>) },
  aprovacoes: () => fetch('/api/gs/aprovacoes').then(j<{ entregas: AprovacaoEntrega[]; decisoes: AprovacaoDecisao[]; n: number }>),
  aprovarLote: (ids: string[], comentario = 'Ficou bom.') => { const fd = new FormData(); fd.append('ids', ids.join(',')); fd.append('comentario', comentario); return fetch('/api/gs/aprovacoes/lote', { method: 'POST', body: fd }).then(j<{ aprovadas: string[]; erros: any[] }>) },
  marcarVistas: (ids: string[]) => { const fd = new FormData(); fd.append('ids', ids.join(',')); return fetch('/api/gs/aprovacoes/vistas', { method: 'POST', body: fd }).then(j<{ vistas: string[] }>) },
  pedirAjuste: (id: string, texto: string, segundo: number | null, arquivo = '') => { const fd = new FormData(); fd.append('texto', texto); fd.append('segundo', segundo == null ? '' : String(segundo)); fd.append('arquivo', arquivo); return fetch(`/api/gs/conversas/${id}/ajuste`, { method: 'POST', body: fd }).then(j<any>) },
  revisaoMarca: (id: string) => fetch(`/api/gs/conversas/${id}/revisao-marca`).then(j<Revisao>),
  metricas: (dias = 30) => fetch(`/api/gs/metricas?dias=${dias}`).then(j<{ painel: Resultados; pecas: any; posmortem: { pendentes: PecaLinha[]; feitos: Posmortem[]; dias: number }; automacoes: Automacao[] }>),
  posmortemGerar: (slug = '') => { const fd = new FormData(); fd.append('slug', slug); return fetch('/api/gs/metricas/posmortem', { method: 'POST', body: fd }).then(j<{ gerados: Posmortem[]; n: number }>) },
  relatorioSemana: (fim = '') => fetch(`/api/gs/metricas/relatorio-semana?fim=${fim}`).then(j<{ inicio: string; fim: string; arquivo: string; conteudo: string; pecas: number; sem_etiqueta: number; posmortens: number }>),
  automacoes: () => fetch('/api/gs/automacoes').then(j<{ itens: Automacao[]; gsi: string }>),
  automacoesRodadas: () => fetch('/api/gs/automacoes/rodadas').then(j<Rodadas>),
  storiesRodar: () => fetch('/api/gs/automacoes/stories_serie/rodar', { method: 'POST' }).then(j<Rodada>),
  storiesConcluir: () => fetch('/api/gs/automacoes/stories_serie/concluir', { method: 'POST' }).then(j<{ feitas: Rodada[] }>),
  storiesConfig: (campos: Record<string, string>) => { const fd = new FormData(); Object.entries(campos).forEach(([k, v]) => fd.append(k, v)); return fetch('/api/gs/automacoes/stories_serie/config', { method: 'POST', body: fd }).then(j<StoriesConfig>) },
  ganchos: (p: Record<string, string>) => fetch('/api/gs/ganchos?' + new URLSearchParams(p).toString()).then(j<Ganchos>),
  skills: (p: Record<string, string> = {}) => fetch('/api/gs/skills?' + new URLSearchParams(p).toString()).then(j<{ itens: SkillItem[]; estado: SkillsEstado; garimpo_ligado: boolean }>),
  skillsRegistrar: (campos: Record<string, string>) => { const fd = new FormData(); Object.entries(campos).forEach(([k, v]) => fd.append(k, v)); return fetch('/api/gs/skills/registrar', { method: 'POST', body: fd }).then(j<{ novos: string[]; ja_tinha: string[]; item: SkillItem }>) },
  skillsPesquisar: (foco = '') => { const fd = new FormData(); fd.append('foco', foco); return fetch('/api/gs/skills/pesquisar', { method: 'POST', body: fd }).then(j<{ rodada: any; conversa: Conversa }>) },
  skillsEnsinar: (fd: FormData) => fetch('/api/gs/skills/ensinar', { method: 'POST', body: fd }).then(j<{ tipo: string; arquivo?: string; titulo?: string; memoria?: { texto: string } }>),
  skillsConhecimentoApagar: (arquivo: string) => fetch(`/api/gs/skills/conhecimento/${encodeURIComponent(arquivo)}`, { method: 'DELETE' }).then(j<{ ok: boolean }>),
  skillDecidir: (id: string, estado: string, nota = '') => { const fd = new FormData(); fd.append('estado', estado); fd.append('nota', nota); return fetch(`/api/gs/skills/${encodeURIComponent(id)}/decidir`, { method: 'POST', body: fd }).then(j<SkillItem>) },
  skillAnotar: (id: string, texto: string) => { const fd = new FormData(); fd.append('texto', texto); return fetch(`/api/gs/skills/${encodeURIComponent(id)}/anotar`, { method: 'POST', body: fd }).then(j<SkillItem>) },
  skillEditar: (id: string, campos: Record<string, string>) => { const fd = new FormData(); Object.entries(campos).forEach(([k, v]) => fd.append(k, v)); return fetch(`/api/gs/skills/${encodeURIComponent(id)}/editar`, { method: 'POST', body: fd }).then(j<SkillItem>) },
  skillInstalar: (id: string) => fetch(`/api/gs/skills/${encodeURIComponent(id)}/instalar`, { method: 'POST' }).then(j<{ pasta: string; skill: string }>),
  skillDesinstalar: (id: string) => fetch(`/api/gs/skills/${encodeURIComponent(id)}/desinstalar`, { method: 'POST' }).then(j<{ ok: boolean }>),
  skillReproduzir: (id: string, modo: 'reproduzir' | 'avaliar' = 'reproduzir') => { const fd = new FormData(); fd.append('modo', modo); return fetch(`/api/gs/skills/${encodeURIComponent(id)}/reproduzir`, { method: 'POST', body: fd }).then(j<Conversa>) },
  acervo: (q: string, origem = 'tudo') => fetch(`/api/gs/acervo?q=${encodeURIComponent(q)}&origem=${origem}`).then(j<AcervoBusca>),
  acervoCorte: (campos: Record<string, string>) => { const fd = new FormData(); Object.entries(campos).forEach(([k, v]) => fd.append(k, v)); return fetch('/api/gs/acervo/corte', { method: 'POST', body: fd }).then(j<{ conversa: Conversa; arquivo: string; corte: any }>) },
  experimentos: (fechar = false) => fetch(`/api/gs/automacoes/experimentos${fechar ? '?fechar=sim' : ''}`).then(j<{ itens: any[]; abertos: number; ganhou: number; perdeu: number; empate: number; fechados_agora: number; regra: string }>),
  recicladoRodar: (gancho = '') => { const fd = new FormData(); fd.append('gancho', gancho); return fetch('/api/gs/automacoes/reel_reciclado/rodar', { method: 'POST', body: fd }).then(j<Rodada>) },
  recicladoConcluir: () => fetch('/api/gs/automacoes/reel_reciclado/concluir', { method: 'POST' }).then(j<{ feitas: Rodada[] }>),
  recicladoConfig: (campos: Record<string, string>) => { const fd = new FormData(); Object.entries(campos).forEach(([k, v]) => fd.append(k, v)); return fetch('/api/gs/automacoes/reel_reciclado/config', { method: 'POST', body: fd }).then(j<RecicladoConfig>) },
  automacaoAlternar: (id: string, ligada: boolean) => { const fd = new FormData(); fd.append('ligada', ligada ? 'sim' : 'nao'); return fetch(`/api/gs/automacoes/${id}`, { method: 'POST', body: fd }).then(j<any>) },
  pecas: (filtros: Record<string, string> = {}) => fetch('/api/gs/pecas?' + new URLSearchParams(filtros).toString()).then(j<{ itens: PecaLinha[]; resumo: any; opcoes: PecaOpcoes }>),
  peca: (slug: string) => fetch(`/api/gs/pecas/${slug}`).then(j<PecaFicha>),
  pecaEtiquetas: (slug: string, dados: Record<string, string>) => { const fd = new FormData(); Object.entries(dados).forEach(([k, v]) => fd.append(k, v)); return fetch(`/api/gs/pecas/${slug}/etiquetas`, { method: 'POST', body: fd }).then(j<PecaEtiquetas>) },
  pecaOpcao: (campo: string, valor: string) => { const fd = new FormData(); fd.append('campo', campo); fd.append('valor', valor); return fetch('/api/gs/pecas/opcoes', { method: 'POST', body: fd }).then(j<any>) },
  vozApagarAmostra: (nome: string, arquivo: string) => fetch(`/api/gs/voz/${nome}/amostras/${encodeURIComponent(arquivo)}`, { method: 'DELETE' }).then(j<any>),
  marca: (gravar = false) => fetch(`/api/gs/marca${gravar ? '?gravar=1' : ''}`).then(j<Marca>),
  mensagem: (id: string, texto: string, modelo = '', arquivos: File[] = [], drive: DriveItem[] = []) => { const fd = new FormData(); fd.append('texto', texto); if (modelo) fd.append('modelo', modelo); arquivos.forEach(f => fd.append('arquivos', f)); if (drive.length) fd.append('drive', JSON.stringify(drive.map(d => ({ raiz: d.raiz, caminho: d.caminho })))); return fetch(`/api/gs/conversas/${id}/mensagens`, { method: 'POST', body: fd }).then(j<{ ok: boolean; modelo?: { id: string; rotulo: string }; trocou?: boolean; drive?: number }>) },
  driveRaizes: () => fetch('/api/gs/drive/raizes').then(j<{ raizes: { id: string; rotulo: string }[] }>),
  driveListar: (raiz: string, caminho: string) => fetch(`/api/gs/drive/listar?raiz=${encodeURIComponent(raiz)}&caminho=${encodeURIComponent(caminho)}`).then(j<DrivePasta>),
  concluir: (id: string) => fetch(`/api/gs/conversas/${id}/concluir`, { method: 'POST' }).then(j<{ ok: boolean; status: string }>),
  excluir: (id: string) => fetch(`/api/gs/conversas/${id}/excluir`, { method: 'POST' }).then(j<{ ok: boolean; status: string }>),
  restaurar: (id: string) => fetch(`/api/gs/conversas/${id}/restaurar`, { method: 'POST' }).then(j<{ ok: boolean; status: string }>),
  lixeira: () => fetch('/api/gs/lixeira').then(j<Conversa[]>),
  estiloCriativo: () => fetch('/api/gs/estilo-criativo').then(j<EstiloCriativo>),
  estiloCriativoPadrao: (cfg: EstiloCfg) => fetch('/api/gs/estilo-criativo/padrao', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) }).then(j<EstiloCriativo>),
  estiloCriativoTexto: (cfg: EstiloCfg) => fetch('/api/gs/estilo-criativo/texto', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) }).then(j<{ texto: string }>),
  lembrar: (texto: string) => { const fd = new FormData(); fd.append('texto', texto); return fetch('/api/gs/estilo-criativo/memorias', { method: 'POST', body: fd }).then(j<Memoria>) },
  esquecer: (mid: string) => fetch(`/api/gs/estilo-criativo/memorias/${mid}`, { method: 'DELETE' }).then(j<{ ok: boolean }>),
  continuar: (id: string) => fetch(`/api/gs/conversas/${id}/continuar`).then(j<{ pedido: string; pasta: string; fluxo: string; estilo: string; origem: string | null }>),
}
// Estilo do criativo (fase D, 07/11/2026): energia + chaves + legenda; memórias = preferências visíveis e removíveis
export type EstiloCfg = { energia: string; chaves: Record<string, boolean>; legenda: string }
export type Memoria = { id: string; texto: string; origem: string; criado: string }
export type EstiloCriativo = { padrao: EstiloCfg; memorias: Memoria[]; atualizado: string | null; texto_padrao: string
  opcoes: { energias: { id: string; rotulo: string }[]; chaves: { id: string; rotulo: string; padrao: boolean }[]; legendas: { id: string; rotulo: string }[] } }
export const STATUS: Record<string, string> = { backlog: 'Na fila', todo: 'Na fila', in_progress: 'Editando', in_review: 'Entregue, aguardando você', done: 'Concluído', blocked: 'Pausado ou aguardando você', cancelled: 'Cancelado' }
