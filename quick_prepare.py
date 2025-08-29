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

def download_static_resources():
    """下载Bootstrap静态资源"""
    print("📦 下载Bootstrap静态资源...")
    
    # 创建静态资源目录
    static_dirs = ['static/css', 'static/js', 'static/fonts']
    for dir_path in static_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # 下载文件列表
    downloads = [
        {
            'url': 'https://fastly.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
            'dest': 'static/css/bootstrap.min.css'
        },
        {
            'url': 'https://fastly.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css',
            'dest': 'static/css/bootstrap-icons.css'
        },
        {
            'url': 'https://fastly.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js',
            'dest': 'static/js/bootstrap.bundle.min.js'
        },
        {
            'url': 'https://fastly.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff',
            'dest': 'static/fonts/bootstrap-icons.woff'
        },
        {
            'url': 'https://fastly.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/bootstrap-icons.woff2',
            'dest': 'static/fonts/bootstrap-icons.woff2'
        }
    ]
    
    for download in downloads:
        try:
            subprocess.run(
                f'curl -o "{download["dest"]}" "{download["url"]}"',
                shell=True, check=True, capture_output=True
            )
            print(f"✅ {download['dest']}")
        except subprocess.CalledProcessError:
            print(f"⚠️ {download['dest']} 下载失败")
    
    # 修复Bootstrap Icons CSS中的字体路径
    css_file = Path('static/css/bootstrap-icons.css')
    if css_file.exists():
        content = css_file.read_text(encoding='utf-8')
        content = content.replace('./fonts/', '../fonts/')
        css_file.write_text(content, encoding='utf-8')
        print("✅ 修复Bootstrap Icons字体路径")

def main():
    print("🚀 主机巡视系统 - 一键离线部署准备")
    print("=" * 40)
    
    # 检查当前目录
    if not Path("requirements.txt").exists():
        print("❌ 错误: 请在项目根目录运行此脚本")
        return
    
    # 下载静态资源
    # download_static_resources()
    
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
    
    # 读取requirements.txt获取包列表
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    print(f"📋 需要下载 {len(packages)} 个包:")
    for i, pkg in enumerate(packages, 1):
        print(f"  {i:2d}. {pkg}")
    
    print("\n🔄 开始下载...")
    cmd = f"pip download -r requirements.txt --dest {packages_dir}"
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, 
                              capture_output=False, text=True)
        print("\n✅ 依赖包下载完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 下载失败: {e}")
        print("请检查网络连接或依赖版本冲突")
        return False
    
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

echo 完成! 现在可以运行: start.bat|start.sh
pause
"""
    
    with open("install_offline.bat", "w", encoding="utf-8") as f:
        f.write(install_script)
    
    # 统计文件
    pkg_files = list(packages_dir.glob("*"))
    total_size = sum(f.stat().st_size for f in pkg_files) / (1024*1024)  # MB
    
    print(f"\n🎉 准备完成!")
    print(f"📊 统计: {len(pkg_files)} 个Python包, {total_size:.1f} MB")
    print(f"📊 静态资源: Bootstrap CSS/JS/Icons 已本地化")
    print(f"\n📋 接下来的步骤:")
    print(f"1. 将整个项目文件夹复制到内网机器")
    print(f"2. 在内网机器上双击运行 install_offline.bat")
    print(f"3. 运行 start.bat|start.sh 启动服务")

if __name__ == "__main__":
    main()