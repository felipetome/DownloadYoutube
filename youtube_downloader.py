import yt_dlp
import os
import re
import shutil
import unicodedata
import logging
import json
import sys
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, fields
from datetime import datetime
from tqdm import tqdm
import time
import threading
import whisper

# ========== SUPRESSÃO DE WARNINGS COSMÉTICOS (Python 3.14 + yt-dlp) ==========
# O Python 3.14 imprime "Exception ignored while finalizing file ... I/O operation
# on closed file" quando o GC fecha conexões HTTP que o yt-dlp já encerrou. É inofensivo.
_original_unraisablehook = sys.unraisablehook


def _quiet_unraisablehook(unraisable):
    exc = unraisable.exc_value
    if isinstance(exc, ValueError) and "closed file" in str(exc):
        return  # ignora silenciosamente
    _original_unraisablehook(unraisable)


sys.unraisablehook = _quiet_unraisablehook

# ========== CONFIGURAÇÕES ==========
@dataclass
class DownloadConfig:
    output_dir: str = "downloads"
    audio_format: str = "mp3"
    audio_quality: str = "192k"
    video_format: str = "bestvideo+bestaudio/best"
    max_retries: int = 3
    retry_delay: int = 5
    enable_playlist: bool = True
    max_playlist_items: int = 10
    whisper_model: str = "medium"  # medium = melhor p/ PT-BR (tiny/base têm qualidade ruim)
    # tolerância (%) entre a duração baixada e a esperada antes de considerar truncado
    duration_tolerance_pct: float = 2.0


# ========== CHECAGEM DE DEPENDÊNCIAS EXTERNAS ==========
def check_dependencies() -> bool:
    """Verifica ffmpeg/ffprobe e avisa se o yt-dlp (lib) estiver desatualizado."""
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            print(f"❌ '{tool}' não encontrado no PATH. Instale com: brew install ffmpeg")
            ok = False

    # Avisa se a biblioteca yt-dlp tiver mais de ~45 dias (formatos do YouTube mudam)
    try:
        ver = getattr(yt_dlp.version, "__version__", "0")
        ver_date = datetime.strptime(ver[:10], "%Y.%m.%d")
        idade = (datetime.now() - ver_date).days
        if idade > 45:
            print(f"⚠️ Biblioteca yt-dlp v{ver} tem {idade} dias — pode truncar downloads.")
            print("   Atualize com: venv/bin/pip install -U yt-dlp")
    except Exception:
        pass

    return ok


# ========== OPÇÕES ROBUSTAS DO YT-DLP (corrige downloads truncados) ==========
def build_ydl_opts(extra: Dict[str, Any]) -> Dict[str, Any]:
    """Base robusta de opções do yt-dlp; `extra` sobrescreve/complementa.

    Pontos-chave que evitam o MP3 truncado silencioso:
      - ignoreerrors=False  -> erro de download levanta exceção (não gera arquivo parcial)
      - abort_on_unavailable_fragment=True -> aborta se faltar fragmento
      - player_client não é forçado: 'web'/'ios' passaram a exigir PO Token e só
        retornam thumbnails ("Requested format is not available"). Deixamos o yt-dlp
        escolher os clients padrão, que se adaptam às mudanças do YouTube.
    """
    base = {
        'quiet': False,
        'no_warnings': True,
        'logger': YTDlpLogger(),
        'ignoreerrors': False,
        'abort_on_unavailable_fragment': True,
        'retries': 20,
        'fragment_retries': 20,
        'file_access_retries': 10,
        'concurrent_fragment_downloads': 5,
        'socket_timeout': 30,
        'continuedl': True,
    }
    base.update(extra)
    return base


def get_media_duration(path: str) -> Optional[float]:
    """Duração em segundos de qualquer mídia (áudio ou vídeo) via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def verify_integrity(path: str, expected_duration: float, tolerance_pct: float = 2.0) -> bool:
    """Confere se o arquivo baixado tem a duração esperada (detecta truncamento).

    Retorna True se OK; imprime aviso e retorna False se faltar conteúdo.
    """
    if not expected_duration or expected_duration <= 0:
        return True  # sem referência confiável, não bloqueia

    actual = get_media_duration(path)
    if actual is None:
        print("⚠️ Não foi possível medir a duração do arquivo para validação.")
        return True

    diff_pct = abs(actual - expected_duration) / expected_duration * 100
    if diff_pct > tolerance_pct:
        def fmt(s):
            return f"{int(s // 60)}min{int(s % 60):02d}s"
        print(f"❌ DOWNLOAD INCOMPLETO: arquivo tem {fmt(actual)}, "
              f"esperado {fmt(expected_duration)} (faltam {diff_pct:.0f}%).")
        return False
    return True

class ConfigManager:
    def __init__(self, config_file: str = "download_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> DownloadConfig:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Filtra apenas chaves conhecidas — assim chaves antigas/extras
                # (ex.: "create_subdirs") não descartam toda a config salva
                valid_keys = {f.name for f in fields(DownloadConfig)}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                ignored = set(data) - valid_keys
                if ignored:
                    print(f"⚠️ Ignorando chaves desconhecidas na config: {', '.join(ignored)}")
                return DownloadConfig(**filtered)
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


def dedupe_stem(directory: Path, stem: str) -> str:
    """Evita sobrescrever downloads anteriores: se já existe algum arquivo
    <stem>.* na pasta, sufixa -2, -3, ... até o nome ficar único."""
    candidate = stem
    n = 2
    while any(directory.glob(f"{candidate}.*")):
        candidate = f"{stem}-{n}"
        n += 1
    return candidate

# ========== PROGRESS HOOK MELHORADO ==========
class ProgressManager:
    def __init__(self):
        self.progress_bar = None
        self.start_time = None
        self.last_update = 0
    
    def hook(self, d: Dict[str, Any]):
        """Hook melhorado para progresso de download"""
        current_time = time.time()
        
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            
            if total_bytes and not self.progress_bar:
                self.start_time = current_time
                self.progress_bar = tqdm(
                    total=total_bytes,
                    unit='B',
                    unit_scale=True,
                    desc='🔽 Baixando',
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                    ncols=80
                )
            
            if self.progress_bar and current_time - self.last_update > 0.1:  # Atualiza a cada 100ms
                self.progress_bar.n = downloaded
                if speed:
                    self.progress_bar.set_postfix({'Speed': f"{speed/1024/1024:.1f}MB/s"})
                self.progress_bar.refresh()
                self.last_update = current_time
        
        elif d['status'] == 'finished':
            if self.progress_bar:
                self.progress_bar.n = self.progress_bar.total
                self.progress_bar.close()
                elapsed = current_time - self.start_time if self.start_time else 0
                print(f"\n✅ Download finalizado em {elapsed:.1f}s")
            self.progress_bar = None
            self.start_time = None

        elif d['status'] == 'error':
            # Fecha a barra para não corromper o terminal nas próximas impressões
            if self.progress_bar:
                self.progress_bar.close()
            self.progress_bar = None
            self.start_time = None

# ========== EXTRATOR DE ÁUDIO MELHORADO ==========
class AudioExtractor:
    def __init__(self, config: DownloadConfig):
        self.config = config

    def _codec_args(self) -> List[str]:
        """Argumentos de codec/bitrate do ffmpeg para o formato configurado."""
        if self.config.audio_format == "mp3":
            return ["-acodec", "libmp3lame", "-ab", self.config.audio_quality]
        # aac e m4a usam o encoder AAC nativo do ffmpeg
        return ["-acodec", "aac", "-b:a", self.config.audio_quality]

    def split_audio(self, audio_path: str, output_dir: str, segment_minutes: int = 29) -> List[str]:
        """Divide o áudio em segmentos de até N minutos"""
        segment_seconds = segment_minutes * 60
        base_name = Path(audio_path).stem
        ext = self.config.audio_format
        output_pattern = str(Path(output_dir) / f"{base_name}_parte%03d.{ext}")

        print(f"\n✂️ Dividindo áudio em partes de {segment_minutes} minutos...")

        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-c", "copy",
            output_pattern
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            parts = sorted(Path(output_dir).glob(f"{base_name}_parte*.{ext}"))
            return [str(p) for p in parts]
        else:
            print(f"❌ Erro ao dividir áudio: {result.stderr}")
            return []

    def extract_audio(self, video_path: str, output_dir: str) -> Optional[str]:
        """Extração de áudio com progresso melhorado"""
        base_name = Path(video_path).stem
        audio_path = Path(output_dir) / f"{base_name}.{self.config.audio_format}"
        
        print(f"\n🎧 Extraindo áudio: {audio_path.name}")
        
        # Obtém informações do vídeo
        duration = self._get_video_duration(video_path)
        
        if not duration:
            print("⚠️ Não foi possível obter a duração do vídeo")
            return self._extract_audio_simple(video_path, audio_path)
        
        # Barra de progresso com atualizações mais frequentes
        progress_bar = tqdm(
            total=100,
            desc=f"🎚️ Convertendo para {self.config.audio_format.upper()}",
            unit="%",
            ncols=80
        )
        
        try:
            # Comando ffmpeg (codec conforme o formato configurado)
            cmd = ["ffmpeg", "-y", "-i", video_path, "-vn",
                   *self._codec_args(), str(audio_path)]

            # Executa conversão com progresso em thread separada
            result = self._extract_with_progress(cmd, progress_bar, duration)
            
            if result and audio_path.exists():
                print(f"✅ Áudio extraído: {audio_path}")
                return str(audio_path)
            else:
                print("❌ Falha na conversão de áudio")
                return None
                
        except Exception as e:
            print(f"❌ Erro na extração de áudio: {e}")
            return None
        finally:
            if progress_bar:
                progress_bar.close()
    
    def _extract_audio_simple(self, video_path: str, audio_path: Path) -> Optional[str]:
        """Extração simples sem progresso"""
        try:
            cmd = ["ffmpeg", "-y", "-i", video_path, "-vn",
                   *self._codec_args(), str(audio_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and audio_path.exists():
                print(f"✅ Áudio extraído: {audio_path}")
                return str(audio_path)
            else:
                print(f"❌ Erro na conversão: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ Erro na extração: {e}")
            return None
    
    def _extract_with_progress(self, cmd: List[str], progress_bar: tqdm, duration: float) -> bool:
        """Extração com progresso em thread separada"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Thread para monitorar o progresso
        def monitor_progress():
            current_percent = 0
            while process.poll() is None:
                try:
                    # Lê uma linha do stderr (onde o ffmpeg envia o progresso)
                    line = process.stderr.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    
                    # Procura por informações de tempo
                    if "time=" in line:
                        time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
                        if time_match:
                            hours, minutes, seconds, centiseconds = map(int, time_match.groups())
                            current_time = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                            percent = int((current_time / duration) * 100)
                            
                            if percent > current_percent and percent <= 100:
                                progress_bar.update(percent - current_percent)
                                current_percent = percent
                                progress_bar.refresh()
                    
                    time.sleep(0.1)  # Pausa pequena para não sobrecarregar
                    
                except Exception:
                    time.sleep(0.1)
                    continue
            
            # Finaliza a barra de progresso
            if current_percent < 100:
                progress_bar.n = 100
                progress_bar.refresh()
        
        # Inicia a thread de monitoramento
        progress_thread = threading.Thread(target=monitor_progress, daemon=True)
        progress_thread.start()
        
        # Aguarda o processo terminar
        process.wait()
        progress_thread.join(timeout=5)  # Aguarda até 5 segundos
        
        return process.returncode == 0
    
    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """Obtém a duração do vídeo"""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
            )
            return float(result.stdout.strip())
        except:
            return None

# ========== TRANSCRITOR DE ÁUDIO ==========
class AudioTranscriber:
    WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]

    def __init__(self, model_name: str = "medium"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        if self.model is None:
            print(f"\n🧠 Carregando modelo Whisper '{self.model_name}'...")
            self.model = whisper.load_model(self.model_name)
            print(f"✅ Modelo carregado!")

    def transcribe(self, audio_path: str, language: str = "pt") -> Optional[str]:
        """Transcreve o áudio e salva um arquivo .txt com timestamps."""
        self._load_model()

        print(f"\n📝 Transcrevendo: {Path(audio_path).name}")
        print(f"   Idioma: {language} | Modelo: {self.model_name}")

        # Aviso de tempo para áudios longos em CPU (Whisper é lento sem GPU)
        dur = get_media_duration(audio_path)
        if dur and dur > 30 * 60:
            mins = int(dur // 60)
            print(f"   ⚠️ Áudio de ~{mins}min. Em CPU, o modelo '{self.model_name}' "
                  f"pode levar horas. Considere 'small' para ir mais rápido.")
        print(f"   Isso pode levar alguns minutos...")

        try:
            result = self.model.transcribe(
                audio_path,
                language=language,
                verbose=False,
            )
        except Exception as e:
            print(f"❌ Erro na transcrição: {e}")
            return None

        # Monta o texto com timestamps
        lines = []
        segments = result.get("segments", [])
        for seg in segments:
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            text = seg["text"].strip()
            lines.append(f"[{start} --> {end}]  {text}")

        transcript_text = "\n".join(lines)

        # Salva o arquivo
        output_path = Path(audio_path).with_suffix(".txt")
        output_path.write_text(transcript_text, encoding="utf-8")

        total_segments = len(segments)
        duration = self._format_time(segments[-1]["end"]) if segments else "0:00"
        print(f"✅ Transcrição salva: {output_path.name}")
        print(f"   {total_segments} segmentos | Duração total: {duration}")

        return str(output_path)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Converte segundos para formato HH:MM:SS ou MM:SS"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


# ========== DATACLASSES PARA ANÁLISE DE CORTES ==========
@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str

@dataclass
class SuggestedCut:
    start: float
    end: float
    start_formatted: str
    end_formatted: str
    title: str
    theme: str
    score: float
    reason: str
    segments: List[TranscriptionSegment] = field(default_factory=list)
    full_text: str = ""


# ========== ANALISADOR DE CORTES PARA PREGAÇÕES ==========
class SermonCutAnalyzer:
    # Palavras-chave para perguntas retóricas
    RHETORICAL_TRIGGERS = [
        "voce ja", "sera que", "por que", "como pode", "ja pensou",
        "ja parou", "o que acontece", "sabe o que", "quer saber",
        "nao e verdade", "nao e mesmo", "voce sabe", "voce entende",
        "me diz uma coisa", "qual e", "quem aqui", "quantos aqui",
    ]

    # Intensificadores emocionais
    EMOTIONAL_INTENSIFIERS = [
        "tremendo", "poderoso", "incrivel", "extraordinario", "glorioso",
        "maravilhoso", "sobrenatural", "aleluia", "gloria", "amem",
        "fortemente", "grandemente", "profundamente", "impressionante",
        "avivamento", "milagre", "transformacao", "liberdade", "vitoria",
    ]

    # Verbos de chamada à ação
    CALL_TO_ACTION = [
        "levante", "ore", "creia", "entregue", "venha", "aceite",
        "receba", "declare", "confesse", "abra seu coracao",
        "faca uma oracao", "repita comigo", "diga comigo",
        "eu te convido", "neste momento", "nesta noite", "agora mesmo",
        "quem quer", "levanta a mao", "fecha os olhos", "coloca a mao",
    ]

    # Palavras-chave de ensino bíblico
    TEACHING_KEYWORDS = [
        "graca", "salvacao", "fe", "pecado", "redencao", "evangelho",
        "espirito santo", "jesus cristo", "palavra de deus", "biblia",
        "alianca", "promessa", "mandamento", "reino de deus", "deus",
        "senhor", "cristo", "cruz", "ressurreicao", "batismo",
        "arrependimento", "santificacao", "justificacao", "misericordia",
    ]

    # Padrão regex para referências bíblicas
    SCRIPTURE_PATTERN = (
        r'(?:genesis|exodo|levitico|numeros|deuteronomio|josue|juizes|rute|'
        r'samuel|reis|cronicas|esdras|neemias|ester|jo|salmos?|proverbios|'
        r'eclesiastes|cantares|isaias|jeremias|lamentacoes|ezequiel|daniel|'
        r'oseias|joel|amos|obadias|jonas|miqueias|naum|habacuque|sofonias|'
        r'ageu|zacarias|malaquias|mateus|marcos|lucas|joao|atos|romanos|'
        r'corintios|galatas|efesios|filipenses|colossenses|tessalonicenses|'
        r'timoteo|tito|filemom|hebreus|tiago|pedro|judas|apocalipse)'
        r'\s*\d+[.:,]\s*\d+'
    )

    # Marcadores de narrativa/testemunho
    NARRATIVE_MARKERS = [
        "eu lembro", "uma vez", "certa vez", "aconteceu", "historia",
        "imagine", "quando eu era", "naquela epoca", "eu estava",
        "vou contar", "deixa eu contar", "um dia", "tempos atras",
    ]

    # Classificação de temas
    THEME_KEYWORDS = {
        "Ensino Biblico": ["biblia", "escritura", "versiculo", "capitulo", "testamento", "evangelho"],
        "Testemunho": ["eu lembro", "aconteceu comigo", "minha vida", "testemunho", "historia"],
        "Chamado ao Altar": ["aceite", "convido", "entregue", "venha", "altar", "decisao"],
        "Exortacao": ["cuidado", "atencao", "nao deixe", "nao desista", "persevere", "lute"],
        "Louvor e Adoracao": ["louve", "adore", "glorifique", "cante", "aleluia", "gloria"],
        "Oracao": ["ore", "oracao", "joelhos", "clame", "interceda", "suplica"],
        "Declaracao Profetica": ["declare", "profetizo", "eu decreto", "vai acontecer", "deus vai"],
    }

    # Pesos para cada categoria de pontuação
    SCORING_WEIGHTS = {
        "rhetorical_questions": 1.5,
        "emotional_intensity": 1.2,
        "call_to_action": 2.0,
        "teaching_content": 1.8,
        "storytelling": 1.3,
        "repetition": 1.0,
        "scripture_reference": 1.5,
    }

    def __init__(self, min_clip_seconds: int = 30, max_clip_seconds: int = 120,
                 score_threshold: float = 3.0, max_suggestions: int = 15):
        self.min_clip_seconds = min_clip_seconds
        self.max_clip_seconds = max_clip_seconds
        self.score_threshold = score_threshold
        self.max_suggestions = max_suggestions

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos e converte para minúsculas para comparação."""
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        return text.lower().strip()

    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Converte string de tempo (M:SS ou H:MM:SS) para segundos."""
        parts = time_str.strip().split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0.0

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def parse_transcription(self, transcript_path: str) -> List[TranscriptionSegment]:
        """Lê o arquivo de transcrição e retorna lista de segmentos."""
        segments = []
        pattern = re.compile(r'\[(.+?)\s*-->\s*(.+?)\]\s+(.+)')

        text = Path(transcript_path).read_text(encoding='utf-8')
        for line in text.splitlines():
            match = pattern.match(line.strip())
            if match:
                start = self._parse_time(match.group(1))
                end = self._parse_time(match.group(2))
                seg_text = match.group(3).strip()
                segments.append(TranscriptionSegment(start=start, end=end, text=seg_text))

        return segments

    # ---------- Métodos de pontuação ----------

    def _score_rhetorical_questions(self, text: str) -> float:
        norm = self._normalize(text)
        if '?' not in text:
            return 0.0
        score = 0.3  # pontuação base por ter "?"
        for trigger in self.RHETORICAL_TRIGGERS:
            if trigger in norm:
                score += 0.35
        return min(score, 1.0)

    def _score_emotional_intensity(self, text: str) -> float:
        norm = self._normalize(text)
        count = sum(1 for word in self.EMOTIONAL_INTENSIFIERS if word in norm)
        exclamations = text.count('!')
        score = count * 0.25 + exclamations * 0.15
        return min(score, 1.0)

    def _score_call_to_action(self, text: str) -> float:
        norm = self._normalize(text)
        count = sum(1 for phrase in self.CALL_TO_ACTION if phrase in norm)
        return min(count * 0.4, 1.0)

    def _score_teaching_content(self, text: str) -> float:
        norm = self._normalize(text)
        count = sum(1 for word in self.TEACHING_KEYWORDS if word in norm)
        return min(count * 0.2, 1.0)

    def _score_scripture_reference(self, text: str) -> float:
        norm = self._normalize(text)
        matches = re.findall(self.SCRIPTURE_PATTERN, norm)
        return min(len(matches) * 0.5, 1.0)

    def _score_storytelling(self, text: str) -> float:
        norm = self._normalize(text)
        count = sum(1 for marker in self.NARRATIVE_MARKERS if marker in norm)
        return min(count * 0.4, 1.0)

    def _score_repetition(self, segments: List[TranscriptionSegment]) -> float:
        """Detecta frases repetidas entre segmentos consecutivos (ênfase do pregador)."""
        if len(segments) < 2:
            return 0.0

        repeated = 0
        for i in range(len(segments) - 1):
            words_a = set(self._normalize(segments[i].text).split())
            words_b = set(self._normalize(segments[i + 1].text).split())
            if len(words_a) < 3 or len(words_b) < 3:
                continue
            overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
            if overlap > 0.4:
                repeated += 1

        return min(repeated * 0.3, 1.0)

    def _score_segment_group(self, segments: List[TranscriptionSegment]) -> Tuple[float, str]:
        """Calcula pontuação total de um grupo de segmentos e retorna o motivo principal."""
        full_text = ' '.join(seg.text for seg in segments)

        scores = {
            "rhetorical_questions": self._score_rhetorical_questions(full_text),
            "emotional_intensity": self._score_emotional_intensity(full_text),
            "call_to_action": self._score_call_to_action(full_text),
            "teaching_content": self._score_teaching_content(full_text),
            "scripture_reference": self._score_scripture_reference(full_text),
            "storytelling": self._score_storytelling(full_text),
            "repetition": self._score_repetition(segments),
        }

        # Calcula pontuação ponderada
        weighted_sum = sum(scores[k] * self.SCORING_WEIGHTS[k] for k in scores)
        max_possible = sum(self.SCORING_WEIGHTS.values())
        final_score = (weighted_sum / max_possible) * 10.0

        # Identifica o motivo principal
        best_category = max(scores, key=lambda k: scores[k] * self.SCORING_WEIGHTS[k])
        reasons_map = {
            "rhetorical_questions": "Perguntas retorica que provocam reflexao",
            "emotional_intensity": "Alta intensidade emocional",
            "call_to_action": "Chamado a acao / convite",
            "teaching_content": "Ensino biblico relevante",
            "scripture_reference": "Referencia biblica direta",
            "storytelling": "Narrativa / testemunho envolvente",
            "repetition": "Enfase por repeticao",
        }
        reason = reasons_map.get(best_category, "Conteudo relevante")

        return round(final_score, 1), reason

    # ---------- Agrupamento de segmentos ----------

    def _group_segments_into_clips(self, segments: List[TranscriptionSegment]) -> List[List[TranscriptionSegment]]:
        """Agrupa segmentos em potenciais clipes usando janela deslizante."""
        if not segments:
            return []

        groups = []
        # Janela deslizante: testa grupos de 3 a 8 segmentos
        for window_size in range(3, 9):
            for i in range(0, len(segments) - window_size + 1, 2):
                group = segments[i:i + window_size]
                duration = group[-1].end - group[0].start

                if duration < self.min_clip_seconds or duration > self.max_clip_seconds:
                    continue

                groups.append(group)

        # Remove grupos muito sobrepostos (mantém o de maior pontuação)
        if not groups:
            return []

        scored_groups = []
        for group in groups:
            score, reason = self._score_segment_group(group)
            scored_groups.append((score, reason, group))

        scored_groups.sort(key=lambda x: x[0], reverse=True)

        # Remove sobreposições: se dois grupos se sobrepõem >50%, mantém o melhor
        final_groups = []
        used_ranges = []

        for score, reason, group in scored_groups:
            start = group[0].start
            end = group[-1].end

            overlaps = False
            for used_start, used_end in used_ranges:
                overlap_start = max(start, used_start)
                overlap_end = min(end, used_end)
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    min_duration = min(end - start, used_end - used_start)
                    if min_duration > 0 and (overlap_duration / min_duration) > 0.5:
                        overlaps = True
                        break

            if not overlaps:
                final_groups.append((score, reason, group))
                used_ranges.append((start, end))

        return [(score, reason, group) for score, reason, group in final_groups]

    # ---------- Geração de título e tema ----------

    def _generate_title(self, segments: List[TranscriptionSegment]) -> str:
        """Gera um título curto para o corte."""
        full_text = ' '.join(seg.text for seg in segments)
        norm = self._normalize(full_text)

        # Tenta encontrar referência bíblica para usar no título
        ref_match = re.search(self.SCRIPTURE_PATTERN, norm)
        if ref_match:
            ref = ref_match.group(0).title()
            # Pega palavras ao redor da referência
            best_seg = max(segments, key=lambda s: len(s.text))
            words = best_seg.text.split()[:8]
            return ' '.join(words) + f" - {ref}"

        # Pega o segmento mais significativo (mais longo com conteúdo)
        best_seg = max(segments, key=lambda s: len(s.text))
        words = best_seg.text.split()
        if len(words) > 10:
            return ' '.join(words[:10]) + "..."
        return best_seg.text

    def _classify_theme(self, text: str) -> str:
        """Classifica o tema do trecho."""
        norm = self._normalize(text)
        scores = {}
        for theme, keywords in self.THEME_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in norm)
            scores[theme] = count

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return "Pregacao Geral"
        return best

    # ---------- Método principal de análise ----------

    def analyze(self, transcript_path: str) -> List[SuggestedCut]:
        """Analisa a transcrição e retorna sugestões de cortes."""
        print(f"\n🔍 Analisando transcrição para cortes...")

        segments = self.parse_transcription(transcript_path)
        if not segments:
            print("❌ Nenhum segmento encontrado na transcrição")
            return []

        total_duration = segments[-1].end if segments else 0
        print(f"   {len(segments)} segmentos | Duração: {self._format_time(total_duration)}")

        # Agrupa e pontua
        scored_groups = self._group_segments_into_clips(segments)

        # Filtra por threshold e limita
        cuts = []
        for score, reason, group in scored_groups:
            if score < self.score_threshold:
                continue

            full_text = ' '.join(seg.text for seg in group)
            title = self._generate_title(group)
            theme = self._classify_theme(full_text)
            duration = group[-1].end - group[0].start

            cut = SuggestedCut(
                start=group[0].start,
                end=group[-1].end,
                start_formatted=self._format_time(group[0].start),
                end_formatted=self._format_time(group[-1].end),
                title=title,
                theme=theme,
                score=score,
                reason=reason,
                segments=group,
                full_text=full_text,
            )
            cuts.append(cut)

            if len(cuts) >= self.max_suggestions:
                break

        # Ordena por tempo de início para facilitar a edição
        cuts.sort(key=lambda c: c.start)

        print(f"   ✅ {len(cuts)} cortes sugeridos encontrados!")
        return cuts

    # ---------- Métodos de saída ----------

    def save_report_json(self, cuts: List[SuggestedCut], output_path: str):
        """Salva relatório em JSON."""
        data = {
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_cuts": len(cuts),
            "suggested_cuts": [
                {
                    "rank": i + 1,
                    "title": cut.title,
                    "theme": cut.theme,
                    "start": cut.start_formatted,
                    "end": cut.end_formatted,
                    "start_seconds": cut.start,
                    "end_seconds": cut.end,
                    "duration_seconds": round(cut.end - cut.start),
                    "score": cut.score,
                    "reason": cut.reason,
                    "text": cut.full_text,
                }
                for i, cut in enumerate(sorted(cuts, key=lambda c: c.score, reverse=True))
            ],
        }
        Path(output_path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'
        )

    def save_report_txt(self, cuts: List[SuggestedCut], output_path: str):
        """Salva relatório legível em TXT."""
        lines = []
        lines.append("=" * 60)
        lines.append("ANALISE DE CORTES PARA PREGACAO")
        lines.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total de cortes sugeridos: {len(cuts)}")
        lines.append("=" * 60)

        # Ordena por score para o relatório
        ranked = sorted(cuts, key=lambda c: c.score, reverse=True)

        for i, cut in enumerate(ranked, 1):
            duration = cut.end - cut.start
            dur_min = int(duration // 60)
            dur_sec = int(duration % 60)

            lines.append("")
            lines.append(f"#{i} [SCORE: {cut.score}/10] - {cut.theme}")
            lines.append(f'   "{cut.title}"')
            lines.append(f"   Inicio: {cut.start_formatted} | Fim: {cut.end_formatted} | "
                         f"Duracao: {dur_min}min {dur_sec}s")
            lines.append(f"   Motivo: {cut.reason}")
            lines.append(f"   ---")
            # Mostra o texto com timestamps por segmento
            for seg in cut.segments:
                seg_start = self._format_time(seg.start)
                seg_end = self._format_time(seg.end)
                lines.append(f"   [{seg_start}] {seg.text}")
            lines.append(f"   ---")

        lines.append("")
        lines.append("=" * 60)
        lines.append("FIM DA ANALISE")
        lines.append("=" * 60)

        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')

    def print_report(self, cuts: List[SuggestedCut]):
        """Imprime resumo no console."""
        ranked = sorted(cuts, key=lambda c: c.score, reverse=True)

        print(f"\n{'=' * 60}")
        print(f"🎬 SUGESTÕES DE CORTES ({len(cuts)} encontrados)")
        print(f"{'=' * 60}")

        for i, cut in enumerate(ranked, 1):
            duration = cut.end - cut.start
            dur_min = int(duration // 60)
            dur_sec = int(duration % 60)

            score_bar = "█" * int(cut.score) + "░" * (10 - int(cut.score))
            print(f"\n  #{i} [{score_bar}] {cut.score}/10")
            print(f"     📌 {cut.theme}")
            print(f"     🎯 {cut.title[:60]}")
            print(f"     ⏱️  {cut.start_formatted} --> {cut.end_formatted} ({dur_min}m{dur_sec}s)")
            print(f"     💡 {cut.reason}")

        print(f"\n{'=' * 60}")


# ========== DOWNLOADER PRINCIPAL ==========
class YouTubeDownloader:
    def __init__(self, config: DownloadConfig):
        self.config = config
        self.progress_manager = ProgressManager()
        self.audio_extractor = AudioExtractor(config)
        self.transcriber = AudioTranscriber(config.whisper_model)
        self.cut_analyzer = SermonCutAnalyzer()
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
        safe_title = dedupe_stem(Path(self.config.output_dir), safe_title)

        video_filename = Path(self.config.output_dir) / f"{safe_title}.mp4"

        # Configurações do yt-dlp (base robusta + específicas deste fluxo)
        ydl_opts = build_ydl_opts({
            'format': self.config.video_format,
            'outtmpl': str(video_filename),
            # URL de vídeo com &list= NÃO deve puxar a playlist inteira aqui
        # (sobrescreveria o mesmo arquivo N vezes). Playlist tem fluxo próprio.
        'noplaylist': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [self.progress_manager.hook],
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # O merge pode gerar extensão diferente; localiza o arquivo real
        if not video_filename.exists():
            candidates = list(Path(self.config.output_dir).glob(f"{safe_title}.*"))
            candidates = [c for c in candidates
                          if c.suffix.lower() in ('.mp4', '.mkv', '.webm')]
            if candidates:
                video_filename = candidates[0]

        if video_filename.exists():
            # Valida integridade antes de prosseguir
            if not verify_integrity(str(video_filename), duration,
                                    self.config.duration_tolerance_pct):
                raise RuntimeError("Vídeo baixado está incompleto (truncado).")

            print(f"✅ Vídeo baixado: {video_filename}")

            # Extrai áudio
            audio_path = self.audio_extractor.extract_audio(str(video_filename), self.config.output_dir)
            if audio_path:
                return audio_path
            else:
                print("⚠️ Download do vídeo OK, mas falha na extração de áudio")
                return str(video_filename)
        else:
            print("❌ Vídeo não foi baixado")
            return None
    
    def download_audio_only(self, url: str) -> Optional[str]:
        """Baixa apenas o áudio (sem vídeo), convertido para o formato configurado."""
        info = self._extract_video_info(url)
        if not info:
            return None

        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)

        print(f"📺 Título: {title}")
        if duration:
            print(f"⏱️ Duração: {duration//60}min {duration%60}s")

        safe_title = sanitize_filename(title)
        safe_title = dedupe_stem(Path(self.config.output_dir), safe_title)
        out_template = str(Path(self.config.output_dir) / f"{safe_title}.%(ext)s")
        final_path = Path(self.config.output_dir) / f"{safe_title}.{self.config.audio_format}"

        ydl_opts = build_ydl_opts({
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            # URL de vídeo com &list= NÃO deve puxar a playlist inteira aqui
        # (sobrescreveria o mesmo arquivo N vezes). Playlist tem fluxo próprio.
        'noplaylist': True,
            'progress_hooks': [self.progress_manager.hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.config.audio_format,
                'preferredquality': self.config.audio_quality.rstrip('k'),
            }],
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if final_path.exists():
            if not verify_integrity(str(final_path), duration,
                                    self.config.duration_tolerance_pct):
                print("⚠️ O áudio parece incompleto. Tente baixar novamente.")
                return None
            print(f"✅ Áudio baixado: {final_path}")
            return str(final_path)
        print("❌ Falha ao baixar áudio")
        return None

    def _extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extrai informações do vídeo"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"❌ Erro ao extrair informações: {e}")
            return None
    
    def download_complete(self, url: str) -> Optional[str]:
        """Download completo: pasta própria + vídeo + thumbnail + áudio dividido em 29min"""
        info = self._extract_video_info(url)
        if not info:
            return None

        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)

        print(f"📺 Título: {title}")
        if duration:
            print(f"⏱️ Duração: {duration//60}min {duration%60}s")

        # Cria pasta com nome do vídeo
        safe_title = sanitize_filename(title)
        video_dir = Path(self.config.output_dir) / safe_title
        video_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Pasta criada: {video_dir}")

        video_filename = video_dir / f"{safe_title}.mp4"

        ydl_opts = build_ydl_opts({
            'format': self.config.video_format,
            'outtmpl': str(video_filename),
            'noplaylist': True,
            'writethumbnail': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [self.progress_manager.hook],
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not video_filename.exists():
            candidates = [c for c in video_dir.glob(f"{safe_title}.*")
                          if c.suffix.lower() in ('.mp4', '.mkv', '.webm')]
            if candidates:
                video_filename = candidates[0]

        if not video_filename.exists():
            print("❌ Vídeo não foi baixado")
            return None

        if not verify_integrity(str(video_filename), duration,
                                self.config.duration_tolerance_pct):
            print("❌ Vídeo incompleto — abortando para não gerar áudio/transcrição truncados.")
            return None

        print(f"✅ Vídeo baixado: {video_filename.name}")

        # Extrai áudio completo
        audio_path = self.audio_extractor.extract_audio(str(video_filename), str(video_dir))
        if not audio_path:
            print("⚠️ Falha na extração de áudio")
            return str(video_dir)

        # Transcrição do áudio (antes de dividir, pois o original pode ser removido)
        transcript_path = self.transcriber.transcribe(audio_path)
        if transcript_path:
            print(f"📝 Transcrição salva: {Path(transcript_path).name}")

            # Análise de cortes
            cuts = self.cut_analyzer.analyze(transcript_path)
            if cuts:
                cuts_json = str(Path(transcript_path).with_name(
                    Path(transcript_path).stem + "_cortes.json"))
                cuts_txt = str(Path(transcript_path).with_name(
                    Path(transcript_path).stem + "_cortes.txt"))
                self.cut_analyzer.save_report_json(cuts, cuts_json)
                self.cut_analyzer.save_report_txt(cuts, cuts_txt)
                self.cut_analyzer.print_report(cuts)
                print(f"📊 Relatório de cortes salvo: {Path(cuts_txt).name}")

        # Divide em partes de 29 minutos
        parts = self.audio_extractor.split_audio(audio_path, str(video_dir))

        if parts:
            if len(parts) == 1:
                # Só uma parte: renomeia para o nome original
                final_path = Path(audio_path)
                Path(parts[0]).rename(final_path)
                print(f"✅ Áudio salvo (sem divisão necessária): {final_path.name}")
            else:
                os.remove(audio_path)
                print(f"✅ Áudio dividido em {len(parts)} parte(s):")
                for p in parts:
                    print(f"  🎵 {Path(p).name}")
        else:
            print("⚠️ Falha ao dividir áudio, mantendo arquivo original")

        # Lista thumbnail gerada
        thumbs = list(video_dir.glob(f"{safe_title}.*"))
        thumbs = [t for t in thumbs if t.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')]
        if thumbs:
            print(f"🖼️ Thumbnail salva: {thumbs[0].name}")

        print(f"\n📂 Tudo salvo em: {video_dir}")
        return str(video_dir)

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
                
                print(f"\n📥 Baixando vídeo {i}/{len(entries)}")
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
        """Menu principal melhorado"""
        while True:
            print("\n" + "="*60)
            print("🎵 DOWNLOADER DE ÁUDIO DO YOUTUBE - VERSÃO MELHORADA")
            print("="*60)
            print("1. 📥 Baixar vídeo único")
            print("2. 📦 Baixar completo (pasta + áudio + transcrição + cortes)")
            print("3. 📋 Baixar playlist")
            print("4. 🎧 Converter vídeo existente")
            print("5. 📝 Transcrever áudio existente")
            print("6. 🎬 Analisar transcrição para cortes")
            print("7. ⚙️  Configurações")
            print("8. 📁 Abrir pasta de downloads")
            print("9. 🎵 Baixar somente áudio")
            print("0. ❌ Sair")
            print("-"*60)

            choice = input("Escolha uma opção (0-9): ").strip()

            if choice == "1":
                self.download_single_video()
            elif choice == "2":
                self.download_complete_video()
            elif choice == "3":
                self.download_playlist()
            elif choice == "4":
                self.convert_existing_video()
            elif choice == "5":
                self.transcribe_existing_audio()
            elif choice == "6":
                self.analyze_for_cuts()
            elif choice == "7":
                self.show_settings()
            elif choice == "8":
                self.open_downloads_folder()
            elif choice == "9":
                self.download_audio_only()
            elif choice == "0":
                print("👋 Até logo!")
                break
            else:
                print("❌ Opção inválida!")

    def download_audio_only(self):
        """Baixa apenas o áudio do vídeo."""
        url = self._get_youtube_url()
        if url:
            print(f"\n🚀 Baixando somente áudio...")
            result = self.downloader.download_audio_only(url)
            if result:
                print(f"\n🎉 Áudio salvo: {result}")
            else:
                print("❌ Falha no download")
    
    def download_single_video(self):
        """Download de vídeo único"""
        url = self._get_youtube_url()
        if url:
            print(f"\n🚀 Iniciando processo completo...")
            result = self.downloader.download_video(url)
            if result:
                print(f"\n🎉 Download e conversão concluídos!")
                print(f"📁 Arquivo final: {result}")
            else:
                print("❌ Falha no processo")
    
    def download_complete_video(self):
        """Download completo: pasta + vídeo + thumbnail + áudio dividido"""
        url = self._get_youtube_url()
        if url:
            print(f"\n🚀 Iniciando download completo...")
            result = self.downloader.download_complete(url)
            if result:
                print(f"\n🎉 Concluído! Arquivos em: {result}")
            else:
                print("❌ Falha no processo")

    def download_playlist(self):
        """Download de playlist"""
        url = self._get_youtube_url()
        if url:
            results = self.downloader.download_playlist(url)
            if results:
                print(f"\n🎉 Playlist processada: {len(results)} arquivos")
                for result in results:
                    print(f"  📁 {result}")
            else:
                print("❌ Falha no download da playlist")
    
    def analyze_for_cuts(self):
        """Analisa uma transcrição existente para sugerir cortes."""
        directory = Path(self.config_manager.config.output_dir)
        if not directory.exists():
            print(f"❌ Pasta '{directory}' não encontrada")
            return

        # Busca arquivos .txt de transcrição (exclui os _cortes.txt)
        txt_files = [f for f in directory.rglob("*.txt")
                     if not f.name.endswith("_cortes.txt")]

        if not txt_files:
            print(f"❌ Nenhuma transcrição encontrada em '{directory}'")
            print("   Primeiro transcreva um áudio (opção 5) ou baixe completo (opção 2)")
            return

        print(f"\n📝 Transcrições disponíveis:")
        for i, tf in enumerate(txt_files, 1):
            rel = tf.relative_to(directory)
            size_kb = tf.stat().st_size / 1024
            print(f"{i}. {rel} ({size_kb:.1f} KB)")

        while True:
            try:
                choice = input(f"\nEscolha a transcrição (1-{len(txt_files)}) ou '0' para cancelar: ").strip()
                if choice == "0":
                    return

                choice_num = int(choice)
                if 1 <= choice_num <= len(txt_files):
                    selected = txt_files[choice_num - 1]

                    # Configurações opcionais
                    print(f"\n⚙️  Configurações do analisador (Enter para padrão):")
                    min_dur = input(f"   Duração mínima do corte em segundos (padrão: 30): ").strip()
                    max_dur = input(f"   Duração máxima do corte em segundos (padrão: 120): ").strip()
                    max_cuts = input(f"   Número máximo de sugestões (padrão: 15): ").strip()

                    analyzer = SermonCutAnalyzer(
                        min_clip_seconds=int(min_dur) if min_dur else 30,
                        max_clip_seconds=int(max_dur) if max_dur else 120,
                        max_suggestions=int(max_cuts) if max_cuts else 15,
                    )

                    cuts = analyzer.analyze(str(selected))
                    if cuts:
                        # Salva relatórios
                        base = selected.with_name(selected.stem + "_cortes")
                        analyzer.save_report_json(cuts, str(base.with_suffix(".json")))
                        analyzer.save_report_txt(cuts, str(base.with_suffix(".txt")))
                        analyzer.print_report(cuts)
                        print(f"\n📊 Relatórios salvos:")
                        print(f"   📄 {base.with_suffix('.txt').name}")
                        print(f"   📋 {base.with_suffix('.json').name}")
                    else:
                        print("⚠️ Nenhum corte relevante encontrado")
                    return
                else:
                    print("❌ Escolha inválida!")
            except ValueError:
                print("❌ Digite um número válido!")

    def transcribe_existing_audio(self):
        """Transcrição de áudio existente"""
        directory = Path(self.config_manager.config.output_dir)
        if not directory.exists():
            print(f"❌ Pasta '{directory}' não encontrada")
            return

        # Busca áudios recursivamente
        audio_extensions = ["*.mp3", "*.m4a", "*.aac", "*.wav", "*.ogg", "*.flac"]
        audio_files = []
        for ext in audio_extensions:
            audio_files.extend(directory.rglob(ext))

        if not audio_files:
            print(f"❌ Nenhum áudio encontrado em '{directory}'")
            return

        print(f"\n🎵 Áudios disponíveis:")
        for i, af in enumerate(audio_files, 1):
            size_mb = af.stat().st_size / (1024 * 1024)
            rel = af.relative_to(directory)
            print(f"{i}. {rel} ({size_mb:.1f} MB)")

        while True:
            try:
                choice = input(f"\nEscolha o áudio (1-{len(audio_files)}) ou '0' para cancelar: ").strip()
                if choice == "0":
                    return

                choice_num = int(choice)
                if 1 <= choice_num <= len(audio_files):
                    selected = audio_files[choice_num - 1]

                    # Pergunta o idioma
                    lang = input("Idioma do áudio (pt/en/es, padrão: pt): ").strip() or "pt"

                    # Pergunta o modelo
                    models = AudioTranscriber.WHISPER_MODELS
                    current = self.downloader.transcriber.model_name
                    print(f"\nModelos disponíveis: {', '.join(models)}")
                    print(f"  tiny   = mais rápido, menos preciso")
                    print(f"  base   = bom equilíbrio (padrão)")
                    print(f"  small  = melhor precisão")
                    print(f"  medium = alta precisão")
                    print(f"  large  = máxima precisão (lento)")
                    model = input(f"Modelo (atual: {current}): ").strip()
                    if model in models:
                        self.downloader.transcriber = AudioTranscriber(model)

                    result = self.downloader.transcriber.transcribe(str(selected), language=lang)
                    if result:
                        print(f"\n✅ Transcrição salva: {result}")
                    else:
                        print("❌ Falha na transcrição")
                    return
                else:
                    print("❌ Escolha inválida!")
            except ValueError:
                print("❌ Digite um número válido!")

    def convert_existing_video(self):
        """Conversão de vídeo existente"""
        directory = Path(self.config_manager.config.output_dir)
        if not directory.exists():
            print(f"❌ Pasta '{directory}' não encontrada")
            return
        
        # Busca por múltiplos formatos de vídeo
        video_extensions = ["*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm", "*.flv"]
        video_files = []
        for ext in video_extensions:
            video_files.extend(directory.glob(ext))
        
        if not video_files:
            print(f"❌ Nenhum vídeo encontrado em '{directory}'")
            return
        
        print(f"\n📂 Vídeos disponíveis em '{directory}':")
        for i, video_file in enumerate(video_files, 1):
            size_mb = video_file.stat().st_size / (1024 * 1024)
            print(f"{i}. {video_file.name} ({size_mb:.1f} MB)")
        
        while True:
            try:
                choice = input(f"\nEscolha o vídeo (1-{len(video_files)}) ou '0' para cancelar: ").strip()
                if choice == "0":
                    return
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(video_files):
                    selected_file = video_files[choice_num - 1]
                    result = self.downloader.audio_extractor.extract_audio(
                        str(selected_file), 
                        str(directory)
                    )
                    if result:
                        print(f"✅ Áudio extraído: {result}")
                    else:
                        print("❌ Falha na extração")
                    return
                else:
                    print("❌ Escolha inválida!")
            except ValueError:
                print("❌ Digite um número válido!")
    
    def show_settings(self):
        """Configurações do programa"""
        while True:
            print("\n" + "="*40)
            print("⚙️ CONFIGURAÇÕES")
            print("="*40)
            config = self.config_manager.config
            
            print(f"1. 📁 Pasta de saída: {config.output_dir}")
            print(f"2. 🎵 Formato de áudio: {config.audio_format}")
            print(f"3. 🎚️ Qualidade de áudio: {config.audio_quality}")
            print(f"4. 📹 Formato de vídeo: {config.video_format}")
            print(f"5. 🔄 Tentativas máximas: {config.max_retries}")
            print(f"6. 📋 Suporte a playlist: {'Sim' if config.enable_playlist else 'Não'}")
            print(f"7. 📊 Máximo de itens na playlist: {config.max_playlist_items}")
            print("8. 💾 Salvar configurações")
            print("9. ↩️ Voltar")
            
            choice = input("\nEscolha uma opção (1-9): ").strip()
            
            if choice == "1":
                new_dir = input(f"Nova pasta de saída (atual: {config.output_dir}): ").strip()
                if new_dir:
                    config.output_dir = new_dir
            elif choice == "2":
                new_format = input(f"Novo formato (atual: {config.audio_format}): ").strip()
                if new_format in ['mp3', 'aac', 'm4a']:
                    config.audio_format = new_format
            elif choice == "3":
                new_quality = input(f"Nova qualidade (atual: {config.audio_quality}): ").strip()
                if new_quality:
                    config.audio_quality = new_quality
            elif choice == "4":
                new_video_format = input(f"Novo formato de vídeo (atual: {config.video_format}): ").strip()
                if new_video_format:
                    config.video_format = new_video_format
            elif choice == "5":
                try:
                    new_retries = int(input(f"Novo número de tentativas (atual: {config.max_retries}): ").strip())
                    if new_retries > 0:
                        config.max_retries = new_retries
                except ValueError:
                    print("❌ Digite um número válido!")
            elif choice == "6":
                config.enable_playlist = not config.enable_playlist
            elif choice == "7":
                try:
                    new_max = int(input(f"Novo máximo (atual: {config.max_playlist_items}): ").strip())
                    if new_max > 0:
                        config.max_playlist_items = new_max
                except ValueError:
                    print("❌ Digite um número válido!")
            elif choice == "8":
                self.config_manager.save_config()
                print("✅ Configurações salvas!")
            elif choice == "9":
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
    """Função principal melhorada"""
    print("🎵 Iniciando Downloader de Áudio do YouTube (Versão Melhorada)...")
    
    # Configura logging
    setup_logging()

    # Verifica ferramentas externas antes de começar
    if not check_dependencies():
        print("\n⚠️ Dependências ausentes. Corrija os itens acima antes de continuar.")
        return

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
