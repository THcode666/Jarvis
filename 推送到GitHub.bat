@echo off
chcp 65001 >nul
cd /d "%~dp0"
set REMOTE=https://github.com/THcode666/Jarvis.git

echo 本地有改动并自测通过后，执行下面三行即可同步到 GitHub：
echo   git add -A ^&^& git commit -m "说明"
echo   git push
echo.
echo 当前状态：
git status -sb
git remote -v | findstr origin
pause
