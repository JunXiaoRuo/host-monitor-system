import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Config:
    # 获取项目根目录
    _basedir = os.path.abspath(os.path.dirname(__file__))
    
    # 应用基本配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('ENCRYPTION_KEY') or 'your-secret-key-here-please-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'True').lower() in ['true', '1', 'yes']
    
    # 支持Flask 2.3+的FLASK_DEBUG环境变量
    if 'FLASK_DEBUG' in os.environ:
        DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 'yes']
    
    # 服务器配置
    HOST = os.environ.get('HOST') or '0.0.0.0'
    PORT = int(os.environ.get('PORT') or 5000)
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(_basedir, "instance", "host_monitor.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SSH配置
    SSH_TIMEOUT = int(os.environ.get('SSH_TIMEOUT') or 30)
    SSH_CONNECT_TIMEOUT = int(os.environ.get('SSH_CONNECT_TIMEOUT') or 10)
    
    # 默认阈值配置
    DEFAULT_CPU_THRESHOLD = float(os.environ.get('DEFAULT_CPU_THRESHOLD') or 80.0)
    DEFAULT_MEMORY_THRESHOLD = float(os.environ.get('DEFAULT_MEMORY_THRESHOLD') or 80.0)
    DEFAULT_DISK_THRESHOLD = float(os.environ.get('DEFAULT_DISK_THRESHOLD') or 80.0)
    
    # 日志配置
    LOG_FILE = os.environ.get('LOG_FILE') or 'host_monitor.log'
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_DIR = os.environ.get('LOG_DIR') or 'logs'
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS') or 30)
    CONSOLE_LOG_ENABLED = os.environ.get('CONSOLE_LOG_ENABLED', 'True').lower() in ['true', '1', 'yes']
    CONSOLE_LOG_LEVEL = os.environ.get('CONSOLE_LOG_LEVEL') or 'INFO'
    
    # 报告配置
    REPORT_DIR = os.environ.get('REPORT_DIR') or 'reports'
    
    # 调度器配置
    SCHEDULER_API_ENABLED = os.environ.get('SCHEDULER_API_ENABLED', 'True').lower() in ['true', '1', 'yes']
    
    # 加密配置
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    # 如果没有设置ENCRYPTION_KEY，生成一个新的Fernet密钥
    if not ENCRYPTION_KEY:
        from cryptography.fernet import Fernet
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("未设置ENCRYPTION_KEY环境变量，生成临时密钥（重启后会丢失）")
        ENCRYPTION_KEY = Fernet.generate_key().decode()
    
    # 性能配置
    MAX_CONCURRENT_MONITORS = int(os.environ.get('MAX_CONCURRENT_MONITORS') or 10)
    MONITOR_TIMEOUT = int(os.environ.get('MONITOR_TIMEOUT') or 300)
    
    # 通知配置
    WEBHOOK_TIMEOUT = int(os.environ.get('WEBHOOK_TIMEOUT') or 30)
    DEFAULT_NOTIFICATION_CHANNEL = os.environ.get('DEFAULT_NOTIFICATION_CHANNEL')