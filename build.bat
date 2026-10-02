@echo off
chcp 65001 >nul
REM 贾维斯 Jarvis 一键打包脚本：生成 dist\贾维斯Jarvis.exe（单文件、免安装）
cd /d "%~dp0"
echo ==============================================
echo   打包 贾维斯 Jarvis ...
echo ==============================================
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "贾维斯Jarvis" ^
  --icon "assets\jarvis.ico" ^
  --add-data "assets;assets" ^
  --exclude-module PyQt5 --exclude-module tkinter ^
  main.py
if errorlevel 1 (
  echo 打包失败！
  pause
  exit /b 1
)
echo.
echo 打包完成：dist\贾维斯Jarvis.exe
pause
