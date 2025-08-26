#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# 添加项目根目录到Python路径
basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

# 切换到项目根目录
os.chdir(basedir)

# 设置日志配置(在导入Flask应用之前)
from log_config import setup_logging
logger = setup_logging('run', 'INFO', True)  # 开发环境显示控制台日志

logger.info(f"项目根目录: {basedir}")
logger.info(f"Python路径: {sys.path[0]}")
logger.info(f"当前工作目录: {os.getcwd()}")
logger.info(f"切换后工作目录: {os.getcwd()}")

try:
    from app import create_app
    logger.info("✓ 模块导入成功")
    
    app = create_app()
    logger.info("✓ Flask应用创建成功")
    logger.info(f"✓ 模板目录: {app.template_folder}")
    logger.info(f"✓ 静态文件目录: {app.static_folder}")
    
    # 检查模板文件是否存在
    template_path = os.path.join(app.template_folder, 'index.html')
    if os.path.exists(template_path):
        logger.info(f"✓ 模板文件存在: {template_path}")
    else:
        logger.error(f"✗ 模板文件不存在: {template_path}")
        
except Exception as e:
    logger.error(f"✗ 初始化失败: {str(e)}")
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)

if __name__ == '__main__':
    logger.info("启动完整版主机巡视系统...")
    logger.info(f"请在浏览器中访问: http://{app.config.get('HOST', '0.0.0.0')}:{app.config.get('PORT', 5000)}")
    logger.info("日志文件保存在 logs/ 目录下")
    logger.info("按 Ctrl+C 停止服务")
    
    try:
        # 开发环境运行，禁用自动重载避免重复启动
        app.run(
            debug=app.config.get('DEBUG', True), 
            host=app.config.get('HOST', '0.0.0.0'), 
            port=app.config.get('PORT', 5000), 
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("正在停止系统...")
        logger.info("系统已停止")
    except Exception as e:
        logger.error(f"运行失败: {e}")
        sys.exit(1)