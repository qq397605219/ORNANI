@echo off
echo 🚀 启动 OpenRouter API Proxy...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 安装依赖
echo 📦 安装依赖包...
pip install -r requirements.txt

REM 启动服务
echo.
echo 🎯 启动服务...
python start.py

pause