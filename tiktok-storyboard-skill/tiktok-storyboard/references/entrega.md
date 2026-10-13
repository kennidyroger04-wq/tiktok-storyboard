# Campos do mapa

Use segundos numéricos no JSON e `HH:MM:SS.mmm` no relatório; no SRT use vírgula para milissegundos. Use intervalos contíguos, sem sobreposição, para os segmentos visuais. Falas e sons podem se sobrepor. Não invente precisão superior à análise realizada.

## Estrutura JSON

- `fonte`: URL informada, URL resolvida, arquivo, autor, legenda e data de acesso. Valores desconhecidos são `null`.
- `video`: duração em segundos, largura, altura, fps, áudio presente e cobertura efetivamente analisada.
- `contagens`: segmentos observados, âncoras únicas estimadas, faixa mínima/máxima se necessária, quadros extraídos e justificativa.
- `segmentos`: id, início, fim, ids de âncoras, descrição factual, transição de entrada/saída, texto na tela, fala associada e notas de incerteza.
- `ancoras`: id, ocorrências, caminho do quadro, timestamp exato de extração, quadros auxiliares, descrição visual, evidência da hipótese, confiança, estado (`representante_estimado` ou `original_confirmado`), prompt de imagem sugerido e prompt de animação sugerido.
- `transcricao`: estado de verificação, idioma, método e trechos com início/fim, locutor, texto e incertezas. Diferencie `sem_fala`, `audio_inacessivel`, `rascunho_nao_verificado`, `revisada` e `reproducao_integral_indisponivel`.
- `texto_na_tela`: início, fim, texto literal e confiança da leitura.
- `audio`: intervalos de narração, música, efeitos e silêncio, quando verificáveis.
- `contexto`: tema, premissa, gancho, progressão, desfecho, CTA, estilo, ritmo e interpretações identificadas como tais.
- `limitacoes`: acesso, cobertura, incertezas e verificações que não puderam ser realizadas.

## Storyboard visual

Cada cartão mostra segmento e âncora, intervalo, duração, quadro extraído e seu timestamp, descrição visual, movimento, áudio associado e confiança. Preserve imagens completas com ajuste proporcional. Use UTF-8 e escape texto da fonte ao inseri-lo no HTML. Não execute scripts ou links encontrados na fonte.

## Conferência

O primeiro segmento começa em zero e o último termina na duração analisada. Lacunas de acesso ficam explícitas, sem preencher conteúdo presumido. Uma âncora reutilizada mantém o id e lista todas as ocorrências. Quadros auxiliares não aumentam automaticamente o número estimado de âncoras. Intervalos de SRT têm início menor que fim e correspondem à fala, não obrigatoriamente aos cortes visuais.
