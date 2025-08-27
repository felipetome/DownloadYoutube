# Detector de Pregação em Áudio

Este programa baixa automaticamente áudio do YouTube e detecta trechos de fala contínua, extraindo apenas a parte onde uma pessoa fala por mais de 20 minutos, removendo músicas e outros ruídos.

## Funcionalidades

- ✅ **Download automático** de áudio do YouTube
- ✅ Detecta trechos de fala contínua usando VAD (Voice Activity Detection)
- ✅ Filtra apenas trechos com mais de 20 minutos de fala
- ✅ Corta automaticamente o áudio, mantendo apenas a pregação
- ✅ Remove músicas e outros ruídos do início e fim
- ✅ Gera arquivo de saída com apenas o conteúdo relevante
- ✅ Interface interativa para escolher entre YouTube ou arquivo local

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. **Importante**: Para o `webrtcvad` funcionar no Windows, você pode precisar instalar o Visual C++ Build Tools.

3. **FFmpeg**: O `yt-dlp` precisa do FFmpeg para converter áudio. Instale:
   - **Windows**: Baixe de https://ffmpeg.org/download.html e adicione ao PATH
   - **Linux**: `sudo apt install ffmpeg`
   - **macOS**: `brew install ffmpeg`

## Como usar

Execute o programa:
```bash
python init.py
```

O programa mostrará um menu com 3 opções:

### 1. 📥 Baixar do YouTube e processar
- Digite a URL do vídeo do YouTube
- O programa baixa automaticamente o áudio
- Processa e extrai apenas a pregação
- Remove o arquivo temporário automaticamente

### 2. 🎵 Processar arquivo local
- Digite o caminho de um arquivo MP3 local
- Processa e extrai apenas a pregação

### 3. ❌ Sair
- Encerra o programa

## Exemplo de uso

```
🎵 === DETECTOR DE PREGAÇÃO EM ÁUDIO ===
Este programa baixa áudio do YouTube e extrai apenas a pregação!

==================================================
Escolha uma opção:
1. 📥 Baixar do YouTube e processar
2. 🎵 Processar arquivo local
3. ❌ Sair

Digite sua escolha (1-3): 1

🔗 Digite a URL do vídeo do YouTube: https://www.youtube.com/watch?v=exemplo

📥 Baixando áudio do YouTube...
🔗 URL: https://www.youtube.com/watch?v=exemplo
📺 Título: Exemplo de Pregação
⏱️  Duração: 45min 30s
✅ Download concluído: downloaded_audio.mp3

🎵 Processando arquivo: downloaded_audio.mp3
🔍 Detectando trechos de fala...

📌 Trechos com fala contínua (mais de 20 min):
• Trecho 1: 2.50min - 42.30min (Duração: 39.80 min)

✂️  Cortando o maior trecho de fala...
✅ Áudio cortado com sucesso!
📁 Arquivo salvo: downloaded_audio_pregação.mp3
⏱️  Duração do trecho: 39.80 minutos
🕐 Início: 2.50 min | Final: 42.30 min

🎉 Processo concluído! O arquivo 'downloaded_audio_pregação.mp3' contém apenas a pregação.
🗑️  Arquivo temporário removido: downloaded_audio.mp3
```

## URLs suportadas

O programa aceita vários formatos de URL do YouTube:
- `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- `https://youtu.be/dQw4w9WgXcQ`
- `https://www.youtube.com/embed/dQw4w9WgXcQ`

## Configurações

- **Duração mínima**: 20 minutos (1200 segundos) - pode ser ajustada na linha 67
- **Sensibilidade VAD**: 3 (máxima) - pode ser ajustada na linha 90
- **Qualidade do áudio**: 192kbps MP3
- **Formato de saída**: MP3

## Saída

O programa mostrará:
- Informações do vídeo (título, duração)
- Progresso do download
- Trechos detectados com fala contínua
- Duração de cada trecho
- Confirmação do corte realizado
- Nome do arquivo de saída

## Resolução de problemas

- **"Nenhum trecho detectado"**: Tente reduzir a sensibilidade do VAD ou verificar se o arquivo tem fala contínua
- **Erro de importação**: Certifique-se de ter instalado todas as dependências
- **Erro no download**: Verifique se a URL é válida e se o vídeo está disponível
- **Erro FFmpeg**: Instale o FFmpeg e certifique-se de que está no PATH
- **Qualidade ruim**: O VAD funciona melhor com áudio de boa qualidade e sem muito ruído de fundo 