#!/bin/bash

# 主机巡视系统启动脚本

echo "=================================="
echo "      主机巡视系统 v2.0"
echo "=================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python 3.7+"
    exit 1
fi

# 检查依赖
if [ ! -f "requirements.txt" ]; then
    echo "❌ 找不到 requirements.txt"
    exit 1
fi

# 检查配置文件
if [ ! -f ".env" ]; then
    echo "⚠️  配置文件 .env 不存在"
    echo "📝 正在复制配置模板..."
    cp .env.example .env
    echo "✅ 请编辑 .env 文件配置系统参数"
    echo "🔑 特别注意修改 SECRET_KEY 和 ENCRYPTION_KEY"
    echo SECRET_KEY密钥生成命令：python -c "import secrets; print(secrets.token_urlsafe(32))"
    echo ENCRYPTION_KEY密钥生成命令：python -c "import os; import base64; key_bytes = os.urandom(32); print(base64.b64encode(key_bytes).decode())"
    echo ""
    echo "配置完成后请重新运行此脚本"
    exit 0
fi

# 选择运行模式
echo "请选择运行模式:"
echo "1) 开发模式 (启用控制台日志，便于调试)"
echo "2) 生产模式 (禁用控制台日志，适合长期运行)"
echo ""
echo "5秒内未选择将自动启动生产模式..."
echo ""

# 设置5秒超时
read -t 5 -p "请输入选择 (1/2): " mode_choice

# 如果超时，则自动启动生产模式
if [ $? -ne 0 ]; then
    echo ""
    echo "🚀 5秒超时，以生产模式启动..."
    python3 start_production.py
else
    case $mode_choice in
        1)
            echo "🚀 以开发模式启动..."
            python3 run.py
            ;;
        2)
            echo "🚀 以生产模式启动..."
            python3 start_production.py
            ;;
        *)
            echo "❌ 无效选择，使用默认生产模式..."
            python3 start_production.py
            ;;
    esac
fi