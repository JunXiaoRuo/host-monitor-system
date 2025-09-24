import paramiko
import socket
import logging
import time
import threading
from typing import Dict, Any, Optional, Tuple, List
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

# 导入配置管理器
from app.ssh_pool_config import ssh_pool_config_manager, SSHPoolConfig

logger = logging.getLogger(__name__)

@dataclass
class ConnectionInfo:
    """连接信息"""
    host: str
    port: int
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    
    def __hash__(self):
        return hash((self.host, self.port, self.username, self.password, self.private_key_path))
    
    def __eq__(self, other):
        if not isinstance(other, ConnectionInfo):
            return False
        return (self.host == other.host and 
                self.port == other.port and 
                self.username == other.username and
                self.password == other.password and
                self.private_key_path == other.private_key_path)

class PooledSSHConnection:
    """连接池中的SSH连接"""
    
    def __init__(self, client: paramiko.SSHClient, conn_info: ConnectionInfo, config: SSHPoolConfig):
        self.client = client
        self.conn_info = conn_info
        self.config = config
        self.created_time = datetime.now()
        self.last_used_time = datetime.now()
        self.last_health_check = datetime.now()
        self.is_healthy = True
        self.use_count = 0
        self.is_in_use = False
    
    def mark_used(self):
        """标记连接被使用"""
        self.last_used_time = datetime.now()
        self.use_count += 1
        self.is_in_use = True
    
    def mark_returned(self):
        """标记连接被归还"""
        self.is_in_use = False
    
    def is_expired(self) -> bool:
        """检查连接是否过期"""
        return (datetime.now() - self.last_used_time).total_seconds() > self.config.max_idle_time
    
    def needs_health_check(self) -> bool:
        """检查是否需要健康检查"""
        if not self.config.health_check_enabled:
            return False
        return (datetime.now() - self.last_health_check).total_seconds() > self.config.health_check_interval
    
    def perform_health_check(self) -> bool:
        """执行健康检查"""
        if not self.config.health_check_enabled:
            return True
            
        try:
            stdin, stdout, stderr = self.client.exec_command(
                self.config.health_check_command, 
                timeout=self.config.health_check_timeout
            )
            result = stdout.read().decode().strip()
            self.last_health_check = datetime.now()
            self.is_healthy = True
            return True
        except Exception as e:
            logger.warning(f"健康检查失败 - {self.conn_info.host}:{self.conn_info.port}: {str(e)}")
            self.is_healthy = False
            return False
    
    def close(self):
        """关闭连接"""
        try:
            if self.client:
                self.client.close()
        except Exception as e:
            logger.warning(f"关闭连接时出错: {str(e)}")

class SSHConnectionPool:
    """SSH连接池"""
    
    def __init__(self, config: Optional[SSHPoolConfig] = None):
        self.config = config or ssh_pool_config_manager.get_config()
        self.pools: Dict[ConnectionInfo, List[PooledSSHConnection]] = {}
        self.lock = threading.RLock()
        self.cleanup_thread = None
        self.health_check_thread = None
        self.monitoring_thread = None
        self.is_running = True
        
        # 统计信息
        self.stats = {
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'total_connections_borrowed': 0,
            'total_connections_returned': 0,
            'total_health_checks': 0,
            'failed_health_checks': 0,
            'pool_hits': 0,
            'pool_misses': 0
        }
        
        self._start_background_threads()
    
    def _start_background_threads(self):
        """启动后台线程"""
        # 清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_connections, daemon=True)
        self.cleanup_thread.start()
        
        # 健康检查线程
        if self.config.health_check_enabled:
            self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
            self.health_check_thread.start()
        
        # 监控线程
        if self.config.enable_pool_monitoring:
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
    
    def get_connection(self, conn_info: ConnectionInfo) -> PooledSSHConnection:
        """从连接池获取连接"""
        with self.lock:
            logger.info(f"连接池查找: {conn_info.host}:{conn_info.port}")
            logger.info(f"当前连接池键值: {list(self.pools.keys())}")
            logger.info(f"查找的连接信息: {conn_info}")
            
            # 尝试从池中获取可用连接
            if conn_info in self.pools:
                pool = self.pools[conn_info]
                logger.info(f"连接池中找到 {conn_info.host}:{conn_info.port} 的连接池，共 {len(pool)} 个连接")
                for conn in pool[:]:  # 创建副本以避免修改时的问题
                    if not conn.is_in_use and conn.is_healthy:
                        # 验证连接（如果启用）
                        if self.config.validate_connection_on_borrow:
                            if not conn.perform_health_check():
                                pool.remove(conn)
                                conn.close()
                                self.stats['failed_health_checks'] += 1
                                logger.debug(f"连接健康检查失败，移除连接: {conn_info.host}:{conn_info.port}")
                                continue
                        
                        conn.mark_used()
                        self.stats['total_connections_borrowed'] += 1
                        self.stats['pool_hits'] += 1
                        logger.info(f"复用连接池中的连接: {conn_info.host}:{conn_info.port}")
                        return conn
                logger.info(f"连接池中没有可用连接: {conn_info.host}:{conn_info.port}")
            else:
                logger.info(f"连接池中没有找到 {conn_info.host}:{conn_info.port} 的连接池")
            
            # 池中没有可用连接，创建新连接
            self.stats['pool_misses'] += 1
            logger.info(f"创建新的SSH连接: {conn_info.host}:{conn_info.port}")
            return self._create_new_connection(conn_info)
    
    def _create_new_connection(self, conn_info: ConnectionInfo) -> PooledSSHConnection:
        """创建新的SSH连接"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 准备认证参数
            auth_kwargs = {
                'hostname': conn_info.host,
                'port': conn_info.port,
                'username': conn_info.username,
                'timeout': self.config.connect_timeout
            }
            
            if conn_info.private_key_path:
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(conn_info.private_key_path)
                    auth_kwargs['pkey'] = private_key
                except Exception:
                    try:
                        private_key = paramiko.Ed25519Key.from_private_key_file(conn_info.private_key_path)
                        auth_kwargs['pkey'] = private_key
                    except Exception as e:
                        raise Exception(f"无法加载私钥文件: {str(e)}")
            elif conn_info.password:
                auth_kwargs['password'] = conn_info.password
            else:
                raise Exception("必须提供密码或私钥文件")
            
            client.connect(**auth_kwargs)
            
            pooled_conn = PooledSSHConnection(client, conn_info, self.config)
            pooled_conn.mark_used()
            
            # 添加到连接池
            if conn_info not in self.pools:
                self.pools[conn_info] = []
            self.pools[conn_info].append(pooled_conn)
            
            self.stats['total_connections_created'] += 1
            self.stats['total_connections_borrowed'] += 1
            
            logger.debug(f"创建新SSH连接: {conn_info.host}:{conn_info.port}")
            return pooled_conn
            
        except Exception as e:
            logger.error(f"创建SSH连接失败 - {conn_info.host}:{conn_info.port}: {str(e)}")
            raise
    
    def return_connection(self, pooled_conn: PooledSSHConnection):
        """归还连接到连接池"""
        with self.lock:
            try:
                # 验证连接（如果启用）
                if self.config.validate_connection_on_return:
                    if not pooled_conn.perform_health_check():
                        logger.debug(f"连接归还时健康检查失败，移除连接: {pooled_conn.conn_info.host}:{pooled_conn.conn_info.port}")
                        self._remove_connection(pooled_conn)
                        return
                
                pooled_conn.mark_returned()
                self.stats['total_connections_returned'] += 1
                logger.info(f"连接已归还到连接池: {pooled_conn.conn_info.host}:{pooled_conn.conn_info.port}")
                
                # 检查连接池大小限制
                pool = self.pools.get(pooled_conn.conn_info, [])
                active_connections = [conn for conn in pool if not conn.is_in_use]
                
                if len(active_connections) >= self.config.max_connections_per_server:
                    # 连接池已满，关闭最旧的连接
                    oldest_conn = min(active_connections, key=lambda x: x.last_used_time)
                    logger.debug(f"连接池已满，关闭最旧的连接: {pooled_conn.conn_info.host}:{pooled_conn.conn_info.port}")
                    self._remove_connection(oldest_conn)
                
            except Exception as e:
                logger.error(f"归还连接时出错: {str(e)}")
                self._remove_connection(pooled_conn)
    
    def _remove_connection(self, pooled_conn: PooledSSHConnection):
        """从连接池中移除连接"""
        try:
            pool = self.pools.get(pooled_conn.conn_info, [])
            if pooled_conn in pool:
                pool.remove(pooled_conn)
            pooled_conn.close()
            self.stats['total_connections_closed'] += 1
        except Exception as e:
            logger.error(f"移除连接时出错: {str(e)}")
    
    def _cleanup_expired_connections(self):
        """清理过期连接的后台线程"""
        while self.is_running:
            try:
                time.sleep(self.config.cleanup_interval)
                
                with self.lock:
                    for conn_info, pool in list(self.pools.items()):
                        expired_connections = [
                            conn for conn in pool 
                            if not conn.is_in_use and conn.is_expired()
                        ]
                        
                        for conn in expired_connections:
                            self._remove_connection(conn)
                        
                        # 如果池为空，删除池
                        if not pool:
                            del self.pools[conn_info]
                
            except Exception as e:
                logger.error(f"清理过期连接时出错: {str(e)}")
    
    def _health_check_loop(self):
        """健康检查的后台线程"""
        while self.is_running:
            try:
                time.sleep(self.config.health_check_interval)
                
                with self.lock:
                    for pool in self.pools.values():
                        for conn in pool[:]:  # 创建副本
                            if not conn.is_in_use and conn.needs_health_check():
                                self.stats['total_health_checks'] += 1
                                if not conn.perform_health_check():
                                    self.stats['failed_health_checks'] += 1
                                    self._remove_connection(conn)
                
            except Exception as e:
                logger.error(f"健康检查时出错: {str(e)}")
    
    def _monitoring_loop(self):
        """监控统计的后台线程"""
        while self.is_running:
            try:
                time.sleep(self.config.pool_stats_log_interval)
                stats = self.get_pool_stats()
                logger.info(f"SSH连接池统计: {stats}")
                
            except Exception as e:
                logger.error(f"连接池监控时出错: {str(e)}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self.lock:
            total_connections = sum(len(pool) for pool in self.pools.values())
            idle_connections = sum(
                len([conn for conn in pool if not conn.is_in_use]) 
                for pool in self.pools.values()
            )
            active_connections = sum(
                len([conn for conn in pool if conn.is_in_use]) 
                for pool in self.pools.values()
            )
            
            return {
                'total_pools': len(self.pools),
                'total_connections': total_connections,
                'active_connections': active_connections,
                'idle_connections': idle_connections,
                'statistics': self.stats.copy(),
                'config': self.config.to_dict()
            }
    
    def close_all(self):
        """关闭所有连接"""
        self.is_running = False
        
        with self.lock:
            for pool in self.pools.values():
                for conn in pool:
                    conn.close()
            self.pools.clear()
        
        logger.info("SSH连接池已关闭所有连接")

class SSHConnectionManager:
    """SSH连接管理器"""
    
    def __init__(self, timeout=None, connect_timeout=None, use_pool=True, 
                 max_connections_per_server=None, max_idle_time=None):
        # 获取配置文件中的默认值
        config = ssh_pool_config_manager.get_config()
        
        self.timeout = timeout if timeout is not None else config.command_timeout
        self.connect_timeout = connect_timeout if connect_timeout is not None else config.connect_timeout
        self.use_pool = use_pool
        
        # 初始化连接池
        if self.use_pool:
            # 使用配置文件中的值作为默认值
            pool_config = SSHPoolConfig(
                max_connections_per_server=max_connections_per_server if max_connections_per_server is not None else config.max_connections_per_server,
                max_idle_time=max_idle_time if max_idle_time is not None else config.max_idle_time,
                cleanup_interval=config.cleanup_interval,
                connect_timeout=self.connect_timeout,
                command_timeout=self.timeout,
                health_check_enabled=config.health_check_enabled,
                health_check_interval=config.health_check_interval,
                health_check_command=config.health_check_command,
                health_check_timeout=config.health_check_timeout,
                max_retries=config.max_retries,
                retry_delay=config.retry_delay,
                enable_pool_monitoring=config.enable_pool_monitoring,
                pool_stats_log_interval=config.pool_stats_log_interval,
                validate_connection_on_borrow=config.validate_connection_on_borrow,
                validate_connection_on_return=config.validate_connection_on_return
            )
            self.connection_pool = SSHConnectionPool(config=pool_config)
            logger.info(f"SSH连接池已初始化，max_idle_time={pool_config.max_idle_time}秒")
        else:
            self.connection_pool = None
    
    def test_connection(self, host: str, port: int, username: str, 
                       password: Optional[str] = None, private_key_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        测试SSH连接，支持重试机制
        
        Args:
            host: 主机地址
            port: 端口
            username: 用户名
            password: 密码
            private_key_path: 私钥文件路径
            
        Returns:
            (is_success, message)
        """
        max_retries = 1  # 最多重试1次
        retry_delay = 3  # 重试间隔3秒
        
        for attempt in range(max_retries + 1):
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # 准备认证参数
                auth_kwargs = {
                    'hostname': host,
                    'port': port,
                    'username': username,
                    'timeout': self.connect_timeout
                }
                
                if private_key_path:
                    try:
                        private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
                        auth_kwargs['pkey'] = private_key
                    except Exception as e:
                        try:
                            private_key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
                            auth_kwargs['pkey'] = private_key
                        except Exception:
                            return False, f"无法加载私钥文件: {str(e)}"
                elif password:
                    auth_kwargs['password'] = password
                else:
                    return False, "必须提供密码或私钥文件"
                
                # 尝试连接
                client.connect(**auth_kwargs)
                
                # 执行简单命令测试
                stdin, stdout, stderr = client.exec_command('echo "connection test"', timeout=5)
                result = stdout.read().decode().strip()
                
                client.close()
                
                if result == "connection test":
                    return True, "连接成功"
                else:
                    return False, "连接测试失败"
                    
            except Exception as e:
                error_str = str(e)
                is_retryable_error = (
                    "远程主机强迫关闭了一个现有的连接" in error_str or
                    "10054" in error_str or
                    "Connection reset by peer" in error_str or
                    "Broken pipe" in error_str or
                    isinstance(e, socket.error)
                )
                
                if attempt < max_retries and is_retryable_error:
                    logger.warning(f"SSH连接测试失败 - {host}:{port} (尝试 {attempt + 1}/{max_retries + 1}): {error_str}，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"SSH连接测试失败 - {host}:{port} (尝试 {attempt + 1}/{max_retries + 1}): {error_str}")
                    
                    if isinstance(e, paramiko.AuthenticationException):
                        return False, "认证失败，请检查用户名和密码/私钥"
                    elif isinstance(e, paramiko.SSHException):
                        return False, f"SSH连接错误: {str(e)}"
                    elif isinstance(e, socket.timeout):
                        return False, "连接超时，请检查网络和主机地址"
                    elif isinstance(e, socket.error):
                        return False, f"网络连接错误: {str(e)}"
                    else:
                        return False, f"连接失败: {str(e)}"
        
        return False, "连接失败"

    @contextmanager
    def get_connection(self, host: str, port: int, username: str,
                      password: Optional[str] = None, private_key_path: Optional[str] = None):
        """
        获取SSH连接的上下文管理器，支持连接池和重试机制
        
        Args:
            host: 主机地址
            port: 端口
            username: 用户名
            password: 密码
            private_key_path: 私钥文件路径
            
        Yields:
            paramiko.SSHClient: SSH客户端连接
        """
        if self.use_pool and self.connection_pool:
            # 使用连接池
            conn_info = ConnectionInfo(
                host=host,
                port=port,
                username=username,
                password=password,
                private_key_path=private_key_path
            )
            
            pooled_conn = None
            try:
                pooled_conn = self.connection_pool.get_connection(conn_info)
                yield pooled_conn.client
            finally:
                if pooled_conn:
                    self.connection_pool.return_connection(pooled_conn)
        else:
            # 传统方式，直接创建连接
            client = None
            max_retries = 1  # 最多重试1次
            retry_delay = 3  # 重试间隔3秒
            
            for attempt in range(max_retries + 1):
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    # 准备认证参数
                    auth_kwargs = {
                        'hostname': host,
                        'port': port,
                        'username': username,
                        'timeout': self.connect_timeout
                    }
                    
                    if private_key_path:
                        try:
                            private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
                            auth_kwargs['pkey'] = private_key
                        except Exception:
                            try:
                                private_key = paramiko.Ed25519Key.from_private_key_file(private_key_path)
                                auth_kwargs['pkey'] = private_key
                            except Exception as e:
                                raise Exception(f"无法加载私钥文件: {str(e)}")
                    elif password:
                        auth_kwargs['password'] = password
                    else:
                        raise Exception("必须提供密码或私钥文件")
                    
                    client.connect(**auth_kwargs)
                    yield client
                    return  # 连接成功，退出重试循环
                    
                except Exception as e:
                    error_str = str(e)
                    is_retryable_error = (
                        "远程主机强迫关闭了一个现有的连接" in error_str or
                        "10054" in error_str or
                        "Connection reset by peer" in error_str or
                        "Broken pipe" in error_str or
                        isinstance(e, socket.error)
                    )
                    
                    if attempt < max_retries and is_retryable_error:
                        logger.warning(f"SSH连接失败 - {host}:{port} (尝试 {attempt + 1}/{max_retries + 1}): {error_str}，{retry_delay}秒后重试...")
                        if client:
                            try:
                                client.close()
                            except:
                                pass
                            client = None
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"SSH连接失败 - {host}:{port} (尝试 {attempt + 1}/{max_retries + 1}): {error_str}")
                        
                        # 提供更详细的错误信息
                        if isinstance(e, paramiko.AuthenticationException):
                            raise Exception("认证失败，请检查用户名和密码/私钥")
                        elif isinstance(e, paramiko.SSHException):
                            raise Exception(f"SSH连接错误: {str(e)}")
                        elif isinstance(e, socket.timeout):
                            raise Exception("连接超时，请检查网络和主机地址")
                        elif isinstance(e, socket.error):
                            raise Exception(f"网络连接错误: {str(e)}")
                        else:
                            raise Exception(f"连接失败: {str(e)}")
                finally:
                    if client and attempt == max_retries:
                        try:
                            client.close()
                        except:
                            pass

    def get_pool_connection(self, host: str, port: int, username: str,
                           password: Optional[str] = None, private_key_path: Optional[str] = None):
        """
        直接从连接池获取连接（不使用上下文管理器）
        
        Returns:
            (PooledSSHConnection, ConnectionInfo): 连接对象和连接信息
        """
        if not self.use_pool or not self.connection_pool:
            raise Exception("连接池未启用")
            
        conn_info = ConnectionInfo(
            host=host,
            port=port,
            username=username,
            password=password,
            private_key_path=private_key_path
        )
        
        pooled_conn = self.connection_pool.get_connection(conn_info)
        return pooled_conn, conn_info
    
    def return_pool_connection(self, pooled_conn):
        """
        归还连接到连接池
        """
        if self.use_pool and self.connection_pool:
            self.connection_pool.return_connection(pooled_conn)
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        """
        if self.use_pool and self.connection_pool:
            return self.connection_pool.get_pool_stats()
        return {'message': '连接池未启用'}
    
    def close_pool(self):
        """
        关闭连接池
        """
        if self.use_pool and self.connection_pool:
            self.connection_pool.close_all()

    def execute_command(self, client: paramiko.SSHClient, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行SSH命令，支持重试机制
        
        Args:
            client: SSH客户端
            command: 要执行的命令
            timeout: 超时时间
            
        Returns:
            包含命令执行结果的字典
        """
        if timeout is None:
            timeout = self.timeout
        
        # 获取重试配置
        config = ssh_pool_config_manager.get_config()
        max_retries = config.max_retries
        retry_delay = config.retry_delay
        
        last_exception = None
        total_start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
                
                # 读取输出
                stdout_data = stdout.read().decode('utf-8', errors='ignore')
                stderr_data = stderr.read().decode('utf-8', errors='ignore')
                exit_code = stdout.channel.recv_exit_status()
                
                execution_time = time.time() - start_time
                
                return {
                    'success': exit_code == 0,
                    'exit_code': exit_code,
                    'stdout': stdout_data,
                    'stderr': stderr_data,
                    'execution_time': execution_time
                }
                
            except socket.timeout as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"命令执行超时 (尝试 {attempt + 1}/{max_retries + 1}): {command[:50]}...，{retry_delay}秒后重试")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"命令执行超时，已达最大重试次数: {command[:50]}...")
                    return {
                        'success': False,
                        'exit_code': -1,
                        'stdout': '',
                        'stderr': '命令执行超时',
                        'execution_time': timeout
                    }
                    
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # 判断是否为可重试的错误
                is_retryable_error = (
                    "远程主机强迫关闭了一个现有的连接" in error_str or
                    "10054" in error_str or
                    "Connection reset by peer" in error_str or
                    "Broken pipe" in error_str or
                    "Socket is closed" in error_str or
                    isinstance(e, socket.error) or
                    isinstance(e, paramiko.SSHException)
                )
                
                if attempt < max_retries and is_retryable_error:
                    logger.warning(f"命令执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {error_str}，{retry_delay}秒后重试")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"命令执行失败，已达最大重试次数: {error_str}")
                    return {
                        'success': False,
                        'exit_code': -1,
                        'stdout': '',
                        'stderr': str(e),
                        'execution_time': time.time() - total_start_time
                    }
        
        # 如果所有重试都失败了
        return {
            'success': False,
            'exit_code': -1,
            'stdout': '',
            'stderr': str(last_exception) if last_exception else '未知错误',
            'execution_time': time.time() - total_start_time
        }
    
    def get_system_info(self, client: paramiko.SSHClient) -> Dict[str, Any]:
        """
        获取系统基本信息
        
        Args:
            client: SSH客户端
            
        Returns:
            系统信息字典
        """
        commands = {
            'hostname': 'hostname',
            'uptime': 'uptime',
            'os_info': 'cat /etc/os-release 2>/dev/null || uname -a',
            'kernel': 'uname -r',
            'architecture': 'uname -m',
            'load_average': 'cat /proc/loadavg',
            'users': 'who | wc -l'
        }
        
        system_info = {}
        
        for key, command in commands.items():
            try:
                result = self.execute_command(client, command, timeout=10)
                if result['success']:
                    system_info[key] = result['stdout'].strip()
                else:
                    system_info[key] = f"获取失败: {result['stderr']}"
            except Exception as e:
                system_info[key] = f"执行错误: {str(e)}"
        
        return system_info
    
    def get_cpu_usage(self, client: paramiko.SSHClient) -> Optional[float]:
        """
        获取CPU使用率
        
        Args:
            client: SSH客户端
            
        Returns:
            CPU使用率百分比
        """
        try:
            # 使用top命令获取CPU使用率
            command = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
            result = self.execute_command(client, command, timeout=10)
            
            if result['success'] and result['stdout'].strip():
                cpu_usage = float(result['stdout'].strip())
                return cpu_usage
            
            # 备用方法：使用vmstat
            command = "vmstat 1 2 | tail -1 | awk '{print 100-$15}'"
            result = self.execute_command(client, command, timeout=15)
            
            if result['success'] and result['stdout'].strip():
                cpu_usage = float(result['stdout'].strip())
                return cpu_usage
            
        except Exception as e:
            logger.error(f"获取CPU使用率失败: {str(e)}")
        
        return None
    
    def get_memory_usage(self, client: paramiko.SSHClient) -> Optional[Dict]:
        """
        获取内存使用情况
        
        Args:
            client: SSH客户端
            
        Returns:
            内存使用情况字典，包含使用率、总内存、使用内存、空闲内存
        """
        try:
            # 使用free命令获取详细内存信息
            command = "free -m | grep Mem | awk '{print $2,$3,$4,$7}'"
            result = self.execute_command(client, command, timeout=10)
            
            if result['success'] and result['stdout'].strip():
                parts = result['stdout'].strip().split()
                if len(parts) >= 4:
                    total_mb = int(parts[0])
                    used_mb = int(parts[1])
                    free_mb = int(parts[2])
                    available_mb = int(parts[3])
                    
                    # 计算使用率（使用已用内存除以总内存）
                    usage_percent = (used_mb / total_mb) * 100.0
                    
                    return {
                        'usage_percent': round(usage_percent, 2),
                        'total_mb': total_mb,
                        'used_mb': used_mb,
                        'free_mb': free_mb,
                        'available_mb': available_mb,
                        'total_gb': round(total_mb / 1024, 2),
                        'used_gb': round(used_mb / 1024, 2),
                        'free_gb': round(free_mb / 1024, 2),
                        'available_gb': round(available_mb / 1024, 2)
                    }
            
            # 备用方法：只获取使用率
            command = "free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'"
            result = self.execute_command(client, command, timeout=10)
            
            if result['success'] and result['stdout'].strip():
                usage_percent = float(result['stdout'].strip())
                return {
                    'usage_percent': usage_percent,
                    'total_mb': None,
                    'used_mb': None,
                    'free_mb': None,
                    'available_mb': None,
                    'total_gb': None,
                    'used_gb': None,
                    'free_gb': None,
                    'available_gb': None
                }
            
        except Exception as e:
            logger.error(f"获取内存使用率失败: {str(e)}")
        
        return None
    
    def get_disk_usage(self, client: paramiko.SSHClient) -> list:
        """
        获取磁盘使用情况
        
        Args:
            client: SSH客户端
            
        Returns:
            磁盘使用情况列表
        """
        disk_info = []
        
        try:
            # 使用df -h获取磁盘使用情况
            command = "df -h | grep -E '^/dev/'"
            result = self.execute_command(client, command, timeout=10)
            
            if result['success']:
                lines = result['stdout'].strip().split('\n')
                
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            filesystem = parts[0]
                            size = parts[1]
                            used = parts[2]
                            available = parts[3]
                            use_percent = parts[4].rstrip('%')
                            mounted_on = parts[5]
                            
                            try:
                                use_percent_float = float(use_percent)
                            except ValueError:
                                use_percent_float = 0.0
                            
                            disk_info.append({
                                'filesystem': filesystem,
                                'size': size,
                                'used': used,
                                'available': available,
                                'use_percent': use_percent_float,
                                'mounted_on': mounted_on
                            })
            
        except Exception as e:
            logger.error(f"获取磁盘使用情况失败: {str(e)}")
        
        return disk_info