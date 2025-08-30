#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据迁移脚本：将通知通道的OSS配置迁移到全局配置表

使用方法：
1. 确保数据库已经创建了 oss_config 表
2. 运行此脚本：python migrate_oss_config.py
3. 脚本会自动检查现有通道的OSS配置并迁移到全局配置
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, NotificationChannel, OSSConfig

def migrate_oss_config():
    """迁移OSS配置到全局配置表"""
    app = create_app()
    
    with app.app_context():
        try:
            print("开始OSS配置迁移...")
            
            # 检查是否已存在全局OSS配置
            existing_config = OSSConfig.query.first()
            if existing_config:
                print(f"发现已存在的全局OSS配置 (ID: {existing_config.id})")
                print(f"配置状态: {'启用' if existing_config.is_enabled else '禁用'}")
                print(f"Endpoint: {existing_config.endpoint}")
                print(f"Bucket: {existing_config.bucket_name}")
                
                choice = input("是否要覆盖现有配置？(y/N): ").strip().lower()
                if choice != 'y':
                    print("迁移已取消")
                    return
                
                # 删除现有配置
                db.session.delete(existing_config)
                db.session.commit()
                print("已删除现有全局OSS配置")
            
            # 由于NotificationChannel模型中的OSS字段已被移除，我们直接创建默认的全局OSS配置
            print("注意：NotificationChannel模型中的OSS字段已被移除，创建默认全局OSS配置")
            
            # 创建默认的禁用配置
            default_config = OSSConfig(
                is_enabled=False,
                endpoint='',
                access_key_id='',
                access_key_secret='',
                bucket_name='',
                folder_path='reports',
                expires_in_hours=24
            )
            db.session.add(default_config)
            db.session.commit()
            print("✓ 已创建默认的全局OSS配置（禁用状态）")
            print(f"✓ 全局OSS配置创建成功 (ID: {default_config.id})")
            
            # 显示所有通知通道
            print("\n当前通知通道列表：")
            all_channels = NotificationChannel.query.all()
            for channel in all_channels:
                print(f"  - {channel.name} (ID: {channel.id})")
            
            print("\n迁移完成！")
            print("注意：")
            print("1. NotificationChannel模型中的OSS字段已被移除")
            print("2. 现在所有通知都将使用全局OSS配置")
            print("3. 可以通过Web界面的'OSS配置'按钮管理全局配置")
            print("4. 如需启用OSS功能，请在Web界面中配置全局OSS设置")
            
        except Exception as e:
            db.session.rollback()
            print(f"迁移失败: {str(e)}")
            import traceback
            traceback.print_exc()

def show_current_status():
    """显示当前OSS配置状态"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=== 当前OSS配置状态 ===")
            
            # 全局OSS配置
            global_config = OSSConfig.query.first()
            if global_config:
                print(f"\n全局OSS配置 (ID: {global_config.id}):")
                print(f"  状态: {'启用' if global_config.is_enabled else '禁用'}")
                print(f"  Endpoint: {global_config.endpoint}")
                print(f"  Bucket: {global_config.bucket_name}")
                print(f"  文件夹: {global_config.folder_path}")
                print(f"  有效期: {global_config.expires_in_hours} 小时")
                print(f"  创建时间: {global_config.created_at}")
                print(f"  更新时间: {global_config.updated_at}")
            else:
                print("\n未找到全局OSS配置")
            
            # 通知通道列表（OSS字段已移除）
            channels = NotificationChannel.query.all()
            print(f"\n通知通道列表 (共 {len(channels)} 个):")
            
            for channel in channels:
                print(f"  - {channel.name} (ID: {channel.id})")
                print(f"    Webhook URL: {channel.webhook_url}")
                print(f"    状态: {'启用' if channel.is_enabled else '禁用'}")
                print(f"    创建时间: {channel.created_at}")
                print()
                
        except Exception as e:
            print(f"查询失败: {str(e)}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        show_current_status()
    else:
        migrate_oss_config()