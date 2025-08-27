import yt_dlp
import os
import re
import unicodedata
import subprocess
import logging

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
        audio_filename = os.path.join(output_dir, f"{safe_title}.mp3")

        # yt-dlp: baixa o vídeo completo em MP4
        ydl_opts = {
            'format': 'best',
            'outtmpl': video_filename,
            'quiet': False,
            'no_warnings': True,
            'noplaylist': True,
            'logger': YTDlpLogger(),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # ffmpeg: converte para MP3
        if os.path.exists(video_filename):
            logging.info(f"🎬 Vídeo baixado: {video_filename}")
            logging.info("🎧 Extraindo áudio com ffmpeg...")

            command = [
                "ffmpeg", "-y", "-i", video_filename,
                "-vn", "-acodec", "libmp3lame", "-ab", "192k", audio_filename
            ]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(audio_filename):
                logging.info(f"✅ Áudio extraído com sucesso: {audio_filename}")
                # Remover o .mp4 original se desejar
                os.remove(video_filename)
                return audio_filename
            else:
                logging.error("❌ Falha ao converter para MP3.")
                return None
        else:
            logging.error("❌ Vídeo .mp4 não foi baixado.")
            return None

    except Exception as e:
        logging.exception("❌ Erro durante o processo de download/conversão")
        return None

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
        print("1. 📥 Baixar vídeo e extrair áudio")
        print("2. ❌ Sair")

        choice = input("\nDigite sua escolha (1-2): ").strip()

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
            logging.info("👋 Até logo!")
            break
        else:
            logging.warning("❌ Opção inválida! Digite 1 ou 2.")

# ========== LOGGER DO YT-DLP ==========
class YTDlpLogger:
    def debug(self, msg): logging.debug(msg)
    def warning(self, msg): logging.warning(msg)
    def error(self, msg): logging.error(msg)

if __name__ == '__main__':
    main()
