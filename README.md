# 🎵 Downloader de Áudio do YouTube - Versão Melhorada

Um downloader robusto e moderno para baixar vídeos do YouTube e extrair áudio em alta qualidade.

## ✨ **Novas Funcionalidades**

### 🔧 **Melhorias Técnicas**
- **Arquitetura Orientada a Objetos**: Código reestruturado com classes bem definidas
- **Sistema de Configuração**: Arquivo JSON para personalizar comportamento
- **Tratamento de Erros Robusto**: Retry automático e melhor gestão de falhas
- **Logging Avançado**: Sistema de logs com cores e arquivos organizados por data
- **Validação de Dependências**: Verifica automaticamente se ffmpeg está instalado

### 📱 **Interface Melhorada**
- **Menu Expandido**: 6 opções principais com submenus
- **Feedback Visual**: Emojis e cores para melhor experiência
- **Configurações Interativas**: Menu para personalizar o programa
- **Acesso Rápido**: Abrir pasta de downloads diretamente

### 🎯 **Funcionalidades Adicionais**
- **Suporte a Playlists**: Download automático de playlists inteiras
- **Múltiplos Formatos**: Suporte a MP3, AAC e M4A
- **Qualidade Configurável**: Ajuste de bitrate de áudio
- **Progresso Detalhado**: Barras de progresso com velocidade e tempo estimado
- **Retry Automático**: Tentativas múltiplas em caso de falha

## 🚀 **Instalação**

### **Pré-requisitos**
```bash
# Python 3.7+
python --version

# FFmpeg (obrigatório)
ffmpeg -version
```

### **Dependências Python**
```bash
pip install -r requirements.txt
```

## 📖 **Como Usar**

### **1. Executar o Programa**
```bash
python down.py
```

### **2. Menu Principal**
```
🎵 DOWNLOADER DE ÁUDIO DO YOUTUBE - VERSÃO MELHORADA
============================================================
1. 📥 Baixar vídeo único
2. 📋 Baixar playlist
3. 🎧 Converter vídeo existente
4. ⚙️  Configurações
5. 📁 Abrir pasta de downloads
6. ❌ Sair
```

### **3. Opções Disponíveis**

#### **📥 Baixar Vídeo Único**
- Cole a URL do YouTube
- Download automático + conversão para áudio
- Arquivo salvo na pasta `downloads/`

#### **📋 Baixar Playlist**
- Cole URL de playlist do YouTube
- Download sequencial de todos os vídeos
- Conversão automática para áudio
- Limite configurável de itens

#### **🎧 Converter Vídeo Existente**
- Lista vídeos .mp4 da pasta downloads
- Conversão para áudio com progresso
- Suporte a múltiplos formatos

#### **⚙️ Configurações**
- Pasta de saída personalizada
- Formato de áudio (MP3, AAC, M4A)
- Qualidade de áudio configurável
- Número de tentativas de retry
- Suporte a playlists
- Limite de itens por playlist

#### **📁 Abrir Pasta de Downloads**
- Acesso direto à pasta de downloads
- Compatível com Windows, macOS e Linux

## ⚙️ **Configurações**

### **Arquivo de Configuração**
```json
{
  "output_dir": "downloads",
  "audio_format": "mp3",
  "audio_quality": "192k",
  "video_format": "best",
  "max_retries": 3,
  "retry_delay": 5,
  "enable_playlist": true,
  "max_playlist_items": 10,
  "create_subdirs": true
}
```

### **Parâmetros Configuráveis**
- **output_dir**: Pasta onde salvar arquivos
- **audio_format**: Formato de saída (mp3, aac, m4a)
- **audio_quality**: Qualidade do áudio (ex: 128k, 192k, 320k)
- **video_format**: Qualidade do vídeo (best, worst, 720p, etc.)
- **max_retries**: Tentativas em caso de falha
- **retry_delay**: Pausa entre tentativas (segundos)
- **enable_playlist**: Habilita suporte a playlists
- **max_playlist_items**: Máximo de vídeos por playlist

## 📁 **Estrutura de Arquivos**

```
projeto/
├── down.py                 # Programa principal melhorado
├── download_config.json    # Configurações personalizáveis
├── requirements.txt        # Dependências Python
├── README.md              # Esta documentação
├── downloads/             # Pasta de arquivos baixados
│   ├── video1.mp4
│   ├── video1.mp3
│   └── ...
└── logs/                  # Logs organizados por data
    ├── download_20241201.log
    └── download_20241202.log
```

## 🔍 **Logs e Monitoramento**

### **Sistema de Logs**
- **Console**: Informações importantes com cores
- **Arquivo**: Logs detalhados organizados por data
- **Níveis**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### **Exemplo de Log**
```
INFO: 🚀 Programa iniciado
INFO: 📥 Iniciando download: https://youtube.com/watch?v=...
INFO: 📺 Título: Nome do Vídeo
INFO: ⏱️ Duração: 3min 45s
INFO: ✅ Download finalizado em 45.2s
INFO: 🎧 Extraindo áudio: video.mp3
INFO: ✅ Áudio extraído: downloads/video.mp3
```

## 🛠️ **Troubleshooting**

### **Problemas Comuns**

#### **FFmpeg não encontrado**
```bash
# Windows: Baixe de https://ffmpeg.org/download.html
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

#### **Erro de permissão**
```bash
# Verifique se a pasta downloads/ tem permissão de escrita
# Windows: Execute como administrador se necessário
```

#### **Download falha**
- Verifique a conexão com a internet
- Confirme se a URL do YouTube é válida
- Aumente o número de tentativas nas configurações

## 🚀 **Melhorias Implementadas**

### **Comparação com Versão Anterior**

| Aspecto | Versão Anterior | Versão Melhorada |
|---------|----------------|------------------|
| **Arquitetura** | Funções soltas | Classes organizadas |
| **Configuração** | Hardcoded | Arquivo JSON |
| **Playlists** | ❌ Não suportado | ✅ Suporte completo |
| **Retry** | ❌ Sem retry | ✅ Retry automático |
| **Logs** | Arquivo único | Sistema organizado |
| **Interface** | Menu básico | Menu expandido |
| **Formato Áudio** | Apenas MP3 | MP3, AAC, M4A |
| **Progresso** | Básico | Detalhado com velocidade |
| **Tratamento Erros** | Básico | Robusto e informativo |

## 🤝 **Contribuição**

Sugestões e melhorias são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 **Licença**

Este projeto é de código aberto e está disponível sob a licença MIT.

## 🙏 **Agradecimentos**

- **yt-dlp**: Biblioteca principal para download
- **FFmpeg**: Conversão de áudio/vídeo
- **tqdm**: Barras de progresso
- **Comunidade Python**: Suporte e feedback

---

**🎉 Versão 2.0 - Totalmente reescrita com foco em robustez, usabilidade e funcionalidades avançadas!** 