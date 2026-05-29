@echo off
chcp 65001 >nul

echo ==================================
echo       主机巡视系统 v2.0
echo ==================================

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python未安装，请先安装Python 3.8
    pause
    exit /b 1
)

REM 检查配置文件
if not exist ".env" (
    echo 配置文件 .env 不存在
    copy .env.example .env
    echo 已创建配置文件，请编辑 .env 后重新运行
    pause
    exit /b 0
)

echo 启动生产模式...
python start_production.py

pause
