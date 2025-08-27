import torch
import torchaudio
from pydub import AudioSegment
import os

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


def main(input_audio):
    print("🎵 Convertendo áudio...")
    wav_audio = convert_audio(input_audio)

    try:
        print("🔍 Detectando voz com Silero VAD...")
        speech_segments = detect_speech_segments(
    wav_audio,
    threshold=0.35,               # mais sensível
    min_speech_duration_sec=300,  # aceita trechos a partir de 5 min
    join_silence_sec=10           # junta pausas de até 10s
)


        if not speech_segments:
            print("❌ Nenhum trecho de voz longa foi detectado.")
            return

        print("📌 Segmentos detectados (voz contínua):")
        for i, seg in enumerate(speech_segments, 1):
            print(f"• Segmento {i}: {seg[0]/60:.2f}min - {seg[1]/60:.2f}min")

        output_audio = input_audio.replace(".mp3", "_pregacao.mp3")
        cut_largest_segment(input_audio, speech_segments, output_audio)
    finally:
        # Remove o arquivo temporário, se existir
        if os.path.exists(wav_audio):
            os.remove(wav_audio)
            print(f"🗑️ Arquivo temporário removido: {wav_audio}")
import sys
if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main("downloaded_audio.mp3")