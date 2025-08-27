import yt_dlp
import os
import re
import unicodedata
import logging
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from tqdm import tqdm
import time

# ========== CONFIGURAÇÕES ==========
@dataclass
class DownloadConfig:
    output_dir: str = "downloads"
    video_format: str = "best"
    max_retries: int = 3
    retry_delay: int = 5
    enable_playlist: bool = True
    max_playlist_items: int = 10

class ConfigManager:
    def __init__(self, config_file: str = "download_config_simple.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> DownloadConfig:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return DownloadConfig(**data)
            except Exception as e:
                print(f"⚠️ Erro ao carregar configuração: {e}")
        
        return DownloadConfig()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config.__dict__, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Erro ao salvar configuração: {e}")

# ========== LOGGING SIMPLES ==========
def setup_logging():
    """Configuração simples de logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

# ========== SANITIZAÇÃO ==========
def sanitize_filename(title: str, max_length: int = 100) -> str:
    """Sanitização de nomes de arquivo"""
    title = unicodedata.normalize('NFKD', title).encode('ASCII', 'ignore').decode('utf-8')
    title = re.sub(r'[^\w\s\-\.]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    if len(title) > max_length:
        title = title[:max_length-3] + "..."
    
    title = re.sub(r'\s+', '-', title)
    title = re.sub(r'-+', '-', title)
    
    return title.strip('-').lower()

# ========== PROGRESS HOOK ==========
class ProgressManager:
    def __init__(self):
        self.progress_bar = None
        self.start_time = None
    
    def hook(self, d: Dict[str, Any]):
        """Hook para progresso de download"""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            
            if total_bytes and not self.progress_bar:
                self.start_time = time.time()
                self.progress_bar = tqdm(
                    total=total_bytes,
                    unit='B',
                    unit_scale=True,
                    desc='🔽 Baixando',
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                )
            
            if self.progress_bar:
                self.progress_bar.n = downloaded
                if speed:
                    self.progress_bar.set_postfix({'Speed': f"{speed/1024/1024:.1f}MB/s"})
                self.progress_bar.refresh()
        
        elif d['status'] == 'finished':
            if self.progress_bar:
                self.progress_bar.n = self.progress_bar.total
                self.progress_bar.close()
                elapsed = time.time() - self.start_time if self.start_time else 0
                print(f"✅ Download finalizado em {elapsed:.1f}s")
            self.progress_bar = None
            self.start_time = None

# ========== DOWNLOADER PRINCIPAL ==========
class YouTubeDownloader:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.progress_manager = ProgressManager()
        self.setup_output_dir()
    
    def setup_output_dir(self):
        """Configura o diretório de saída"""
        Path(self.config.output_dir).mkdir(exist_ok=True)
    
    def download_video(self, url: str, playlist_index: Optional[int] = None) -> Optional[str]:
        """Download principal com retry"""
        for attempt in range(self.config.max_retries):
            try:
                return self._download_single_video(url, playlist_index)
            except Exception as e:
                print(f"⚠️ Tentativa {attempt + 1} falhou: {e}")
                if attempt < self.config.max_retries - 1:
                    print(f"🔄 Tentando novamente em {self.config.retry_delay}s...")
                    time.sleep(self.config.retry_delay)
                else:
                    print("❌ Todas as tentativas falharam")
                    return None
    
    def _download_single_video(self, url: str, playlist_index: Optional[int] = None) -> Optional[str]:
        """Download de um único vídeo"""
        print(f"📥 Iniciando download: {url}")
        
        # Extrai informações
        info = self._extract_video_info(url)
        if not info:
            return None
        
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        
        print(f"📺 Título: {title}")
        if duration:
            print(f"⏱️ Duração: {duration//60}min {duration%60}s")
        
        # Nome do arquivo
        safe_title = sanitize_filename(title)
        if playlist_index is not None:
            safe_title = f"{playlist_index:02d}_{safe_title}"
        
        video_filename = Path(self.config.output_dir) / f"{safe_title}.mp4"
        
        # Configurações do yt-dlp
        ydl_opts = {
            'format': self.config.video_format,
            'outtmpl': str(video_filename),
            'quiet': False,
            'no_warnings': True,
            'noplaylist': not self.config.enable_playlist,
            'logger': YTDlpLogger(),
            'progress_hooks': [self.progress_manager.hook],
            'ignoreerrors': True,
        }
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if video_filename.exists():
            print(f"✅ Vídeo baixado: {video_filename}")
            return str(video_filename)
        else:
            print("❌ Vídeo não foi baixado")
            return None
    
    def _extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extrai informações do vídeo"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"❌ Erro ao extrair informações: {e}")
            return None
    
    def download_playlist(self, url: str) -> List[str]:
        """Download de playlist"""
        print(f"📋 Iniciando download de playlist: {url}")
        
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                
            if info.get('_type') != 'playlist':
                print("⚠️ URL não é uma playlist")
                return [self.download_video(url)]
            
            entries = info.get('entries', [])
            if not entries:
                print("❌ Playlist vazia")
                return []
            
            print(f"📋 Playlist com {len(entries)} vídeos")
            
            downloaded_files = []
            for i, entry in enumerate(entries[:self.config.max_playlist_items], 1):
                if not entry:
                    continue
                
                video_url = entry.get('url') or entry.get('webpage_url')
                if not video_url:
                    continue
                
                print(f"📥 Baixando vídeo {i}/{len(entries)}")
                result = self.download_video(video_url, i)
                if result:
                    downloaded_files.append(result)
                
                # Pausa entre downloads
                if i < len(entries):
                    time.sleep(1)
            
            return downloaded_files
            
        except Exception as e:
            print(f"❌ Erro no download da playlist: {e}")
            return []

# ========== INTERFACE DO USUÁRIO ==========
class UserInterface:
    def __init__(self, downloader: YouTubeDownloader, config_manager: ConfigManager):
        self.downloader = downloader
        self.config_manager = config_manager
    
    def show_menu(self):
        """Menu principal"""
        while True:
            print("\n" + "="*60)
            print("🎵 DOWNLOADER DE VÍDEO DO YOUTUBE - VERSÃO SIMPLES")
            print("="*60)
            print("⚠️  NOTA: Esta versão baixa apenas vídeos (sem conversão de áudio)")
            print("📥 Para converter para áudio, instale o FFmpeg")
            print("="*60)
            print("1. 📥 Baixar vídeo único")
            print("2. 📋 Baixar playlist")
            print("3. ⚙️  Configurações")
            print("4. 📁 Abrir pasta de downloads")
            print("5. ❌ Sair")
            print("-"*60)
            
            choice = input("Escolha uma opção (1-5): ").strip()
            
            if choice == "1":
                self.download_single_video()
            elif choice == "2":
                self.download_playlist()
            elif choice == "3":
                self.show_settings()
            elif choice == "4":
                self.open_downloads_folder()
            elif choice == "5":
                print("👋 Até logo!")
                break
            else:
                print("❌ Opção inválida!")
    
    def download_single_video(self):
        """Download de vídeo único"""
        url = self._get_youtube_url()
        if url:
            result = self.downloader.download_video(url)
            if result:
                print(f"✅ Download concluído: {result}")
            else:
                print("❌ Falha no download")
    
    def download_playlist(self):
        """Download de playlist"""
        url = self._get_youtube_url()
        if url:
            results = self.downloader.download_playlist(url)
            if results:
                print(f"✅ Playlist baixada: {len(results)} arquivos")
                for result in results:
                    print(f"  📁 {result}")
            else:
                print("❌ Falha no download da playlist")
    
    def show_settings(self):
        """Configurações do programa"""
        while True:
            print("\n" + "="*40)
            print("⚙️ CONFIGURAÇÕES")
            print("="*40)
            config = self.config_manager.config
            
            print(f"1. 📁 Pasta de saída: {config.output_dir}")
            print(f"2. 📹 Formato de vídeo: {config.video_format}")
            print(f"3. 🔄 Tentativas máximas: {config.max_retries}")
            print(f"4. 📋 Suporte a playlist: {'Sim' if config.enable_playlist else 'Não'}")
            print(f"5. 📊 Máximo de itens na playlist: {config.max_playlist_items}")
            print("6. 💾 Salvar configurações")
            print("7. ↩️ Voltar")
            
            choice = input("\nEscolha uma opção (1-7): ").strip()
            
            if choice == "1":
                new_dir = input(f"Nova pasta de saída (atual: {config.output_dir}): ").strip()
                if new_dir:
                    config.output_dir = new_dir
            elif choice == "2":
                new_format = input(f"Novo formato (atual: {config.video_format}): ").strip()
                if new_format:
                    config.video_format = new_format
            elif choice == "3":
                try:
                    new_retries = int(input(f"Novo número de tentativas (atual: {config.max_retries}): ").strip())
                    if new_retries > 0:
                        config.max_retries = new_retries
                except ValueError:
                    print("❌ Digite um número válido!")
            elif choice == "4":
                config.enable_playlist = not config.enable_playlist
            elif choice == "5":
                try:
                    new_max = int(input(f"Novo máximo (atual: {config.max_playlist_items}): ").strip())
                    if new_max > 0:
                        config.max_playlist_items = new_max
                except ValueError:
                    print("❌ Digite um número válido!")
            elif choice == "6":
                self.config_manager.save_config()
                print("✅ Configurações salvas!")
            elif choice == "7":
                break
            else:
                print("❌ Opção inválida!")
    
    def open_downloads_folder(self):
        """Abre a pasta de downloads"""
        downloads_path = Path(self.config_manager.config.output_dir)
        if downloads_path.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(downloads_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", downloads_path])
                else:
                    subprocess.run(["xdg-open", downloads_path])
                print(f"📁 Pasta aberta: {downloads_path}")
            except Exception as e:
                print(f"❌ Erro ao abrir pasta: {e}")
        else:
            print(f"❌ Pasta '{downloads_path}' não existe")
    
    def _get_youtube_url(self) -> Optional[str]:
        """Obtém URL do YouTube com validação"""
        while True:
            url = input("\n🔗 Digite a URL do YouTube: ").strip()
            if not url:
                continue
            
            if any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'music.youtube.com']):
                return url
            else:
                print("❌ URL inválida! Digite uma URL válida do YouTube.")

# ========== LOGGER DO YT-DLP ==========
class YTDlpLogger:
    def debug(self, msg): pass
    def warning(self, msg): print(f"⚠️ {msg}")
    def error(self, msg): print(f"❌ {msg}")

# ========== FUNÇÃO PRINCIPAL ==========
def main():
    """Função principal"""
    print("🎵 Iniciando Downloader de Vídeo do YouTube (Versão Simples)...")
    
    # Configura logging
    setup_logging()
    
    try:
        # Inicializa componentes
        config_manager = ConfigManager()
        downloader = YouTubeDownloader(config_manager.config)
        ui = UserInterface(downloader, config_manager)
        
        # Executa interface
        ui.show_menu()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Programa interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
    finally:
        print("🛑 Programa finalizado")

if __name__ == '__main__':
    main()
