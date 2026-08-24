#!/usr/bin/env python3
"""Baixa o áudio (MP3) de um vídeo do YouTube usando a lib yt_dlp.

Uso:
    venv/bin/python3 baixar_audio.py "https://www.youtube.com/watch?v=ID"

Trata os erros mais comuns (formato indisponível/PO token, ffmpeg ausente,
rede/vídeo indisponível) e imprime uma saída limpa — sem barra de progresso.
"""
import os as _os
import sys as _sys
from pathlib import Path as _Path

# Roda sempre no venv do projeto: fora dele a lib `yt_dlp` está ausente ou antiga
# (versão antiga => HTTP 403 Forbidden do YouTube).
_PROJ = _Path(__file__).resolve().parent
_VENV_PY = _PROJ / ("venv/Scripts/python.exe" if _os.name == "nt" else "venv/bin/python3")
if (_VENV_PY.exists()
        and _Path(_sys.prefix).resolve() != (_PROJ / "venv").resolve()
        and not _os.environ.get("YTDL_VENV_REEXEC")):
    _os.environ["YTDL_VENV_REEXEC"] = "1"
    _os.execv(str(_VENV_PY), [str(_VENV_PY), str(_Path(__file__).resolve()), *_sys.argv[1:]])

import shutil
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("erro: yt_dlp não instalado. Rode: venv/bin/pip install -U yt-dlp")

DEST = Path(__file__).parent / "downloads"


class _SilentLogger:
    """Suprime o ruído do yt-dlp; só deixa passar erros de verdade."""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg, file=sys.stderr)


def _hook(d):
    """Progresso resumido: uma linha por etapa, sem poluir o terminal."""
    if d["status"] == "finished":
        nome = Path(d["filename"]).name
        print(f"  baixado: {nome} — convertendo para MP3...")


def _base_opts():
    return {
        "format": "bestaudio/best",
        "outtmpl": str(DEST / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "logger": _SilentLogger(),
        "progress_hooks": [_hook],
        "noprogress": True,
        "ignoreerrors": False,  # nunca silenciar erro — evita MP3 truncado
        "retries": 5,
        "fragment_retries": 5,
    }


def baixar(url: str) -> Path:
    """Baixa o áudio e devolve o caminho do MP3 gerado. Levanta em falha."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg não encontrado no PATH — necessário para gerar MP3. "
            "Instale com: brew install ffmpeg"
        )

    DEST.mkdir(exist_ok=True)
    opts = _base_opts()

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # caminho final do MP3 após o pós-processamento
        mp3 = DEST / f"{ydl.prepare_filename(info, outtmpl='%(title)s')}.mp3"
        return mp3


def main():
    if len(sys.argv) < 2:
        sys.exit(f"uso: {Path(sys.argv[0]).name} <url-do-youtube>")

    url = sys.argv[1]
    print(f"Baixando áudio de: {url}")
    try:
        mp3 = baixar(url)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Requested format is not available" in msg:
            sys.exit(
                "erro: formato indisponível. NÃO force player_client web/ios "
                "(exige PO Token). Use a config padrão."
            )
        if "Video unavailable" in msg or "Private video" in msg:
            sys.exit("erro: vídeo indisponível, privado ou removido.")
        sys.exit(f"erro de download: {msg}")
    except RuntimeError as e:
        sys.exit(f"erro: {e}")
    except Exception as e:
        sys.exit(f"erro inesperado ({type(e).__name__}): {e}")

    if mp3.exists():
        tam = mp3.stat().st_size / (1024 * 1024)
        print(f"OK — {mp3.name} ({tam:.1f} MB)")
        print(f"salvo em: {mp3}")
    else:
        sys.exit("erro: download terminou mas o MP3 não foi encontrado.")


if __name__ == "__main__":
    main()
