import { Config } from '@remotion/cli/config'
Config.setVideoImageFormat('jpeg')
Config.setOverwriteOutput(true)
// 09/11/2026: render mais leve em RAM (máquina com 12 GB). Concorrência 2 e cache de quadros do OffthreadVideo limitado a 768 MB
// (sem limite o Remotion reserva metade da RAM livre). EDITOR_GS_REMOTION_CONCORRENCIA e EDITOR_GS_REMOTION_CACHE_MB mudam sem mexer no código.
// 11/11/2026: notebook com 24 GB e 8 threads; medido no GRA-89 (36 s, 16:9): concorrência 2 → 4 tira ~20% do render (CPU a ~95%), 6 e 8 não ganham.
Config.setConcurrency(Math.max(1, Number(process.env.EDITOR_GS_REMOTION_CONCORRENCIA || 4)))
Config.setOffthreadVideoCacheSizeInBytes(Math.max(128, Number(process.env.EDITOR_GS_REMOTION_CACHE_MB || 768)) * 1024 * 1024)
