import torch
import torchaudio
from pydub import AudioSegment
import os
import glob
from pathlib import Path

# Baixa o modelo Silero VAD
# Essa versão é a mais recente
def get_silero_vad():
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                  model='silero_vad',
                                  force_reload=False)
    return model, utils

# Carrega e converte o áudio em WAV mono 16kHz
def convert_audio(input_path, output_path='temp.wav'):
    audio = AudioSegment.from_file(input_path).set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format='wav')
    return output_path

# Detecta os trechos com voz utilizando Silero VAD
def detect_speech_segments(audio_path, threshold=0.4, min_speech_duration_sec=30, join_silence_sec=8):
    model, utils = get_silero_vad()
    (get_speech_timestamps, _, read_audio, *_) = utils

    wav = read_audio(audio_path, sampling_rate=16000)
    speech_timestamps = get_speech_timestamps(wav, model, threshold=threshold)

    segments = []
    current_segment = []
    for ts in speech_timestamps:
        start, end = ts['start']/16000, ts['end']/16000
        if not current_segment:
            current_segment = [start, end]
        elif start - current_segment[1] <= join_silence_sec:  # <-- aumente aqui!
            current_segment[1] = end
        else:
            if (current_segment[1] - current_segment[0]) >= min_speech_duration_sec:
                segments.append(current_segment)
            current_segment = [start, end]

    if current_segment and (current_segment[1] - current_segment[0]) >= min_speech_duration_sec:
        segments.append(current_segment)

    return segments

# Corta o maior segmento detectado
def cut_largest_segment(input_path, segments, output_path):
    audio = AudioSegment.from_file(input_path)
    largest_segment = max(segments, key=lambda x: x[1] - x[0])
    start_ms = int(largest_segment[0] * 1000)
    end_ms = int(largest_segment[1] * 1000)
    audio_cut = audio[start_ms:end_ms]
    audio_cut.export(output_path, format='mp3')

    print(f"✅ Trecho salvo: {output_path}")
    print(f"⏱️ Duração: {(largest_segment[1] - largest_segment[0])/60:.2f} min")
    print(f"🕐 Início: {largest_segment[0]/60:.2f} min | Final: {largest_segment[1]/60:.2f} min")

# Lista todos os arquivos de áudio na pasta downloads
def list_audio_files():
    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        print("❌ Pasta 'downloads' não encontrada!")
        return []
    
    # Extensões de áudio suportadas
    audio_extensions = ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.flac', '*.ogg']
    audio_files = []
    
    for ext in audio_extensions:
        audio_files.extend(downloads_dir.glob(ext))
    
    # Ordena por nome
    audio_files.sort()
    return audio_files

# Mostra menu de seleção de arquivos
def show_file_selection():
    print("🎵 ANALISADOR DE VOZ - SILERO VAD")
    print("=" * 50)
    
    audio_files = list_audio_files()
    
    if not audio_files:
        print("❌ Nenhum arquivo de áudio encontrado na pasta 'downloads'")
        print("💡 Baixe alguns vídeos primeiro usando o downloader!")
        return None
    
    print(f"📁 Encontrados {len(audio_files)} arquivo(s) de áudio:")
    print("-" * 50)
    
    for i, file_path in enumerate(audio_files, 1):
        # Obtém informações do arquivo
        file_size = file_path.stat().st_size / (1024 * 1024)  # MB
        print(f"{i:2d}. 🎧 {file_path.name}")
        print(f"    📊 Tamanho: {file_size:.1f} MB")
        print(f"    📂 Caminho: {file_path}")
        print()
    
    # Interface de seleção
    while True:
        try:
            choice = input(f"🎯 Escolha um arquivo (1-{len(audio_files)}) ou 'q' para sair: ").strip()
            
            if choice.lower() == 'q':
                print("👋 Até logo!")
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(audio_files):
                selected_file = audio_files[choice_num - 1]
                print(f"✅ Arquivo selecionado: {selected_file.name}")
                return selected_file
            else:
                print(f"❌ Por favor, escolha um número entre 1 e {len(audio_files)}")
        except ValueError:
            print("❌ Por favor, digite um número válido")
        except KeyboardInterrupt:
            print("\n👋 Até logo!")
            return None

# Configurações personalizáveis
def get_analysis_settings():
    print("\n⚙️ CONFIGURAÇÕES DE ANÁLISE")
    print("-" * 30)
    
    # Threshold de detecção
    while True:
        try:
            threshold_input = input("🎙️ Sensibilidade da detecção (0.1-0.9, padrão: 0.35): ").strip()
            if not threshold_input:
                threshold = 0.35
                break
            threshold = float(threshold_input)
            if 0.1 <= threshold <= 0.9:
                break
            else:
                print("❌ Valor deve estar entre 0.1 e 0.9")
        except ValueError:
            print("❌ Digite um número válido")
    
    # Duração mínima
    while True:
        try:
            duration_input = input("⏱️ Duração mínima em segundos (padrão: 300 = 5 min): ").strip()
            if not duration_input:
                min_duration = 300
                break
            min_duration = int(duration_input)
            if min_duration > 0:
                break
            else:
                print("❌ Duração deve ser maior que 0")
        except ValueError:
            print("❌ Digite um número válido")
    
    # Pausas permitidas
    while True:
        try:
            silence_input = input("🔇 Pausas permitidas em segundos (padrão: 10): ").strip()
            if not silence_input:
                join_silence = 10
                break
            join_silence = int(silence_input)
            if join_silence >= 0:
                break
            else:
                print("❌ Pausas devem ser >= 0")
        except ValueError:
            print("❌ Digite um número válido")
    
    return threshold, min_duration, join_silence

def main():
    print("🎵 ANALISADOR DE VOZ - SILERO VAD")
    print("=" * 50)
    
    # Seleciona arquivo
    selected_file = show_file_selection()
    if not selected_file:
        return
    
    # Obtém configurações
    threshold, min_duration, join_silence = get_analysis_settings()
    
    print(f"\n🔍 Iniciando análise de: {selected_file.name}")
    print(f"⚙️ Configurações: Sensibilidade={threshold}, Duração mínima={min_duration}s, Pausas={join_silence}s")
    
    try:
        print("\n🎵 Convertendo áudio...")
        wav_audio = convert_audio(str(selected_file))

        print("🔍 Detectando voz com Silero VAD...")
        speech_segments = detect_speech_segments(
            wav_audio,
            threshold=threshold,
            min_speech_duration_sec=min_duration,
            join_silence_sec=join_silence
        )

        if not speech_segments:
            print("❌ Nenhum trecho de voz longa foi detectado.")
            print("💡 Tente ajustar as configurações (sensibilidade mais baixa ou duração menor)")
            return

        print(f"\n📌 Segmentos detectados (voz contínua ≥ {min_duration/60:.1f} min):")
        for i, seg in enumerate(speech_segments, 1):
            duration_min = (seg[1] - seg[0]) / 60
            print(f"• Segmento {i}: {seg[0]/60:.2f}min - {seg[1]/60:.2f}min (Duração: {duration_min:.2f} min)")

        # Cria nome do arquivo de saída
        output_name = selected_file.stem + "_pregacao.mp3"
        output_path = selected_file.parent / output_name
        
        print(f"\n✂️ Cortando maior segmento...")
        cut_largest_segment(str(selected_file), speech_segments, str(output_path))
        
        print(f"\n🎉 Análise concluída!")
        print(f"📁 Arquivo salvo em: {output_path}")
        
    except Exception as e:
        print(f"❌ Erro durante a análise: {str(e)}")
    finally:
        # Remove o arquivo temporário, se existir
        if 'wav_audio' in locals() and os.path.exists(wav_audio):
            os.remove(wav_audio)
            print(f"🗑️ Arquivo temporário removido: {wav_audio}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Programa interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")