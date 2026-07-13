# Análise de melhorias — youtube_downloader.py

> Análise de 2026-07-13 sobre o código atual (1617 linhas, monolítico).
> Prioridade: 🔴 bug real · 🟠 melhoria de alto impacto · 🟡 qualidade/manutenção
>
> **Status:** fase 1 (bugs #1, #2, #3, #5, #6) aplicada e validada em 2026-07-13.
> Testes: conversão AAC ok (46min convertidos = duração da origem), dedupe sufixa -2,
> noplaylist fixo nos fluxos de item único.

---

## 🔴 Bugs reais encontrados

### 1. Conversão para AAC/M4A está quebrada (`AudioExtractor.extract_audio`)
```python
cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", codec, "-ab", quality, out]
if self.config.audio_format != "mp3":
    cmd[4] = "aac"     # sobrescreve "-vn" (que remove o vídeo!)
    cmd[5] = "-b:a"    # sobrescreve "-acodec"
```
Os índices estão errados: `cmd[4]` é `-vn` e `cmd[5]` é `-acodec`. Para qualquer formato ≠ mp3 o comando vira `ffmpeg -y -i video aac -b:a aac -ab 192k out` → **falha sempre**. Como o menu permite escolher `aac`/`m4a` nas configurações, o usuário que trocar o formato quebra a extração.
**Correção:** montar o comando por formato, sem index-hacking:
```python
codec_args = {"mp3": ["-acodec", "libmp3lame", "-ab", q],
              "aac": ["-acodec", "aac", "-b:a", q],
              "m4a": ["-acodec", "aac", "-b:a", q]}[fmt]
cmd = ["ffmpeg", "-y", "-i", src, "-vn", *codec_args, out]
```

### 2. URL com `&list=` sobrescreve o mesmo arquivo N vezes (`_download_single_video`)
`'noplaylist': not self.config.enable_playlist` com o padrão `enable_playlist=True` resulta em `noplaylist=False`. Se o usuário colar uma URL de vídeo que contém `&list=...` (muito comum ao copiar do YouTube), o yt-dlp baixa a **playlist inteira**, todos com o mesmo `outtmpl` fixo (`titulo.mp4`) → cada vídeo sobrescreve o anterior e a validação de duração falha.
**Correção:** no fluxo de vídeo único, `noplaylist: True` sempre. Playlist tem fluxo próprio (opção 3).

### 3. `_extract_audio_simple` ignora o formato configurado
Hardcoded `libmp3lame` mesmo se `audio_format` for `aac`. Gera um arquivo `.aac` com conteúdo MP3.

### 4. `_extract_video_info` não usa as opções robustas
Usa `yt_dlp.YoutubeDL({'quiet': True})` cru, sem `build_ydl_opts()`. Se um dia voltar a precisar de `extractor_args`/retries, a extração de info falha enquanto o download funcionaria. Inconsistência que já causou confusão no passado (bug do player_client).

### 5. Colisão de nomes sobrescreve download anterior
`sanitize_filename` remove acentos e trunca em 100 chars. Dois vídeos com títulos parecidos → mesmo arquivo, sem aviso. **Correção:** se o destino existe, sufixar `-2`, `-3`… ou usar o ID do vídeo no nome.

### 6. Barra de progresso vaza em erro
`ProgressManager.hook` só fecha o tqdm no status `finished`. Se o download aborta, a barra fica aberta e corrompe o terminal na próxima impressão. Tratar status `error` e usar `finally`.

---

## 🟠 Melhorias de alto impacto

### 7. Baixar áudio direto em vez de vídeo → extração (opção 1 e 2)
Hoje o fluxo "vídeo único" baixa o MP4 (ex.: 1,35 GB) e re-encoda o áudio via ffmpeg. Se o objetivo final é o MP3:
- **2 passos caros** (download grande + re-encode CPU);
- **perda de qualidade** (AAC do YouTube → MP3 é transcodificação com perdas).
O fluxo `download_audio_only` (opção 9) já faz certo com postprocessor. Sugestão: na opção 2 (completo), baixar vídeo e áudio **em paralelo como formatos separados** ou extrair o áudio com `-c copy` para `.m4a` (sem re-encode, instantâneo) e só converter pra MP3 se o usuário precisar.

### 8. Migrar Whisper → faster-whisper
`openai-whisper` em CPU no modelo medium leva horas num sermão de 69 min. `faster-whisper` (CTranslate2) roda o mesmo modelo **4–8× mais rápido** em CPU com a mesma qualidade, API quase idêntica e suporte a `word_timestamps`. É a melhoria com melhor custo/benefício do projeto inteiro.

### 9. Interface por argumentos (CLI) além do menu
Tudo hoje exige menu interativo. Um `argparse` simples habilitaria automação (inclusive pelas suas routines):
```
python youtube_downloader.py --audio URL
python youtube_downloader.py --complete URL --whisper-model small
```
O menu continua como fallback quando chamado sem argumentos.

### 10. Transcrição com timestamps por palavra → cortes mais precisos
O `SermonCutAnalyzer` corta nos limites dos segmentos do Whisper (frases de ~5-15s). Com `word_timestamps` (faster-whisper), os cortes podem começar/terminar exatamente na palavra, evitando clipes que começam no meio de uma frase.

### 11. Retomar pipeline após falha (opção 2)
Se a transcrição falha no minuto 50, o vídeo e o áudio já baixados são esquecidos — rodar de novo refaz tudo. Um manifesto simples (`estado.json` na pasta do vídeo: baixado ✓, extraído ✓, transcrito ✗) permitiria retomar do ponto em que parou.

---

## 🟡 Qualidade e manutenção

12. **Dividir o monólito** (1617 linhas) em módulos: `downloader.py`, `extractor.py`, `transcriber.py`, `analyzer.py`, `ui.py`, `config.py`. Facilita teste e reuso.
13. **Zero testes.** As funções puras (`sanitize_filename`, `_parse_time`, `verify_integrity`, todo o `SermonCutAnalyzer`) são fáceis de testar com pytest — o analisador de cortes em especial merece testes de regressão, pois qualquer ajuste de pesos muda o resultado silenciosamente.
14. **Retry indiscriminado**: `download_video` re-tenta 3× até para erros permanentes (vídeo privado, removido, geo-block). Classificar exceções do yt-dlp (`DownloadError` com "Private video", "unavailable") e falhar rápido nesses casos.
15. **`download_playlist` re-extrai info 2×** por vídeo (uma na listagem, outra em `download_video`). Usar `extract_flat` na listagem.
16. **Duplicação**: os 3 fluxos de download repetem o bloco "extrai info → sanitiza → monta opts → baixa → localiza arquivo → valida". Extrair um método comum `_fetch(url, opts) -> Path`.
17. **`YTDlpLogger` engole tudo em `debug`** — inclusive mensagens úteis de pós-processamento. Encaminhar para `logging.debug` em vez de `pass`, aí um `--verbose` habilita diagnóstico sem mudar código.
18. **Config sem validação**: `audio_quality` aceita qualquer string ("abc" → erro criptico do ffmpeg). Validar com regex `^\d+k$` ao salvar.
19. **`requirements.txt` sem pin** de versões testadas (`yt-dlp>=2025.6.9` ok, mas um `pip freeze > requirements.lock` documentaria o ambiente que funciona).
20. **Thread de progresso do ffmpeg**: usar `-progress pipe:1` do ffmpeg em vez de regex no stderr — formato estável chave=valor, sem parsing frágil.

---

## Sugestão de ordem de ataque

| Fase | Itens | Esforço |
|------|-------|---------|
| 1. Correções | #1, #2, #3, #5, #6 | ~1h |
| 2. Ganho rápido | #8 (faster-whisper), #7 (m4a sem re-encode) | ~2h |
| 3. Automação | #9 (CLI), #11 (retomada) | ~2-3h |
| 4. Estrutura | #12 (módulos), #13 (testes) | contínuo |
