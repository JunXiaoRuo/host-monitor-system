@echo off
chcp 65001 >nul

echo ==================================
echo       主机巡视系统 v2.0
echo ==================================

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python未安装，请先安装Python 3.8
    pause
    exit /b 1
)

REM 检查配置文件
if not exist ".env" (
    echo ⚠️  配置文件 .env 不存在
    echo 📝 正在复制配置模板...
    copy .env.example .env
    echo ✅ 请编辑 .env 文件配置系统参数
    echo 🔑 特别注意修改 SECRET_KEY 和 ENCRYPTION_KEY
    echo.
    echo 配置完成后请重新运行此脚本
    pause
    exit /b 0
)

REM 选择运行模式
echo 请选择运行模式:
echo 1) 开发模式 (启用控制台日志，便于调试)
echo 2) 生产模式 (禁用控制台日志，适合长期运行)
echo 3) 自动生产模式 (5秒后自动启动生产模式)
echo.
choice /c 123 /m "请选择运行模式" /t 5 /d 3

if errorlevel 3 (
    echo.
    echo ⏰ 5秒后自动启动生产模式...
    timeout /t 5 /nobreak >nul
    echo 🚀 以生产模式启动...
    python start_production.py
) else if errorlevel 2 (
    echo 🚀 以生产模式启动...
    python start_production.py
) else (
    echo 🚀 以开发模式启动...
    python run.py
)

pause
