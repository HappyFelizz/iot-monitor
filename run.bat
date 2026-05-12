@echo off

setlocal enabledelayedexpansion
pushd "%~dp0"

set SERIAL_PORT=COM5

echo.
echo ===============================================
echo   Sistema de Monitoramento IoT - Arduino
echo ===============================================
echo.
echo [INFO] Ativando ambiente virtual...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] Virtualenv não encontrado em .venv. Usando python do PATH.
)

echo [INFO] Porta serial definida: %SERIAL_PORT%
echo [INFO] Iniciando aplicacao...
echo.

python app.py

REM Se o script terminar com erro, pausa para mostrar a mensagem
if errorlevel 1 (
    echo.
    echo [ERRO] A aplicacao finalizou com erro!
    echo Pressione qualquer tecla para sair...
    pause
)

endlocal
rem Restaurar pasta original
popd
