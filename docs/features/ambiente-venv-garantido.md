# Garantia de ambiente (venv) — correção do HTTP 403

## Visão geral

O `youtube_downloader.py` usa a **biblioteca Python `yt_dlp`** (`import yt_dlp`), não o
binário do brew. Quando o script era iniciado com o `python3` global do sistema, ele
carregava a cópia da lib instalada nesse Python — em 2026-08-24 essa cópia estava na
versão `2026.03.17` (160 dias) e o YouTube respondia **HTTP 403 Forbidden** em todo
download (opção 9 — "Baixar somente áudio" — e demais opções).

O venv do projeto tinha a versão `2026.08.19`, que baixa normalmente. Ou seja: o mesmo
vídeo falhava ou funcionava dependendo apenas de qual Python iniciou o script.

## Comportamento

Um bloco no topo de `youtube_downloader.py`, antes de qualquer import da lib, compara
`sys.prefix` com a pasta `venv/` do projeto. Se forem diferentes e o venv existir, o
script se reexecuta com `venv/bin/python3` via `os.execv`:

```
🔁 Reexecutando no venv do projeto: /Users/felipetome/Documents/DownloadYoutube/venv/bin/python3
```

A variável de ambiente `YTDL_VENV_REEXEC=1` marca o processo já relançado e impede
qualquer laço de reexecução. Em Windows, o alvo é `venv/Scripts/python.exe`.

A comparação usa `sys.prefix` (e **não** `sys.executable`) porque `venv/bin/python3` é um
symlink para o mesmo binário do Homebrew — comparar os executáveis resolvidos dá falso
negativo e o relaunch nunca acontece.

## Arquivos alterados

- `youtube_downloader.py` — bloco "GARANTIA DE AMBIENTE (venv do projeto)" no topo.

## Como testar

```bash
# Deve imprimir a linha "🔁 Reexecutando no venv do projeto: ..." e não avisar sobre
# biblioteca yt-dlp antiga:
echo "0" | /opt/homebrew/bin/python3 youtube_downloader.py | head -4

# Download real (opção 9) num vídeo curto:
venv/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from youtube_downloader import YouTubeDownloader, DownloadConfig
d = YouTubeDownloader(DownloadConfig(output_dir='downloads'))
print(d.download_audio_only('https://www.youtube.com/watch?v=jNQXAC9IVRw'))
"
```

## Manutenção

O aviso de `check_dependencies()` dispara quando a lib do venv passa de 45 dias. Ao vê-lo:

```bash
venv/bin/pip install -U yt-dlp
```

Nota sobre o CLI: `which -a yt-dlp` mostra `~/Library/Python/3.14/bin/yt-dlp` (2026.03.17)
antes de `/opt/homebrew/bin/yt-dlp`. Isso não afeta o script, mas o uso manual do comando
`yt-dlp` no terminal pega a versão antiga e dá 403.
