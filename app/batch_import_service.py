"""
批量导入服务
处理服务器和服务配置的批量导入功能
"""

import pandas as pd
import os
import logging
from typing import List, Dict, Any, Tuple
from flask import current_app
from app.models import db, Server, ServiceConfig
from app.services import ServerService

logger = logging.getLogger(__name__)

class BatchImportService:
    """批量导入服务"""
    
    def __init__(self):
        self.server_service = ServerService()
    
    def create_server_template(self, template_path: str) -> bool:
        """
        创建服务器导入模板Excel文件
        
        Args:
            template_path: 模板文件保存路径
            
        Returns:
            是否创建成功
        """
        try:
            # 创建服务器模板数据
            server_template_data = {
                '服务器名称': ['Web服务器01', 'DB服务器01'],
                '主机地址': ['192.168.1.100', '192.168.1.101'],
                'SSH端口': [22, 22],
                '用户名': ['root', 'admin'],
                '密码': ['password123', 'admin123'],
                '私钥路径': ['', ''],
                '描述': ['Web应用服务器', '数据库服务器'],
                '状态': ['active', 'active']
            }
            
            # 创建DataFrame
            df = pd.DataFrame(server_template_data)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(template_path), exist_ok=True)
            
            # 保存Excel文件
            with pd.ExcelWriter(template_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='服务器列表', index=False)
                
                # 获取工作表
                worksheet = writer.sheets['服务器列表']
                
                # 设置列宽
                column_widths = {
                    'A': 15,  # 服务器名称
                    'B': 20,  # 主机地址
                    'C': 10,  # SSH端口
                    'D': 12,  # 用户名
                    'E': 15,  # 密码
                    'F': 25,  # 私钥路径
                    'G': 30,  # 描述
                    'H': 10   # 状态
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
            
            logger.info(f"服务器导入模板创建成功: {template_path}")
            return True
            
        except Exception as e:
            logger.error(f"创建服务器模板失败: {str(e)}")
            return False
    
    def create_service_template(self, template_path: str) -> bool:
        """
        创建服务配置导入模板Excel文件
        
        Args:
            template_path: 模板文件保存路径
            
        Returns:
            是否创建成功
        """
        try:
            # 创建服务配置模板数据
            service_template_data = {
                '服务器名称': ['Web服务器01', 'Web服务器01', 'DB服务器01'],
                '服务名称': ['Nginx服务', 'PHP-FPM服务', 'MySQL服务'],
                '进程名称': ['nginx', 'php-fpm', 'mysqld'],
                '是否监控': [True, True, True],
                '服务描述': ['Web服务器', 'PHP处理服务', '数据库服务']
            }
            
            # 创建DataFrame
            df = pd.DataFrame(service_template_data)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(template_path), exist_ok=True)
            
            # 保存Excel文件
            with pd.ExcelWriter(template_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='服务配置列表', index=False)
                
                # 获取工作表
                worksheet = writer.sheets['服务配置列表']
                
                # 设置列宽
                column_widths = {
                    'A': 15,  # 服务器名称
                    'B': 20,  # 服务名称
                    'C': 15,  # 进程名称
                    'D': 12,  # 是否监控
                    'E': 30   # 服务描述
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
            
            logger.info(f"服务配置导入模板创建成功: {template_path}")
            return True
            
        except Exception as e:
            logger.error(f"创建服务配置模板失败: {str(e)}")
            return False
    
    def parse_server_excel(self, file_path: str) -> Tuple[bool, str, List[Dict]]:
        """
        解析服务器Excel文件
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            (success, message, server_list)
        """
        try:
            # 读取Excel文件
            df = pd.read_excel(file_path, sheet_name=0)
            
            # 检查必需的列
            required_columns = ['服务器名称', '主机地址', '用户名']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return False, f"Excel文件缺少必需的列: {', '.join(missing_columns)}", []
            
            # 解析服务器数据
            servers = []
            for index, row in df.iterrows():
                try:
                    # 处理pandas的NaN值，将其转换为空字符串
                    def safe_str(value):
                        """安全地将值转换为字符串，处理NaN值"""
                        if pd.isna(value) or value is None:
                            return ''
                        return str(value).strip()
                    
                    server_data = {
                        'name': safe_str(row['服务器名称']),
                        'host': safe_str(row['主机地址']),
                        'port': int(row.get('SSH端口', 22)) if pd.notna(row.get('SSH端口', 22)) else 22,
                        'username': safe_str(row['用户名']),
                        'password': safe_str(row.get('密码', '')),
                        'private_key_path': safe_str(row.get('私钥路径', '')),
                        'description': safe_str(row.get('描述', '')),
                        'status': safe_str(row.get('状态', 'active')) or 'active'
                    }
                    
                    # 验证必填字段
                    if not server_data['name'] or not server_data['host'] or not server_data['username']:
                        logger.warning(f"第{index+2}行数据不完整，跳过")
                        continue
                    
                    servers.append(server_data)
                    
                except Exception as e:
                    logger.warning(f"解析第{index+2}行数据失败: {str(e)}")
                    continue
            
            if not servers:
                return False, "未找到有效的服务器数据", []
            
            return True, f"成功解析 {len(servers)} 条服务器数据", servers
            
        except Exception as e:
            logger.error(f"解析服务器Excel文件失败: {str(e)}")
            return False, f"解析Excel文件失败: {str(e)}", []
    
    def parse_service_excel(self, file_path: str) -> Tuple[bool, str, List[Dict]]:
        """
        解析服务配置Excel文件
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            (success, message, service_list)
        """
        try:
            # 读取Excel文件
            df = pd.read_excel(file_path, sheet_name=0)
            
            # 检查必需的列
            required_columns = ['服务器名称', '服务名称', '进程名称']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return False, f"Excel文件缺少必需的列: {', '.join(missing_columns)}", []
            
            # 解析服务数据
            services = []
            for index, row in df.iterrows():
                try:
                    # 处理pandas的NaN值，将其转换为空字符串
                    def safe_str(value):
                        """安全地将值转换为字符串，处理NaN值"""
                        if pd.isna(value) or value is None:
                            return ''
                        return str(value).strip()
                    
                    service_data = {
                        'server_name': safe_str(row['服务器名称']),
                        'service_name': safe_str(row['服务名称']),
                        'process_name': safe_str(row['进程名称']),
                        'is_monitoring': bool(row.get('是否监控', True)) if pd.notna(row.get('是否监控')) else True,
                        'description': safe_str(row.get('服务描述', ''))
                    }
                    
                    # 验证必填字段
                    if not service_data['server_name'] or not service_data['service_name'] or not service_data['process_name']:
                        logger.warning(f"第{index+2}行数据不完整，跳过")
                        continue
                    
                    services.append(service_data)
                    
                except Exception as e:
                    logger.warning(f"解析第{index+2}行数据失败: {str(e)}")
                    continue
            
            if not services:
                return False, "未找到有效的服务配置数据", []
            
            return True, f"成功解析 {len(services)} 条服务配置数据", services
            
        except Exception as e:
            logger.error(f"解析服务配置Excel文件失败: {str(e)}")
            return False, f"解析Excel文件失败: {str(e)}", []
    
    def import_servers(self, servers: List[Dict]) -> Tuple[bool, str, Dict]:
        """
        批量导入服务器
        
        Args:
            servers: 服务器数据列表
            
        Returns:
            (success, message, import_result)
        """
        try:
            success_count = 0
            failed_count = 0
            failed_items = []
            
            for server_data in servers:
                success, message, server = self.server_service.create_server(server_data)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_items.append({
                        'name': server_data.get('name', ''),
                        'error': message
                    })
            
            # 准备结果
            result = {
                'total': len(servers),
                'success': success_count,
                'failed': failed_count,
                'failed_items': failed_items
            }
            
            if success_count > 0:
                return True, f"成功导入 {success_count} 个服务器，失败 {failed_count} 个", result
            else:
                return False, f"导入失败，共 {failed_count} 个服务器导入失败", result
            
        except Exception as e:
            logger.error(f"批量导入服务器失败: {str(e)}")
            return False, f"批量导入服务器失败: {str(e)}", {}
    
    def import_services(self, services: List[Dict]) -> Tuple[bool, str, Dict]:
        """
        批量导入服务配置
        
        Args:
            services: 服务配置数据列表
            
        Returns:
            (success, message, import_result)
        """
        try:
            success_count = 0
            failed_count = 0
            failed_items = []
            
            for service_data in services:
                try:
                    # 根据服务器名称查找服务器
                    server = Server.query.filter_by(name=service_data['server_name']).first()
                    if not server:
                        failed_count += 1
                        failed_items.append({
                            'name': service_data.get('service_name', ''),
                            'error': f"服务器 '{service_data['server_name']}' 不存在"
                        })
                        continue
                    
                    # 检查服务配置是否已存在
                    existing_service = ServiceConfig.query.filter_by(
                        server_id=server.id,
                        service_name=service_data['service_name']
                    ).first()
                    
                    if existing_service:
                        failed_count += 1
                        failed_items.append({
                            'name': service_data.get('service_name', ''),
                            'error': f"服务配置已存在"
                        })
                        continue
                    
                    # 创建服务配置
                    service_config = ServiceConfig(
                        server_id=server.id,
                        service_name=service_data['service_name'],
                        process_name=service_data['process_name'],
                        is_monitoring=service_data['is_monitoring'],
                        description=service_data['description']
                    )
                    
                    db.session.add(service_config)
                    success_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    failed_items.append({
                        'name': service_data.get('service_name', ''),
                        'error': str(e)
                    })
            
            # 提交所有成功的数据
            if success_count > 0:
                db.session.commit()
            
            # 准备结果
            result = {
                'total': len(services),
                'success': success_count,
                'failed': failed_count,
                'failed_items': failed_items
            }
            
            if success_count > 0:
                return True, f"成功导入 {success_count} 个服务配置，失败 {failed_count} 个", result
            else:
                return False, f"导入失败，共 {failed_count} 个服务配置导入失败", result
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量导入服务配置失败: {str(e)}")
            return False, f"批量导入服务配置失败: {str(e)}", {}
    
    def test_server_connections(self, server_ids: List[int]) -> Dict[int, Dict]:
        """
        批量测试服务器连接
        
        Args:
            server_ids: 服务器ID列表
            
        Returns:
            测试结果字典 {server_id: {'success': bool, 'message': str, 'response_time': float, 'server_name': str, 'server_host': str}}
        """
        try:
            results = {}
            
            for server_id in server_ids:
                try:
                    server = Server.query.get(server_id)
                    if not server:
                        results[server_id] = {
                            'success': False,
                            'message': '服务器不存在',
                            'response_time': 0,
                            'server_name': f'服务器{server_id}',
                            'server_host': 'N/A'
                        }
                        continue
                    
                    # 测试SSH连接
                    success, message, response_time = self.server_service.test_connection(server_id)
                    results[server_id] = {
                        'success': success,
                        'message': message,
                        'response_time': response_time,
                        'server_name': server.name,
                        'server_host': f'{server.host}:{server.port}'
                    }
                    
                except Exception as e:
                    results[server_id] = {
                        'success': False,
                        'message': str(e),
                        'response_time': 0,
                        'server_name': f'服务器{server_id}',
                        'server_host': 'N/A'
                    }
            
            return results
            
        except Exception as e:
            logger.error(f"批量测试服务器连接失败: {str(e)}")
            return {}