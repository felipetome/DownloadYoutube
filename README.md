# 🎵 YouTube Downloader — Áudio, Transcrição e Cortes

Ferramenta de linha de comando em Python para **baixar vídeos e áudios do YouTube**, **transcrever** a fala com o Whisper (OpenAI) e **sugerir cortes** automaticamente — pensada especialmente para reaproveitar pregações e palestras em clipes curtos.

Tudo roda por um **menu interativo** no terminal, sem precisar decorar comandos.

---

## ✨ Recursos

| # | Recurso | O que faz |
|---|---------|-----------|
| 1 | **Baixar vídeo único** | Baixa o MP4 na melhor qualidade e extrai o áudio (MP3). |
| 2 | **Baixar completo** | Cria uma pasta com vídeo + thumbnail + áudio + transcrição + relatório de cortes. |
| 3 | **Baixar playlist** | Baixa vários vídeos de uma playlist (limite configurável). |
| 4 | **Converter vídeo existente** | Extrai o áudio de um vídeo já salvo em `downloads/`. |
| 5 | **Transcrever áudio** | Gera um `.txt` com timestamps usando o Whisper. |
| 6 | **Analisar cortes** | Lê uma transcrição e sugere os melhores trechos para clipes. |
| 9 | **Baixar somente áudio** | Baixa direto o áudio (sem passar pelo vídeo). |

Recursos de robustez embutidos:

- ✅ **Validação de integridade** — compara a duração baixada com a esperada e aborta se o arquivo vier truncado (evita MP3 cortado silenciosamente).
- ✅ **Retentativas automáticas** de download e de fragmentos.
- ✅ **Seleção automática de client do YouTube** — sem forçar `web/ios`, que hoje exigem PO Token e falham.
- ✅ **Divisão de áudios longos** em partes de ~29 min (útil para uploads com limite de duração).

---

## 📋 Pré-requisitos

- **Python 3.10+** (testado em 3.14)
- **FFmpeg** e **FFprobe** no `PATH` — usados para converter e medir a duração das mídias:

  ```bash
  # macOS
  brew install ffmpeg

  # Ubuntu / Debian
  sudo apt install ffmpeg

  # Windows: baixe em https://www.gyan.dev/ffmpeg/builds/ e adicione ao PATH
  ```

> ℹ️ O Whisper precisa de bastante RAM/CPU. Em máquinas sem GPU, a transcrição de áudios longos (>30 min) com o modelo `medium` pode levar **horas**. Veja [Dicas de desempenho](#-dicas-de-desempenho).

---

## 🚀 Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/felipetome/DownloadYoutube.git
cd DownloadYoutube

# 2. Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt
```

> Na **primeira transcrição**, o Whisper baixa automaticamente o modelo escolhido (o `medium` tem ~1.5 GB).

---

## ▶️ Como usar (passo a passo)

Com o ambiente virtual ativado:

```bash
python youtube_downloader.py
```

Você verá o menu:

```
============================================================
🎵 DOWNLOADER DE ÁUDIO DO YOUTUBE - VERSÃO MELHORADA
============================================================
1. 📥 Baixar vídeo único
2. 📦 Baixar completo (pasta + áudio + transcrição + cortes)
3. 📋 Baixar playlist
4. 🎧 Converter vídeo existente
5. 📝 Transcrever áudio existente
6. 🎬 Analisar transcrição para cortes
7. ⚙️  Configurações
8. 📁 Abrir pasta de downloads
9. 🎵 Baixar somente áudio
0. ❌ Sair
```

Digite o número da opção e siga as instruções na tela.

### Exemplo 1 — Só o áudio (MP3)

1. Escolha a opção **9**.
2. Cole a URL do vídeo (ex.: `https://www.youtube.com/watch?v=XXXXXXXXXXX`).
3. O MP3 aparece em `downloads/`.

### Exemplo 2 — Fluxo completo (vídeo + transcrição + cortes)

1. Escolha a opção **2**.
2. Cole a URL do vídeo.
3. O programa cria uma pasta em `downloads/<titulo>/` contendo:
   - o **vídeo** `.mp4` e a **thumbnail**;
   - o **áudio** (dividido em partes de ~29 min, se for longo);
   - a **transcrição** `.txt` com timestamps;
   - o **relatório de cortes** (`_cortes.txt` e `_cortes.json`).

### Exemplo 3 — Transcrever um áudio que você já tem

1. Coloque o arquivo de áudio em `downloads/`.
2. Escolha a opção **5**, selecione o arquivo, o idioma (`pt` por padrão) e o modelo do Whisper.

---

## ⚙️ Configurações

Acesse pelo menu (opção **7**). As preferências são salvas em `download_config.json`:

| Configuração | Padrão | Descrição |
|--------------|--------|-----------|
| `output_dir` | `downloads` | Pasta de saída. |
| `audio_format` | `mp3` | Formato do áudio (`mp3`, `aac`, `m4a`). |
| `audio_quality` | `192k` | Bitrate do áudio. |
| `video_format` | `bestvideo+bestaudio/best` | Seleção de qualidade do yt-dlp. |
| `max_retries` | `3` | Tentativas por download. |
| `enable_playlist` | `true` | Permitir baixar playlists. |
| `max_playlist_items` | `10` | Máximo de itens por playlist. |
| `whisper_model` | `medium` | Modelo do Whisper (`tiny`→`large`). |
| `duration_tolerance_pct` | `2.0` | Tolerância (%) para considerar o download completo. |

---

## 🎬 Análise de cortes (para pregações/palestras)

A classe `SermonCutAnalyzer` percorre a transcrição e pontua trechos com base em sinais como:

- **Perguntas retóricas** e **chamados à ação** ("levante", "ore", "repita comigo"…)
- **Intensidade emocional** e **repetição** (ênfase do orador)
- **Referências bíblicas** e **conteúdo de ensino**
- **Narrativas / testemunhos**

Cada trecho recebe uma nota de 0 a 10 e uma classificação de tema (Ensino Bíblico, Testemunho, Chamado ao Altar, etc.). O resultado é salvo em `.txt` (legível) e `.json` (para automação).

> Os pesos e as palavras-chave estão no topo da classe `SermonCutAnalyzer` em `youtube_downloader.py` — ajuste conforme o seu conteúdo.

---

## 🧠 Estrutura do código

Tudo está em **`youtube_downloader.py`**, organizado em classes:

| Classe | Responsabilidade |
|--------|------------------|
| `DownloadConfig` / `ConfigManager` | Configuração e persistência em JSON. |
| `YouTubeDownloader` | Orquestra downloads (vídeo, áudio, playlist, completo). |
| `AudioExtractor` | Extrai e divide o áudio via FFmpeg. |
| `AudioTranscriber` | Transcrição com Whisper. |
| `SermonCutAnalyzer` | Pontuação e sugestão de cortes. |
| `ProgressManager` | Barra de progresso do download. |
| `UserInterface` | Menu interativo. |

Funções auxiliares importantes:

- `build_ydl_opts()` — base robusta de opções do yt-dlp (retentativas, aborta em fragmento faltando, deixa o client padrão do YouTube).
- `verify_integrity()` — detecta arquivos truncados comparando durações via `ffprobe`.

---

## ⚡ Dicas de desempenho

- **Modelo do Whisper**: `medium` tem boa qualidade em PT-BR, mas é lento em CPU. Para áudios muito longos, `small` é um bom equilíbrio; `tiny`/`base` são rápidos, porém imprecisos.
- **Áudios longos**: o programa divide automaticamente em partes de ~29 min. Transcreva por partes se quiser paralelizar.
- **GPU**: com CUDA disponível, o Whisper acelera drasticamente.

---

## 🛠️ Solução de problemas

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `❌ 'ffmpeg' não encontrado` | FFmpeg fora do PATH | Instale o FFmpeg (veja pré-requisitos). |
| `Requested format is not available` / "Only images are available" | Client do YouTube exigindo PO Token | Atualize o yt-dlp: `pip install -U yt-dlp`. O código já usa o client padrão. |
| Download trava ou vem incompleto | yt-dlp desatualizado | `pip install -U yt-dlp` (o YouTube muda os formatos com frequência). |
| Transcrição demora horas | Whisper em CPU | Use um modelo menor (`small`) ou uma máquina com GPU. |
| `⚠️ Biblioteca yt-dlp ... dias` | Versão antiga da lib | Atualize o yt-dlp. |

---

## ⚖️ Uso responsável

Este projeto é para fins **pessoais e educacionais**. Baixe apenas conteúdo que você tem direito de usar e respeite os [Termos de Serviço do YouTube](https://www.youtube.com/t/terms) e a legislação de direitos autorais aplicável.

---

## 📄 Licença

Uso livre para fins pessoais e educacionais. Ajuste conforme a sua necessidade.
