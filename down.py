import yt_dlp
import os
import re
import unicodedata
import subprocess
import logging
from tqdm import tqdm
import time

# ========== LOGGING ==========
logging.basicConfig(
    filename="log_download.txt",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(console)

# ========== SANITIZAÇÃO ==========
def sanitize_filename(title):
    title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'\s+', '-', title)
    title = re.sub(r'-+', '-', title)
    return title.strip('-').lower()

# ========== PROGRESS HOOK DOWNLOAD ==========
progress_bar = None
def my_hook(d):
    global progress_bar
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded = d.get('downloaded_bytes', 0)

        if total_bytes:
            if progress_bar is None:
                progress_bar = tqdm(total=total_bytes, unit='B', unit_scale=True, desc='🔽 Baixando')
            progress_bar.n = downloaded
            progress_bar.refresh()

    elif d['status'] == 'finished':
        if progress_bar:
            progress_bar.n = progress_bar.total
            progress_bar.close()
            print("✅ Download finalizado.")
            logging.info("✅ Download finalizado.")

# ========== EXTRAIR ÁUDIO COM PROGRESSO ==========
def extract_audio_with_progress(video_path, output_dir="downloads"):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, base_name + ".mp3")

    logging.info(f"🎧 Extraindo áudio: {base_name}.mp3")

    # Obtém a duração total do vídeo (em segundos)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        total_duration = float(result.stdout.strip())
    except:
        total_duration = None

    bar = tqdm(total=100, desc="🎚️  Convertendo para MP3", unit="%") if total_duration else None

    # Inicia o processo do ffmpeg com progresso
    process = subprocess.Popen(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", audio_path, "-progress", "pipe:1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    current_percent = 0
    while True:
        line = process.stdout.readline()
        if line == '' and process.poll() is not None:
            break
        if "out_time_ms=" in line and total_duration:
            try:
                ms = int(line.strip().split('=')[1])
                seconds = ms / 1_000_000
                percent = int((seconds / total_duration) * 100)
                if percent > current_percent:
                    bar.update(percent - current_percent)
                    current_percent = percent
            except:
                pass

    if bar:
        bar.n = 100
        bar.close()

    if os.path.exists(audio_path):
        logging.info(f"✅ Áudio extraído com sucesso: {audio_path}")
        return audio_path
    else:
        logging.error("❌ Falha ao converter para MP3.")
        return None

# ========== DOWNLOAD ==========
def download_youtube_video(url, output_dir="downloads"):
    logging.info("📥 Iniciando download completo do vídeo do YouTube...")
    logging.info(f"🔗 URL: {url}")

    try:
        os.makedirs(output_dir, exist_ok=True)

        # Primeiro, extrai informações
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            logging.info(f"📺 Título: {title}")
            logging.info(f"⏱️  Duração: {duration//60}min {duration%60}s")

        safe_title = sanitize_filename(title)
        video_filename = os.path.join(output_dir, f"{safe_title}.mp4")

        ydl_opts = {
            'format': 'best',
            'outtmpl': video_filename,
            'quiet': False,
            'no_warnings': True,
            'noplaylist': True,
            'logger': YTDlpLogger(),
            'progress_hooks': [my_hook],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(video_filename):
            return extract_audio_with_progress(video_filename, output_dir)
        else:
            logging.error("❌ Vídeo .mp4 não foi baixado.")
            return None

    except Exception as e:
        logging.exception("❌ Erro durante o processo de download/conversão")
        return None

# ========== LISTAR VÍDEOS EXISTENTES ==========
def list_and_extract_existing_video():
    directory = "downloads"
    files = [f for f in os.listdir(directory) if f.endswith(".mp4")]
    if not files:
        print("❌ Nenhum vídeo encontrado em 'downloads/'.")
        return

    print("\n📂 Vídeos disponíveis:")
    for i, f in enumerate(files, start=1):
        print(f"{i}. {f}")

    while True:
        choice = input("\nDigite o número do vídeo para extrair o áudio (ou '0' para cancelar): ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            selected_file = os.path.join(directory, files[int(choice)-1])
            extract_audio_with_progress(selected_file, directory)
            return
        else:
            print("❌ Escolha inválida. Tente novamente.")

# ========== URL ==========
def get_youtube_url():
    while True:
        url = input("\n🔗 Digite a URL do vídeo do YouTube: ").strip()
        if "youtube.com" in url or "youtu.be" in url:
            return url
        else:
            print("❌ URL inválida! Digite uma URL válida do YouTube.")

# ========== MAIN ==========
def main():
    logging.info("🎵 === DOWNLOADER DE ÁUDIO DO YOUTUBE ===")
    while True:
        print("\n" + "="*50)
        print("Escolha uma opção:")
        print("1. 📥 Baixar vídeo do YouTube e extrair áudio")
        print("2. 🎧 Converter vídeo existente da pasta 'downloads/'")
        print("3. ❌ Sair")

        choice = input("\nDigite sua escolha (1-3): ").strip()

        if choice == "1":
            url = get_youtube_url()
            if url:
                downloaded_file = download_youtube_video(url)
                if downloaded_file:
                    logging.info(f"\n🎉 Download e conversão concluídos com sucesso!")
                    logging.info(f"📁 Arquivo salvo: {downloaded_file}")
                else:
                    logging.error("❌ Falha no processo completo.")
        elif choice == "2":
            list_and_extract_existing_video()
        elif choice == "3":
            logging.info("👋 Até logo!")
            break
        else:
            logging.warning("❌ Opção inválida! Digite 1, 2 ou 3.")

# ========== LOGGER DO YT-DLP ==========
class YTDlpLogger:
    def debug(self, msg): logging.debug(msg)
    def warning(self, msg): logging.warning(msg)
    def error(self, msg): logging.error(msg)

if __name__ == '__main__':
    main()
