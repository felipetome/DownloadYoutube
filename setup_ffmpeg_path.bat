@echo off
echo 🔧 Configurando PATH do FFmpeg...
echo.

REM Caminho do FFmpeg
set "FFMPEG_PATH=C:\Users\felipetome\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin"

REM Verifica se o caminho existe
if not exist "%FFMPEG_PATH%" (
    echo ❌ Caminho do FFmpeg não encontrado: %FFMPEG_PATH%
    echo.
    echo 📋 Por favor, verifique se o FFmpeg foi instalado corretamente.
    pause
    exit /b 1
)

echo ✅ Caminho do FFmpeg encontrado: %FFMPEG_PATH%
echo.

REM Adiciona ao PATH do usuário
echo 🔄 Adicionando ao PATH do usuário...
setx PATH "%PATH%;%FFMPEG_PATH%"

if %ERRORLEVEL% EQU 0 (
    echo ✅ PATH configurado com sucesso!
    echo.
    echo 📋 IMPORTANTE: Feche e reabra o terminal para as mudanças terem efeito.
    echo.
    echo 🧪 Testando FFmpeg...
    "%FFMPEG_PATH%\ffmpeg.exe" -version >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo ✅ FFmpeg funcionando perfeitamente!
        echo.
        echo 🚀 Agora você pode usar: python down.py
    ) else (
        echo ❌ Erro ao testar FFmpeg
    )
) else (
    echo ❌ Erro ao configurar PATH
)

echo.
pause
