import paramiko
import socket
import logging
import time
from typing import Dict, Any, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class SSHConnectionManager:
    """SSH连接管理器"""
    
    def __init__(self, timeout=30, connect_timeout=10):
        self.timeout = timeout
        self.connect_timeout = connect_timeout
    
    def test_connection(self, host: str, port: int, username: str, 
                       password: Optional[str] = None, private_key_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        测试SSH连接
        
        Args:
            host: 主机地址
            port: 端口
            username: 用户名
            password: 密码
            private_key_path: 私钥文件路径
            
        Returns:
            (is_success, message)
        """
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
                
        except paramiko.AuthenticationException:
            return False, "认证失败，请检查用户名和密码/私钥"
        except paramiko.SSHException as e:
            return False, f"SSH连接错误: {str(e)}"
        except socket.timeout:
            return False, "连接超时，请检查网络和主机地址"
        except socket.error as e:
            return False, f"网络连接错误: {str(e)}"
        except Exception as e:
            logger.error(f"SSH连接测试异常: {str(e)}")
            return False, f"连接失败: {str(e)}"
    
    @contextmanager
    def get_connection(self, host: str, port: int, username: str,
                      password: Optional[str] = None, private_key_path: Optional[str] = None):
        """
        获取SSH连接的上下文管理器
        
        Args:
            host: 主机地址
            port: 端口
            username: 用户名
            password: 密码
            private_key_path: 私钥文件路径
            
        Yields:
            paramiko.SSHClient: SSH客户端连接
        """
        client = None
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
            
        except Exception as e:
            logger.error(f"SSH连接失败 - {host}:{port}: {str(e)}")
            
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
            if client:
                client.close()
    
    def execute_command(self, client: paramiko.SSHClient, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        执行SSH命令
        
        Args:
            client: SSH客户端
            command: 要执行的命令
            timeout: 超时时间
            
        Returns:
            包含命令执行结果的字典
        """
        if timeout is None:
            timeout = self.timeout
            
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
            
        except socket.timeout:
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': '命令执行超时',
                'execution_time': timeout
            }
        except Exception as e:
            logger.error(f"命令执行失败: {str(e)}")
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'execution_time': 0
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
    
    def get_memory_usage(self, client: paramiko.SSHClient) -> Optional[float]:
        """
        获取内存使用率
        
        Args:
            client: SSH客户端
            
        Returns:
            内存使用率百分比
        """
        try:
            command = "free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'"
            result = self.execute_command(client, command, timeout=10)
            
            if result['success'] and result['stdout'].strip():
                memory_usage = float(result['stdout'].strip())
                return memory_usage
            
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