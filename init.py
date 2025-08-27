
from pydub import AudioSegment
import os
import sys
import numpy as np
from pyAudioAnalysis import audioSegmentation as aS
from pyAudioAnalysis import audioBasicIO
from pyAudioAnalysis import MidTermFeatures

# Lê o áudio para corte posterior
def read_audio(path):
    return AudioSegment.from_file(path)

# Detecta segmentos de fala usando pyAudioAnalysis (speech/music)
def detect_speech_segments_pyaudio(audio_path, frame_duration_sec=1.0, min_voice_duration=1200):
    # Classifica cada frame como fala (0) ou música (1)
    # O modelo svmSM já vem com o pyAudioAnalysis, mas pode ser baixado do repo oficial
    flags, class_names, acc, _ = aS.mid_term_file_classification(audio_path, "models/svm_rbf_sm", "svm_rbf_sm")
    flags = np.array(flags)
    speech_segments = []
    triggered = False
    start_time = 0
    voiced_duration = 0
    for i, flag in enumerate(flags):
        time = i * frame_duration_sec
        if flag == 0:  # 0 = fala
            if not triggered:
                start_time = time
                triggered = True
            voiced_duration += frame_duration_sec
        elif triggered:
            if voiced_duration >= min_voice_duration:
                speech_segments.append((start_time, time))
            triggered = False
            voiced_duration = 0
        # Barra de progresso
        percent = int((i + 1) / len(flags) * 100)
        sys.stdout.write(f"\rAnalisando áudio (pyAudioAnalysis): {percent}% concluído")
        sys.stdout.flush()
    print()
    # Final
    if triggered and voiced_duration >= min_voice_duration:
        speech_segments.append((start_time, len(flags) * frame_duration_sec))
    return speech_segments

# Corta o áudio baseado nos timestamps de fala
def cut_audio(audio, timestamps, output_path):
    if not timestamps:
        print("❌ Nenhum trecho de fala longa foi detectado!")
        return False
    # Pega o maior trecho de fala
    longest_segment = max(timestamps, key=lambda x: x[1] - x[0])
    start_time, end_time = longest_segment
    start_ms = int(start_time * 1000)
    end_ms = int(end_time * 1000)
    cut_audio = audio[start_ms:end_ms]
    cut_audio.export(output_path, format="mp3")
    duration_minutes = (end_time - start_time) / 60
    print(f"✅ Áudio cortado com sucesso!")
    print(f"📁 Arquivo salvo: {output_path}")
    print(f"⏱️  Duração do trecho: {duration_minutes:.2f} minutos")
    print(f"🕐 Início: {start_time/60:.2f} min | Final: {end_time/60:.2f} min")
    return True

def convert_to_wav(input_path, output_path="temp_for_analysis.wav"):
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    audio.export(output_path, format="wav")
    return output_path

def main(audio_path):
    if not os.path.exists(audio_path):
        print(f"❌ Arquivo não encontrado: {audio_path}")
        return
    print(f"🎵 Processando arquivo: {audio_path}")
    print("🔍 Detectando trechos de fala (pyAudioAnalysis)...")
    
    # Converte para WAV em formato ideal
    wav_path = convert_to_wav(audio_path)
    
    # Ajuste aqui: frame de 0.5 segundo e mínimo de 30 segundos para considerar fala contínua
    speech_times = detect_speech_segments_pyaudio(
        wav_path,
        frame_duration_sec=0.5,  # melhor resolução
        min_voice_duration=30    # mais sensível a pausas breves
    )

    if not speech_times:
        print("❌ Nenhum trecho de fala longa foi detectado!")
        return
    
    print(f"\n📌 Trechos detectados:")
    for i, (start, end) in enumerate(speech_times):
        duration = end - start
        print(f"• Trecho {i+1}: {start/60:.2f}min - {end/60:.2f}min (Duração: {duration/60:.2f} min)")
    
    audio = read_audio(audio_path)
    base_name = os.path.splitext(audio_path)[0]
    output_path = f"{base_name}_pregacao.mp3"
    print(f"\n✂️ Cortando o maior trecho identificado como fala...")
    success = cut_audio(audio, speech_times, output_path)
    if success:
        print(f"\n🎉 Concluído! Arquivo cortado: '{output_path}'")


if __name__ == '__main__':
    print("Se aparecer erro de dependência, rode: pip install scipy scikit-learn numpy pydub pyAudioAnalysis")
    main('downloaded_audio.mp3')  # Substitua pelo nome do arquivo baixado
