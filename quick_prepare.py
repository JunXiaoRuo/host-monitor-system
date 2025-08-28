#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主机巡视系统 - 一键离线部署准备工具
简化版本，用于快速准备离线部署包
"""

import os
import subprocess
import sys
from pathlib import Path

def main():
    print("🚀 主机巡视系统 - 一键离线部署准备")
    print("=" * 40)
    
    # 检查当前目录
    if not Path("requirements.txt").exists():
        print("❌ 错误: 请在项目根目录运行此脚本")
        return
    
    # 创建依赖包目录
    packages_dir = Path("python-packages")
    if packages_dir.exists():
        print("🔄 清理现有的依赖包目录...")
        import shutil
        shutil.rmtree(packages_dir)
    
    packages_dir.mkdir()
    print(f"✅ 创建目录: {packages_dir}")
    
    # 下载依赖包
    print("📦 下载依赖包...")
    cmd = f"pip download -r requirements.txt --dest {packages_dir}"
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              capture_output=True, text=True)
        print("✅ 依赖包下载完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 下载失败: {e}")
        print("🔧 尝试手动下载主要包...")
        
        # 手动下载主要包
        packages = [
            "Flask==2.3.3", "Flask-SQLAlchemy==3.0.5", "paramiko==3.3.1",
            "APScheduler==3.10.4", "psutil==5.9.6", "requests==2.31.0",
            "python-dotenv==1.0.0", "pandas==2.0.3", "openpyxl==3.1.2"
        ]
        
        for pkg in packages:
            try:
                subprocess.run(f"pip download {pkg} --dest {packages_dir}", 
                             shell=True, check=True, capture_output=True)
                print(f"✅ {pkg}")
            except:
                print(f"⚠️ {pkg} 下载失败")
    
    # 创建安装脚本
    install_script = """@echo off
echo 主机巡视系统 - 离线安装
echo ========================

python --version
if errorlevel 1 (
    echo 错误: 请先安装Python 3.8+
    pause
    exit /b 1
)

echo 安装依赖包...
pip install --no-index --find-links python-packages -r requirements.txt

echo 验证安装...
python -c "import flask; print('安装成功!')"

echo 完成! 现在可以运行: python run.py
pause
"""
    
    with open("install_offline.bat", "w", encoding="utf-8") as f:
        f.write(install_script)
    
    # 统计文件
    pkg_files = list(packages_dir.glob("*"))
    total_size = sum(f.stat().st_size for f in pkg_files) / (1024*1024)  # MB
    
    print(f"\n🎉 准备完成!")
    print(f"📊 统计: {len(pkg_files)} 个包, {total_size:.1f} MB")
    print(f"\n📋 接下来的步骤:")
    print(f"1. 将整个项目文件夹复制到内网机器")
    print(f"2. 在内网机器上双击运行 install_offline.bat")
    print(f"3. 运行 python run.py 启动服务")

if __name__ == "__main__":
    main()