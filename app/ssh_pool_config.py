"""
SSH连接池配置模块
定义连接池的各种配置参数和健康检查机制
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SSHPoolConfig:
    """SSH连接池配置类"""
    
    # 连接池基本配置
    max_connections_per_server: int = 3  # 每个服务器的最大连接数
    max_idle_time: int = 300  # 连接最大空闲时间（秒）
    cleanup_interval: int = 60  # 清理线程运行间隔（秒）
    
    # 连接超时配置
    connect_timeout: int = 10  # 连接超时时间（秒）
    command_timeout: int = 30  # 命令执行超时时间（秒）
    
    # 健康检查配置
    health_check_enabled: bool = True  # 是否启用健康检查
    health_check_interval: int = 120  # 健康检查间隔（秒）
    health_check_command: str = "echo 'health_check'"  # 健康检查命令
    health_check_timeout: int = 5  # 健康检查超时时间（秒）
    
    # 重试配置
    max_retries: int = 2  # 最大重试次数
    retry_delay: int = 3  # 重试间隔（秒）
    
    # 连接池监控配置
    enable_pool_monitoring: bool = True  # 是否启用连接池监控
    pool_stats_log_interval: int = 300  # 连接池统计日志间隔（秒）
    
    # 连接验证配置
    validate_connection_on_borrow: bool = True  # 借用连接时是否验证
    validate_connection_on_return: bool = False  # 归还连接时是否验证
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'max_connections_per_server': self.max_connections_per_server,
            'max_idle_time': self.max_idle_time,
            'cleanup_interval': self.cleanup_interval,
            'connect_timeout': self.connect_timeout,
            'command_timeout': self.command_timeout,
            'health_check_enabled': self.health_check_enabled,
            'health_check_interval': self.health_check_interval,
            'health_check_command': self.health_check_command,
            'health_check_timeout': self.health_check_timeout,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'enable_pool_monitoring': self.enable_pool_monitoring,
            'pool_stats_log_interval': self.pool_stats_log_interval,
            'validate_connection_on_borrow': self.validate_connection_on_borrow,
            'validate_connection_on_return': self.validate_connection_on_return
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'SSHPoolConfig':
        """从字典创建配置对象"""
        return cls(**config_dict)
    
    def validate(self) -> bool:
        """验证配置参数的有效性"""
        try:
            if self.max_connections_per_server <= 0:
                logger.error("max_connections_per_server 必须大于 0")
                return False
            
            if self.max_idle_time <= 0:
                logger.error("max_idle_time 必须大于 0")
                return False
            
            if self.cleanup_interval <= 0:
                logger.error("cleanup_interval 必须大于 0")
                return False
            
            if self.connect_timeout <= 0:
                logger.error("connect_timeout 必须大于 0")
                return False
            
            if self.command_timeout <= 0:
                logger.error("command_timeout 必须大于 0")
                return False
            
            if self.health_check_enabled:
                if self.health_check_interval <= 0:
                    logger.error("health_check_interval 必须大于 0")
                    return False
                
                if self.health_check_timeout <= 0:
                    logger.error("health_check_timeout 必须大于 0")
                    return False
                
                if not self.health_check_command.strip():
                    logger.error("health_check_command 不能为空")
                    return False
            
            if self.max_retries < 0:
                logger.error("max_retries 不能小于 0")
                return False
            
            if self.retry_delay < 0:
                logger.error("retry_delay 不能小于 0")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {str(e)}")
            return False


class SSHPoolConfigManager:
    """SSH连接池配置管理器"""
    
    def __init__(self):
        self._config = SSHPoolConfig()
        self._config_file_path = None
    
    def get_config(self) -> SSHPoolConfig:
        """获取当前配置"""
        return self._config
    
    def update_config(self, **kwargs) -> bool:
        """更新配置参数"""
        try:
            # 创建新的配置对象
            current_dict = self._config.to_dict()
            current_dict.update(kwargs)
            
            new_config = SSHPoolConfig.from_dict(current_dict)
            
            # 验证新配置
            if not new_config.validate():
                logger.error("新配置验证失败")
                return False
            
            # 应用新配置
            self._config = new_config
            logger.info(f"SSH连接池配置已更新: {kwargs}")
            return True
            
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            return False
    
    def reset_to_default(self):
        """重置为默认配置"""
        self._config = SSHPoolConfig()
        logger.info("SSH连接池配置已重置为默认值")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        config_dict = self._config.to_dict()
        return {
            'config': config_dict,
            'is_valid': self._config.validate(),
            'description': {
                'max_connections_per_server': '每个服务器的最大连接数',
                'max_idle_time': '连接最大空闲时间（秒）',
                'cleanup_interval': '清理线程运行间隔（秒）',
                'connect_timeout': '连接超时时间（秒）',
                'command_timeout': '命令执行超时时间（秒）',
                'health_check_enabled': '是否启用健康检查',
                'health_check_interval': '健康检查间隔（秒）',
                'health_check_command': '健康检查命令',
                'health_check_timeout': '健康检查超时时间（秒）',
                'max_retries': '最大重试次数',
                'retry_delay': '重试间隔（秒）',
                'enable_pool_monitoring': '是否启用连接池监控',
                'pool_stats_log_interval': '连接池统计日志间隔（秒）',
                'validate_connection_on_borrow': '借用连接时是否验证',
                'validate_connection_on_return': '归还连接时是否验证'
            }
        }


# 全局配置管理器实例
ssh_pool_config_manager = SSHPoolConfigManager()