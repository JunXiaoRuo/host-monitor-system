#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态资源本地化验证脚本
检查所有必需的本地静态资源是否存在
"""

from pathlib import Path
import sys

def check_static_resources():
    """检查静态资源是否完整"""
    print("🔍 检查静态资源本地化状态...")
    
    required_files = [
        'static/css/bootstrap.min.css',
        'static/css/bootstrap-icons.css', 
        'static/js/bootstrap.bundle.min.js',
        'static/js/main.js',
        'static/fonts/bootstrap-icons.woff',
        'static/fonts/bootstrap-icons.woff2'
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            size = path.stat().st_size / 1024  # KB
            existing_files.append(f"✅ {file_path} ({size:.1f} KB)")
        else:
            missing_files.append(f"❌ {file_path}")
    
    print("\n📋 静态资源检查结果:")
    for file_info in existing_files:
        print(file_info)
    
    if missing_files:
        print("\n⚠️ 缺失的文件:")
        for file_info in missing_files:
            print(file_info)
        return False
    
    return True

def check_templates():
    """检查模板文件是否使用本地资源"""
    print("\n🔍 检查模板文件...")
    
    template_files = [
        'templates/login.html',
        'templates/index.html', 
        'templates/setup.html'
    ]
    
    issues = []
    for template_path in template_files:
        path = Path(template_path)
        if path.exists():
            content = path.read_text(encoding='utf-8')
            # 检查是否还有CDN链接
            if 'fastly.jsdelivr.net' in content:
                issues.append(f"⚠️ {template_path} 仍包含CDN链接")
            elif "{{ url_for('static'" in content:
                print(f"✅ {template_path} 使用本地资源")
            else:
                issues.append(f"❓ {template_path} 资源引用状态不明")
        else:
            issues.append(f"❌ {template_path} 文件不存在")
    
    if issues:
        print("\n⚠️ 发现的问题:")
        for issue in issues:
            print(issue)
        return False
    
    return True

def check_bootstrap_icons_css():
    """检查Bootstrap Icons CSS中的字体路径"""
    print("\n🔍 检查Bootstrap Icons字体路径...")
    
    css_path = Path('static/css/bootstrap-icons.css')
    if not css_path.exists():
        print("❌ bootstrap-icons.css 文件不存在")
        return False
    
    content = css_path.read_text(encoding='utf-8')
    if '../fonts/bootstrap-icons' in content:
        print("✅ Bootstrap Icons 字体路径已正确配置")
        return True
    else:
        print("❌ Bootstrap Icons 字体路径配置错误")
        return False

def main():
    print("🚀 主机巡视系统 - 离线资源验证工具")
    print("=" * 50)
    
    all_good = True
    
    # 检查静态资源
    if not check_static_resources():
        all_good = False
    
    # 检查模板文件  
    if not check_templates():
        all_good = False
    
    # 检查Bootstrap Icons配置
    if not check_bootstrap_icons_css():
        all_good = False
    
    print("\n" + "=" * 50)
    if all_good:
        print("🎉 验证通过！所有静态资源已正确本地化")
        print("\n✅ 系统已准备好进行内网离线部署")
        print("📝 可以安全地在无网络环境中使用")
    else:
        print("❌ 验证失败！请检查并修复上述问题")
        print("\n💡 建议:")
        print("1. 运行 python quick_prepare.py 重新下载资源")
        print("2. 检查网络连接是否正常")
        print("3. 确保有足够的磁盘空间")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())