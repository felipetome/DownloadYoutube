# Script PowerShell para configurar PATH do FFmpeg
Write-Host "🔧 Configurando PATH do FFmpeg..." -ForegroundColor Cyan
Write-Host ""

# Caminho do FFmpeg
$FFMPEG_PATH = "C:\Users\felipetome\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0-full_build\bin"

# Verifica se o caminho existe
if (-not (Test-Path $FFMPEG_PATH)) {
    Write-Host "❌ Caminho do FFmpeg não encontrado: $FFMPEG_PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "📋 Por favor, verifique se o FFmpeg foi instalado corretamente." -ForegroundColor Yellow
    Read-Host "Pressione Enter para sair"
    exit 1
}

Write-Host "✅ Caminho do FFmpeg encontrado: $FFMPEG_PATH" -ForegroundColor Green
Write-Host ""

# Obtém o PATH atual do usuário
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")

# Verifica se já está no PATH
if ($currentPath -like "*$FFMPEG_PATH*") {
    Write-Host "ℹ️ FFmpeg já está no PATH!" -ForegroundColor Blue
} else {
    # Adiciona ao PATH do usuário
    Write-Host "🔄 Adicionando ao PATH do usuário..." -ForegroundColor Yellow
    $newPath = "$currentPath;$FFMPEG_PATH"
    
    try {
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "✅ PATH configurado com sucesso!" -ForegroundColor Green
    } catch {
        Write-Host "❌ Erro ao configurar PATH: $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Pressione Enter para sair"
        exit 1
    }
}

Write-Host ""
Write-Host "📋 IMPORTANTE: Feche e reabra o terminal para as mudanças terem efeito." -ForegroundColor Yellow
Write-Host ""

# Testa o FFmpeg
Write-Host "🧪 Testando FFmpeg..." -ForegroundColor Cyan
try {
    $ffmpegVersion = & "$FFMPEG_PATH\ffmpeg.exe" -version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ FFmpeg funcionando perfeitamente!" -ForegroundColor Green
        Write-Host ""
        Write-Host "🚀 Agora você pode usar: python down.py" -ForegroundColor Green
    } else {
        Write-Host "❌ Erro ao testar FFmpeg" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Erro ao executar FFmpeg: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Read-Host "Pressione Enter para sair"

