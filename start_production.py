#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主机巡视系统 - 生产环境启动脚本
避免调试模式的重复启动问题
"""

import os
import sys

# 强制设置生产环境参数
os.environ['CONSOLE_LOG_ENABLED'] = 'False'  # 生产环境强制禁用控制台日志
os.environ['DEBUG'] = 'False'                # 生产环境强制禁用调试模式
os.environ['FLASK_DEBUG'] = 'False'          # 生产环境强制禁用Flask调试

# 添加项目根目录到Python路径
basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

# 切换到项目根目录
os.chdir(basedir)

# 设置日志配置(在导入Flask应用之前)
from log_config import setup_logging
logger = setup_logging('production', 'INFO', False)  # 生产环境不显示控制台日志

# 额外确保所有日志都不会输出到控制台
import logging

# 禁用根日志器的控制台输出
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
        root_logger.removeHandler(handler)

# 设置所有已知可能产生控制台输出的日志器
silent_loggers = [
    'apscheduler',
    'apscheduler.scheduler', 
    'apscheduler.executors',
    'apscheduler.jobstores',
    'apscheduler.executors.default',
    'werkzeug',
    'urllib3',
    'requests',
    'paramiko',
    'cryptography',
    'sqlalchemy.engine',
    'sqlalchemy.pool'
]

for logger_name in silent_loggers:
    silent_logger = logging.getLogger(logger_name)
    silent_logger.setLevel(logging.ERROR)  # 提高到ERROR级别，避免WARNING输出
    # 移除控制台处理器
    for handler in silent_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            silent_logger.removeHandler(handler)
    # 设置不传播到父日志器
    silent_logger.propagate = False
    # 确保没有处理器
    silent_logger.handlers.clear()

logger.info(f"项目根目录: {basedir}")
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
    print("="*50)
    print("启动主机巡视系统（生产模式）")
    print("="*50)
    print("系统特性:")
    print("- 主机监控与巡视")
    print("- 服务状态监控") 
    print("- 计划任务调度")
    print("- 监控报告生成")
    print("- 告警通知推送")
    print("="*50)
    print(f"请在浏览器中访问: http://{app.config.get('HOST', '0.0.0.0')}:{app.config.get('PORT', 5000)}")
    print("生产环境模式: 控制台日志已禁用，日志保存在 logs/ 目录")
    print("按 Ctrl+C 停止服务")
    print("="*50)
    
    logger.info("初始化生产环境主机巡视系统")
    logger.info(f"监听地址: {app.config.get('HOST', '0.0.0.0')}:{app.config.get('PORT', 5000)}")
    
    try:
        # 生产环境运行，禁用调试和自动重载
        app.run(
            debug=False,                              # 关闭调试模式
            host=app.config.get('HOST', '0.0.0.0'),  # 从配置读取主机地址
            port=app.config.get('PORT', 5000),       # 从配置读取端口
            use_reloader=False,                       # 禁用自动重载
            threaded=True                             # 启用多线程
        )
    except KeyboardInterrupt:
        logger.info("正在停止系统...")
        print("\n正在停止系统...")
        logger.info("系统已停止")
        print("系统已停止")
    except Exception as e:
        logger.error(f"启动失败: {e}")
        print(f"启动失败: {e}")
        sys.exit(1)