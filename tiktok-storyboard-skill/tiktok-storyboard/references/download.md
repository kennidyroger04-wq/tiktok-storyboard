# Download público do TikTok

Use `scripts/download_public.py` antes de depender do navegador. Ele usa a API do yt-dlp, não carrega configurações de usuário e não lê cookies. Solicita um formato com vídeo e áudio juntos, evitando depender de FFmpeg para unir faixas. Grava mídia e um manifesto mínimo em `work/`, sem salvar URLs assinadas, cookies ou cabeçalhos em entregáveis.

## Preparação e execução

Escolha um Python funcional. Instale pelo PyPI oficial no ambiente disponível ou em uma pasta privada de dependências da skill:

```text
python -m pip install --target <pasta-da-skill>/.runtime yt-dlp
python <pasta-da-skill>/scripts/download_public.py <url-tiktok> --output <workspace>/work/<id>
```

Para usar dependências em outro diretório, acrescente `--deps <diretorio>`. Solicite acesso de rede ou gravação apenas quando o ambiente exigir. A pasta `.runtime` é uma dependência local, não parte do pacote distribuível da skill. Não altere o Python global nem configurações do navegador.

## Verificação e recuperação

Para URL canônica, o script reutiliza um arquivo no diretório solicitado quando id, caminho e SHA-256 coincidem com o manifesto. Isso evita consultas repetidas a uma fonte intermitente. Esse reaproveitamento não substitui a verificação de decodificação.

Sucesso de download não confirma mídia íntegra: decodifique o arquivo inteiro com FFmpeg ou equivalente, confirme áudio e vídeo e confira quadros do início e do fim. Compare id e duração com a fonte. Só então prossiga com o storyboard. O estado `downloaded_not_decoded` no manifesto descreve exclusivamente a etapa de download.

Em falha de extração, verifique a versão instalada; faça no máximo uma atualização oficial e uma nova tentativa quando houver evidência de incompatibilidade de versão. Não troque repetidamente fingerprints, proxies ou regiões para atravessar um bloqueio. Erro de rede não prova que o vídeo é privado.

Se a fonte exigir sessão autenticada, pare o fluxo anônimo e explique o erro. Peça autorização específica antes de ler cookies do navegador, identificando navegador/perfil e uso local no TikTok. A permissão genérica de rede não autoriza leitura de cookies. Não solicite senha ou cookies no chat e não inclua segredos nos relatórios. Este script não implementa autenticação; um fluxo autenticado deve ser preparado separadamente ou substituído pelo MP4 anexado pelo usuário. Não contorne CAPTCHA, restrições de idade, conteúdo privado ou controles de acesso.

Documentação oficial: https://github.com/yt-dlp/yt-dlp#installation e https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp
