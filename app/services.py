from typing import List, Dict, Any, Optional, Tuple
from app.models import db, Server, Threshold, ScheduleTask, MonitorLog
from app.ssh_manager import SSHConnectionManager
from cryptography.fernet import Fernet
import base64
import logging

logger = logging.getLogger(__name__)

class ServerService:
    """服务器管理服务"""
    
    def __init__(self):
        # 使用HostMonitor的全局共享SSH连接管理器
        from app.monitor import HostMonitor
        if HostMonitor._shared_ssh_manager is None:
            HostMonitor._shared_ssh_manager = SSHConnectionManager()
            logger.info("创建全局SSH连接管理器，连接池已启用")
        self.ssh_manager = HostMonitor._shared_ssh_manager
        # 从配置文件获取加密密钥
        self.cipher_key = self._get_cipher_key()
    
    def _get_cipher_key(self) -> bytes:
        """从配置获取加密密钥"""
        try:
            from flask import current_app
            # 尝试从Flask配置获取密钥
            if current_app:
                encryption_key = current_app.config.get('ENCRYPTION_KEY')
                if encryption_key:
                    # Fernet密钥必须是base64编码的44字符字符串
                    import base64
                    try:
                        # 验证是否为有效的base64编码
                        decoded_key = base64.b64decode(encryption_key)
                        # 验证解码后的长度是否为32字节（Fernet要求）
                        if len(decoded_key) == 32:
                            # 返回原始的base64编码字符串，不是解码后的bytes
                            return encryption_key.encode()
                        else:
                            logger.warning(f"ENCRYPTION_KEY解码后长度不正确: {len(decoded_key)}字节，应为32字节")
                            return Fernet.generate_key()
                    except Exception as e:
                        logger.warning(f"ENCRYPTION_KEY不是有效的base64编码: {str(e)}")
                        return Fernet.generate_key()
        except:
            pass
        
        # 备用方案：从环境变量获取
        import os
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if encryption_key:
            import base64
            try:
                decoded_key = base64.b64decode(encryption_key)
                if len(decoded_key) == 32:
                    # 返回原始的base64编码字符串，不是解码后的bytes
                    return encryption_key.encode()
                else:
                    logger.warning(f"环境变量ENCRYPTION_KEY解码后长度不正确: {len(decoded_key)}字节，应为32字节")
            except Exception as e:
                logger.warning(f"环境变量ENCRYPTION_KEY不是有效的base64编码: {str(e)}")
        
        # 最后备用方案：生成新密钥
        logger.warning("未找到有效的加密密钥，生成新密钥")
        return Fernet.generate_key()
    
    def _encrypt_password(self, password: str) -> str:
        """加密密码"""
        if not password:
            return ""
        try:
            f = Fernet(self.cipher_key)
            encrypted = f.encrypt(password.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"密码加密失败: {str(e)}")
            return password
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """解密密码"""
        if not encrypted_password:
            return ""
        try:
            f = Fernet(self.cipher_key)
            encrypted_data = base64.b64decode(encrypted_password.encode())
            decrypted = f.decrypt(encrypted_data)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"密码解密失败: {str(e)}")
            return encrypted_password
    
    def create_server(self, server_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Server]]:
        """
        创建服务器
        
        Args:
            server_data: 服务器信息字典
            
        Returns:
            (success, message, server)
        """
        try:
            # 验证必填字段
            required_fields = ['name', 'host', 'username']
            for field in required_fields:
                if not server_data.get(field):
                    return False, f"字段 {field} 不能为空", None
            
            # 检查服务器名称是否已存在
            existing_server = Server.query.filter_by(name=server_data['name']).first()
            if existing_server:
                return False, "服务器名称已存在", None
            
            # 检查主机地址是否已存在
            existing_host = Server.query.filter_by(
                host=server_data['host'], 
                port=server_data.get('port', 22)
            ).first()
            if existing_host:
                return False, "主机地址和端口组合已存在", None
            
            # 加密密码
            encrypted_password = ""
            if server_data.get('password'):
                encrypted_password = self._encrypt_password(server_data['password'])
            
            # 创建服务器对象
            server = Server(
                name=server_data['name'],
                host=server_data['host'],
                port=server_data.get('port', 22),
                username=server_data['username'],
                password=encrypted_password,
                private_key_path=server_data.get('private_key_path', ''),
                description=server_data.get('description', ''),
                status=server_data.get('status', 'active')
            )
            
            db.session.add(server)
            db.session.commit()
            
            logger.info(f"服务器创建成功: {server.name}")
            return True, "服务器创建成功", server
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建服务器失败: {str(e)}")
            return False, f"创建服务器失败: {str(e)}", None
    
    def get_server_list(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        获取服务器列表
        
        Args:
            page: 页码
            per_page: 每页数量
            
        Returns:
            分页的服务器列表
        """
        try:
            pagination = Server.query.paginate(
                page=page, 
                per_page=per_page, 
                error_out=False
            )
            
            servers = []
            for server in pagination.items:
                server_dict = server.to_dict()
                # 不返回敏感信息
                server_dict.pop('password', None)
                servers.append(server_dict)
            
            return {
                'servers': servers,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': page,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
            
        except Exception as e:
            logger.error(f"获取服务器列表失败: {str(e)}")
            return {
                'servers': [],
                'total': 0,
                'pages': 0,
                'current_page': page,
                'has_prev': False,
                'has_next': False
            }
    
    def get_server_by_id(self, server_id: int) -> Optional[Server]:
        """
        根据ID获取服务器
        
        Args:
            server_id: 服务器ID
            
        Returns:
            服务器对象或None
        """
        try:
            return Server.query.get(server_id)
        except Exception as e:
            logger.error(f"获取服务器失败: {str(e)}")
            return None
    
    def update_server(self, server_id: int, server_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Server]]:
        """
        更新服务器信息
        
        Args:
            server_id: 服务器ID
            server_data: 更新的服务器信息
            
        Returns:
            (success, message, server)
        """
        try:
            server = Server.query.get(server_id)
            if not server:
                return False, "服务器不存在", None
            
            # 检查服务器名称是否与其他服务器冲突
            if 'name' in server_data and server_data['name'] != server.name:
                existing_server = Server.query.filter_by(name=server_data['name']).first()
                if existing_server:
                    return False, "服务器名称已存在", None
            
            # 检查主机地址是否与其他服务器冲突
            if 'host' in server_data or 'port' in server_data:
                new_host = server_data.get('host', server.host)
                new_port = server_data.get('port', server.port)
                
                existing_host = Server.query.filter(
                    Server.host == new_host,
                    Server.port == new_port,
                    Server.id != server_id
                ).first()
                
                if existing_host:
                    return False, "主机地址和端口组合已存在", None
            
            # 更新字段
            if 'name' in server_data:
                server.name = server_data['name']
            if 'host' in server_data:
                server.host = server_data['host']
            if 'port' in server_data:
                server.port = server_data['port']
            if 'username' in server_data:
                server.username = server_data['username']
            if 'password' in server_data:
                server.password = self._encrypt_password(server_data['password'])
            if 'private_key_path' in server_data:
                server.private_key_path = server_data['private_key_path']
            if 'description' in server_data:
                server.description = server_data['description']
            if 'status' in server_data:
                server.status = server_data['status']
            
            db.session.commit()
            
            logger.info(f"服务器更新成功: {server.name}")
            return True, "服务器更新成功", server
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新服务器失败: {str(e)}")
            return False, f"更新服务器失败: {str(e)}", None
    
    def delete_server(self, server_id: int) -> Tuple[bool, str]:
        """
        删除服务器
        
        Args:
            server_id: 服务器ID
            
        Returns:
            (success, message)
        """
        try:
            server = Server.query.get(server_id)
            if not server:
                return False, "服务器不存在"
            
            server_name = server.name
            
            # 手动删除相关的服务配置（确保级联删除生效）
            from app.models import ServiceConfig
            service_configs = ServiceConfig.query.filter_by(server_id=server_id).all()
            
            if service_configs:
                logger.info(f"开始删除服务器 {server_name} 的 {len(service_configs)} 个服务配置")
                for config in service_configs:
                    logger.info(f"删除服务配置: {config.service_name} (ID: {config.id})")
                    db.session.delete(config)
            
            # 删除服务器（监控日志会通过级联删除自动处理）
            db.session.delete(server)
            db.session.commit()
            
            logger.info(f"服务器删除成功: {server_name}")
            return True, "服务器删除成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除服务器失败: {str(e)}")
            return False, f"删除服务器失败: {str(e)}"
    
    def bulk_delete_servers(self, server_ids: List[int]) -> Tuple[bool, str, Dict]:
        """
        批量删除服务器
        
        Args:
            server_ids: 服务器ID列表
            
        Returns:
            (success, message, result_dict)
        """
        try:
            if not server_ids:
                return False, "请选择要删除的服务器", {}
            
            # 验证所有ID都是整数
            try:
                server_ids = [int(server_id) for server_id in server_ids]
            except (ValueError, TypeError):
                return False, "无效的服务器ID", {}
            
            # 查找存在的服务器
            servers = Server.query.filter(Server.id.in_(server_ids)).all()
            
            if not servers:
                return False, "找不到指定的服务器", {}
            
            deleted_count = len(servers)
            deleted_servers = []
            deleted_services_count = 0
            
            # 批量删除
            from app.models import ServiceConfig
            for server in servers:
                server_info = {
                    'id': server.id,
                    'name': server.name,
                    'host': server.host
                }
                deleted_servers.append(server_info)
                
                # 手动删除相关的服务配置
                service_configs = ServiceConfig.query.filter_by(server_id=server.id).all()
                
                if service_configs:
                    logger.info(f"删除服务器 {server.name} 的 {len(service_configs)} 个服务配置")
                    for config in service_configs:
                        logger.info(f"删除服务配置: {config.service_name} (ID: {config.id})")
                        db.session.delete(config)
                        deleted_services_count += 1
                
                # 删除服务器（监控日志会通过级联删除自动处理）
                logger.info(f"删除服务器: {server.name} (ID: {server.id})")
                db.session.delete(server)
            
            db.session.commit()
            
            result = {
                'deleted_count': deleted_count,
                'deleted_servers': deleted_servers,
                'deleted_services_count': deleted_services_count
            }
            
            logger.info(f"批量删除服务器成功: {deleted_count}个服务器, {deleted_services_count}个服务配置")
            
            return True, f"成功删除 {deleted_count} 个服务器及 {deleted_services_count} 个相关服务配置", result
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量删除服务器失败: {str(e)}")
            return False, f"批量删除服务器失败: {str(e)}", {}
    
    def test_server_connection(self, server_id: int) -> Tuple[bool, str]:
        """
        测试服务器连接
        
        Args:
            server_id: 服务器ID
            
        Returns:
            (success, message)
        """
        try:
            server = Server.query.get(server_id)
            if not server:
                return False, "服务器不存在"
            
            # 解密密码
            password = self._decrypt_password(server.password) if server.password else None
            
            # 测试连接
            success, message = self.ssh_manager.test_connection(
                host=server.host,
                port=server.port,
                username=server.username,
                password=password,
                private_key_path=server.private_key_path if server.private_key_path else None
            )
            
            return success, message
            
        except Exception as e:
            logger.error(f"测试服务器连接失败: {str(e)}")
            return False, f"测试连接失败: {str(e)}"
    
    def test_connection(self, server_id: int) -> Tuple[bool, str, float]:
        """
        测试服务器连接并返回响应时间
        
        Args:
            server_id: 服务器ID
            
        Returns:
            (success, message, response_time)
        """
        import time
        
        try:
            server = Server.query.get(server_id)
            if not server:
                return False, "服务器不存在", 0.0
            
            # 解密密码
            password = self._decrypt_password(server.password) if server.password else None
            
            # 记录开始时间
            start_time = time.time()
            
            # 测试连接
            success, message = self.ssh_manager.test_connection(
                host=server.host,
                port=server.port,
                username=server.username,
                password=password,
                private_key_path=server.private_key_path if server.private_key_path else None
            )
            
            # 计算响应时间
            response_time = time.time() - start_time
            
            return success, message, response_time
            
        except Exception as e:
            logger.error(f"测试服务器连接失败: {str(e)}")
            return False, f"测试连接失败: {str(e)}", 0.0
    
    def get_active_servers(self) -> List[Server]:
        """
        获取所有激活的服务器
        
        Returns:
            活跃服务器列表
        """
        try:
            return Server.query.filter_by(status='active').all()
        except Exception as e:
            logger.error(f"获取活跃服务器失败: {str(e)}")
            return []

class ThresholdService:
    """阈值管理服务"""
    
    def get_threshold_config(self) -> Dict[str, float]:
        """
        获取阈值配置
        
        Returns:
            阈值配置字典
        """
        try:
            threshold = Threshold.query.first()
            if threshold:
                return {
                    'cpu_threshold': threshold.cpu_threshold,
                    'memory_threshold': threshold.memory_threshold,
                    'disk_threshold': threshold.disk_threshold
                }
            else:
                # 返回默认阈值
                from config import Config
                return {
                    'cpu_threshold': Config.DEFAULT_CPU_THRESHOLD,
                    'memory_threshold': Config.DEFAULT_MEMORY_THRESHOLD,
                    'disk_threshold': Config.DEFAULT_DISK_THRESHOLD
                }
        except Exception as e:
            logger.error(f"获取阈值配置失败: {str(e)}")
            # 返回默认值
            return {
                'cpu_threshold': 80.0,
                'memory_threshold': 80.0,
                'disk_threshold': 80.0
            }
    
    def update_threshold_config(self, threshold_data: Dict[str, float]) -> Tuple[bool, str]:
        """
        更新阈值配置
        
        Args:
            threshold_data: 阈值配置数据
            
        Returns:
            (success, message)
        """
        try:
            threshold = Threshold.query.first()
            
            if threshold:
                # 更新现有配置
                if 'cpu_threshold' in threshold_data:
                    threshold.cpu_threshold = threshold_data['cpu_threshold']
                if 'memory_threshold' in threshold_data:
                    threshold.memory_threshold = threshold_data['memory_threshold']
                if 'disk_threshold' in threshold_data:
                    threshold.disk_threshold = threshold_data['disk_threshold']
            else:
                # 创建新配置
                threshold = Threshold(
                    cpu_threshold=threshold_data.get('cpu_threshold', 80.0),
                    memory_threshold=threshold_data.get('memory_threshold', 80.0),
                    disk_threshold=threshold_data.get('disk_threshold', 80.0)
                )
                db.session.add(threshold)
            
            db.session.commit()
            
            logger.info("阈值配置更新成功")
            return True, "阈值配置更新成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新阈值配置失败: {str(e)}")
            return False, f"更新阈值配置失败: {str(e)}"