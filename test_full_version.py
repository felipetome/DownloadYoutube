import os
import sys
import subprocess

# Adiciona o FFmpeg ao PATH temporariamente
ffmpeg_path = r"C:\Users\felipetome\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin"
os.environ['PATH'] = ffmpeg_path + os.pathsep + os.environ.get('PATH', '')

print("🔧 Testando versão completa com FFmpeg...")
print(f"📁 FFmpeg path: {ffmpeg_path}")

# Testa se o FFmpeg está funcionando
try:
    result = subprocess.run(['ffmpeg', '-version'], 
                          capture_output=True, text=True, check=True)
    print("✅ FFmpeg funcionando!")
    print("🚀 Iniciando versão completa...")
    
    # Importa e executa a versão completa
    import down
    down.main()
    
except subprocess.CalledProcessError as e:
    print(f"❌ Erro ao executar FFmpeg: {e}")
except ImportError as e:
    print(f"❌ Erro ao importar versão completa: {e}")
except Exception as e:
    print(f"❌ Erro inesperado: {e}")
