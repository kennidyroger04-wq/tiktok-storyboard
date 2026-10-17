# Auditoria e recuperação — Missão 06

## Recuperação do histórico

O checkout inicial estava no commit `7d8f888` (branch local `work`), com um diretório legado e seu ZIP. A busca examinou refs locais, branches, tags, objetos inalcançáveis, reflogs e o remoto `origin`. O commit solicitado `a8f9f91` não existe no checkout nem pôde ser obtido do remoto; o remoto anunciava apenas `main` em `7d8f888`. Não havia tags nem outros checkouts acessíveis. A tentativa de consultar o histórico de tarefas/artifacts não respondeu durante a janela de execução.

Assim, não foi possível recuperar bytes da implementação das Missões 04/05. O legado e ZIP foram mantidos intactos. A skill em `.agents/skills/tiktok-storyboard/` é uma reconstrução funcional a partir dos arquivos legados e dos requisitos registrados nas missões, não uma restauração verificável do commit perdido. Os 25 testes atuais são testes recuperados/reconstruídos nesta execução; não se afirma que sejam os mesmos 25 testes anteriormente aprovados.

## Implementado

- Skill Codex completa em `.agents/skills/tiktok-storyboard/` com metadados do agente, instruções e referências.
- Download público com `yt-dlp`, manifesto e validação; configuração compatível com o trust store do sistema e TLS verificado.
- Inspeção integral com `ffprobe`/FFmpeg, amostragem temporal, candidatos de cortes e folha de contato HTML local.
- Rascunho local por `faster-whisper` tiny multilingual, timestamps por palavra, lacunas estimadas e marcação explícita de incerteza. Não há diarização implementada.
- Validação/renderização do mapa para HTML e Markdown integrados; exportação TXT/SRT/JSON apenas após revisão humana do texto.
- Instalador reprodutível e dependências diretas fixadas em `requirements-cloud.txt`; caches/modelos/dependências ignorados pelo Git.
- Os cartões de storyboard integram âncoras, períodos, evidência visual, ações, fala associada, som e prompts sugeridos de imagem/animação. A análise semântica continua sendo completada pelo agente, não automatizada por detecção visual.

## Validação nesta sessão Cloud

- Runtime conectado, fase `running`; política de rede em modo restrito com estado reportado como `unknown`. `unknown` não foi interpretado como bloqueio ou como política efetivamente aplicada.
- Python 3.12.14, FFmpeg e ffprobe 7.1.5 disponíveis.
- `yt-dlp 2026.8.19`, `faster-whisper 1.2.1`, `ctranslate2 4.8.3`, PyAV 15.1.0 e Hugging Face Hub instalados em `.runtime/`; modelo `Systran/faster-whisper-tiny` baixado para `.models/` (fora do Git).
- Vídeo real fornecido pelo usuário (`7685159918147472660`, 129 s) baixado por URL pública e decodificado integralmente; 66 amostras temporais, quadros de cortes candidatos e seis folhas de contato. O download inicial falhou por incompatibilidade entre certifi e o CA do proxy; usar o trust store do sistema corrigiu o problema mantendo validação TLS. Houve aviso não fatal do yt-dlp sobre impersonation.
- Quadros inspecionados visualmente na sessão. A sequência foi observada como animação com personagens-fruta em diferentes cenários. A detecção automática sugeriu cortes, mas não é suficientemente confiável para determinar sozinha todas as cenas.
- faster-whisper gerou rascunho em português com 36 segmentos e 235 timestamps de palavras. Isso demonstra execução do reconhecedor no vídeo, não precisão lexical: não havia transcrição de referência nem revisão auditiva independente. O resultado permanece `rascunho_nao_verificado`.
- Fixture de fala conhecida em inglês reconhecida pelo modelo local, incluindo “hello” e “world”, com timestamps por palavra.
- Testes automatizados: **25 passaram, 0 falharam, 0 ignorados** após a instalação reprodutível, incluindo o teste de integração de fala local; 0 falhas e 0 skips.

## Limitações e prontidão

- Não há recuperação comprovada de `a8f9f91` ou artefatos da implementação avançada anterior.
- A sincronização por palavra e cena é suportada no schema/renderizador, mas a precisão depende da correção/revisão do ASR e da segmentação semântica do agente. Diarização automática não está disponível.
- Não foi gerado um pacote final do vídeo TikTok real: falta revisar o rascunho de fala e construir/revisar mapa de cenas, âncoras e prompts. Download, decodificação, inspeção por quadros e rascunho ASR foram exercitados de ponta a ponta parcialmente.
- A versão atual está sendo preparada em branch nova; só ficará no branch principal após PR e merge. A configuração Cloud publicada existente ainda aponta ao SHA inicial `7d8f888`. As atualizações de configuração devem ser revisadas/publicadas pela interface; o estado de rede atual é `unknown`.
- Uma nova sessão não foi criada para testar restauração. Não há prova de persistência entre tarefas até publicação e teste independente.

**Veredito:** preparada para um teste de reconstrução com revisão humana, aprovada com ressalvas. O download e a inspeção de um vídeo real foram demonstrados; a equivalência integral com a versão perdida e a qualidade de transcrição PT-BR permanecem não validadas.
