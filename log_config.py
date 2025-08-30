#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志配置模块
支持按天分割日志文件和分类存储
"""

import os
import logging
import logging.handlers
import time
import re
from datetime import datetime
from typing import Optional


class LogsAPIFilter(logging.Filter):
    """过滤掉日志API相关的请求记录"""
    
    def filter(self, record):
        """过滤日志记录"""
        # 如果日志消息包含 '/api/logs/' 路径，则过滤掉
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if '/api/logs/' in message:
                return False
        return True


class DailyRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """自定义按天轮转的日志处理器"""
    
    def __init__(self, filename, when='midnight', interval=1, backupCount=30, encoding=None, delay=False, utc=False):
        """
        初始化日志处理器
        
        Args:
            filename: 日志文件名模板
            when: 轮转时间 ('midnight' 表示每天午夜)
            interval: 轮转间隔
            backupCount: 保留的备份文件数量
            encoding: 文件编码
            delay: 是否延迟创建文件
            utc: 是否使用UTC时间
        """
        # 确保日志目录存在
        log_dir = os.path.dirname(filename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 调用父类构造函数
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        
        # 设置自定义的suffix格式，匹配我们的文件命名规则
        if when == 'midnight':
            self.suffix = '%Y%m%d'
            self.extMatch = re.compile(r'^\d{8}(\.\w+)?$')
    
    def doRollover(self):
        """
        执行日志轮转
        重写此方法以确保正确的文件命名
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        # 获取轮转时间点（昨天的日期）
        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            
        # 获取基础文件名（不含路径）
        dir_name, file_name = os.path.split(self.baseFilename)
        base_name, ext = os.path.splitext(file_name)
        
        # 移除可能已存在的日期后缀
        if '-' in base_name and base_name.split('-')[-1].isdigit() and len(base_name.split('-')[-1]) == 8:
            base_name = '-'.join(base_name.split('-')[:-1])
        
        # 生成正确的轮转文件名
        date_str = time.strftime(self.suffix, timeTuple)
        dfn = os.path.join(dir_name, f"{base_name}-{date_str}{ext}")
        
        # 如果目标文件已存在，则删除
        if os.path.exists(dfn):
            os.remove(dfn)
        
        # 重命名当前日志文件
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn)
        
        # 删除过期的日志文件
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                os.remove(s)
        
        # 延迟创建新文件
        if not self.delay:
            self.stream = self._open()
        
        # 更新下次轮转时间
        newRolloverAt = self.computeRollover(time.time())
        while newRolloverAt <= time.time():
            newRolloverAt = newRolloverAt + self.interval
        self.rolloverAt = newRolloverAt

def setup_logging(app_name: str = 'main', log_level: str = 'INFO', console_output: bool = True) -> logging.Logger:
    """
    设置应用程序日志配置
    
    Args:
        app_name: 应用名称 (run/production/scheduler等)
        log_level: 日志级别
        console_output: 是否在控制台输出日志
        
    Returns:
        配置好的logger对象
    """
    # 创建logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除已有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 1. 文件处理器 - 按天分割
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 使用不带日期的文件名，让DailyRotatingFileHandler处理日期
    log_filename = os.path.join(log_dir, f'{app_name}.log')
    
    file_handler = DailyRotatingFileHandler(
        filename=log_filename,
        when='midnight',
        interval=1,
        backupCount=30,  # 保留30天的日志
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    # 2. 控制台处理器 - 根据参数决定是否添加
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)  # 控制台只显示INFO及以上级别
        logger.addHandler(console_handler)
    
    # 3. 错误日志单独存储
    error_log_filename = os.path.join(log_dir, f'{app_name}-error.log')
    error_handler = DailyRotatingFileHandler(
        filename=error_log_filename,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)
    
    return logger


def setup_flask_app_logging(app, app_name: str = 'flask', console_output: bool = True):
    """
    为Flask应用设置日志配置
    
    Args:
        app: Flask应用实例
        app_name: 应用名称
        console_output: 是否在控制台输出
    """
    # 设置Flask应用的日志级别
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    
    # 设置根日志器
    setup_logging(app_name, log_level, console_output)
    
    # 配置Flask应用日志
    app.logger.setLevel(getattr(logging, log_level.upper()))
    
    # 特别设置service_monitor模块的日志级别为INFO，以便看到详细的调试信息
    service_monitor_logger = logging.getLogger('app.service_monitor')
    service_monitor_logger.setLevel(logging.INFO)
    
    # 配置werkzeug日志（Flask开发服务器）
    werkzeug_logger = logging.getLogger('werkzeug')
    # 添加过滤器，过滤掉日志API相关的请求
    logs_api_filter = LogsAPIFilter()
    werkzeug_logger.addFilter(logs_api_filter)
    
    if not console_output:
        # 如果不需要控制台输出，将werkzeug日志级别设置为WARNING，减少输出
        werkzeug_logger.setLevel(logging.WARNING)
    
    return app.logger


def get_log_files_info():
    """
    获取日志文件信息
    
    Returns:
        日志文件列表及其信息
    """
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        return []
    
    log_files = []
    for filename in os.listdir(log_dir):
        if filename.endswith('.log'):
            filepath = os.path.join(log_dir, filename)
            stat = os.stat(filepath)
            log_files.append({
                'filename': filename,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'created': datetime.fromtimestamp(stat.st_ctime)
            })
    
    # 按修改时间排序
    log_files.sort(key=lambda x: x['modified'], reverse=True)
    return log_files


def cleanup_old_logs(days: int = 30):
    """
    清理超过指定天数的日志文件
    
    Args:
        days: 保留天数
    """
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        return
    
    cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
    
    for filename in os.listdir(log_dir):
        if filename.endswith('.log'):
            filepath = os.path.join(log_dir, filename)
            if os.path.getmtime(filepath) < cutoff_time:
                try:
                    os.remove(filepath)
                    print(f"已删除过期日志文件: {filename}")
                except Exception as e:
                    print(f"删除日志文件失败 {filename}: {e}")


if __name__ == '__main__':
    # 测试日志配置
    logger = setup_logging('test', 'DEBUG', True)
    logger.info("测试信息日志")
    logger.warning("测试警告日志")
    logger.error("测试错误日志")
    
    # 显示日志文件信息
    files = get_log_files_info()
    print("\n当前日志文件:")
    for file_info in files:
        print(f"- {file_info['filename']} ({file_info['size']} bytes, {file_info['modified']})")