"""
通知服务模块
负责webhook通知的发送和管理
"""

import json
import requests
from datetime import datetime
from app.models import db, NotificationChannel
import logging
from app.oss_service import OSSService

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务类"""
    
    def __init__(self):
        self.default_timeout = 30
        # 初始化OSS服务
        self.oss_service = OSSService()
    
    def create_channel(self, data):
        """创建通知通道"""
        try:
            channel = NotificationChannel(
                name=data['name'],
                webhook_url=data['webhook_url'],
                method=data.get('method', 'POST'),
                # content_template字段已移除，直接在请求体模板中使用变量
                timeout=data.get('timeout', self.default_timeout),
                is_enabled=data.get('is_enabled', True),
                # OSS配置字段
                oss_enabled=data.get('oss_enabled', False),
                oss_endpoint=data.get('oss_endpoint', ''),
                oss_access_key_id=data.get('oss_access_key_id', ''),
                oss_access_key_secret=data.get('oss_access_key_secret', ''),
                oss_bucket_name=data.get('oss_bucket_name', ''),
                oss_folder_path=data.get('oss_folder_path', '')
            )
            
            # 设置请求体模板
            if 'request_body' in data:
                channel.set_request_body_template(data['request_body'])
            
            db.session.add(channel)
            db.session.commit()
            
            logger.info(f"通知通道创建成功: {channel.name}")
            return True, "通知通道创建成功", channel
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建通知通道失败: {str(e)}")
            return False, f"创建通知通道失败: {str(e)}", None
    
    def update_channel(self, channel_id, data):
        """更新通知通道"""
        try:
            channel = NotificationChannel.query.get(channel_id)
            if not channel:
                return False, "通知通道不存在", None
            
            # 更新字段
            if 'name' in data:
                channel.name = data['name']
            if 'webhook_url' in data:
                channel.webhook_url = data['webhook_url']
            if 'method' in data:
                channel.method = data.get('method', 'POST')
            # content_template字段已移除，直接在请求体模板中使用变量
            if 'is_enabled' in data:
                channel.is_enabled = data.get('is_enabled', True)
            if 'timeout' in data:
                channel.timeout = data.get('timeout', self.default_timeout)
            if 'request_body' in data:
                channel.set_request_body_template(data['request_body'])
            
            from datetime import datetime
            channel.updated_at = datetime.now()
            db.session.commit()
            
            logger.info(f"通知通道更新成功: {channel.name}")
            return True, "通知通道更新成功", channel
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新通知通道失败: {str(e)}")
            return False, f"更新通知通道失败: {str(e)}", None
    
    def delete_channel(self, channel_id):
        """删除通知通道"""
        try:
            channel = NotificationChannel.query.get(channel_id)
            if not channel:
                return False, "通知通道不存在"
            
            channel_name = channel.name
            db.session.delete(channel)
            db.session.commit()
            
            logger.info(f"通知通道删除成功: {channel_name}")
            return True, "通知通道删除成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除通知通道失败: {str(e)}")
            return False, f"删除通知通道失败: {str(e)}"
    
    def get_all_channels(self):
        """获取所有通知通道"""
        try:
            channels = NotificationChannel.query.order_by(NotificationChannel.created_at.desc()).all()
            return [channel.to_dict() for channel in channels]
        except Exception as e:
            logger.error(f"获取通知通道列表失败: {str(e)}")
            return []
    
    def send_notification(self, monitor_result, report_file_path=None):
        """发送巡视报告通知"""
        try:
            # 获取所有启用的通知通道
            channels = NotificationChannel.query.filter_by(is_enabled=True).all()
            
            if not channels:
                logger.info("没有启用的通知通道")
                return True, "没有启用的通知通道"
            
            # 生成通知内容
            content = self._generate_notification_content(monitor_result)
            
            success_count = 0
            for channel in channels:
                try:
                    # 处理OSS上传和URL变量
                    download_url = None
                    logger.info(f"通道 {channel.name}: OSS启用状态={channel.oss_enabled}, 报告文件路径={report_file_path}")
                    
                    if channel.oss_enabled and report_file_path:
                        logger.info(f"开始上传报告到OSS - 通道: {channel.name}")
                        download_url = self._upload_to_oss_and_get_url(channel, report_file_path)
                        if not download_url:
                            download_url = '报告上传失败，请检查OSS配置'
                            logger.error(f"OSS上传失败 - 通道: {channel.name}")
                        else:
                            logger.info(f"OSS上传成功 - 通道: {channel.name}, URL: {download_url}")
                    else:
                        if not channel.oss_enabled:
                            logger.info(f"通道 {channel.name} 未启用OSS")
                        if not report_file_path:
                            logger.info(f"通道 {channel.name} 没有报告文件路径")
                        download_url = '未配置OSS存储，无法提供下载链接'
                    
                    # 不在这里替换#url#变量，让_send_to_channel方法统一处理
                    if self._send_to_channel(channel, content, download_url):
                        success_count += 1
                except Exception as e:
                    logger.error(f"发送通知失败 - 通道: {channel.name}, 错误: {str(e)}")
            
            message = f"通知发送完成，成功 {success_count}/{len(channels)} 个通道"
            logger.info(message)
            return True, message
            
        except Exception as e:
            logger.error(f"发送通知失败: {str(e)}")
            return False, f"发送通知失败: {str(e)}"
    
    def _upload_to_oss_and_get_url(self, channel, report_file_path):
        """上传报告到OSS并获取下载链接"""
        try:
            # 配置OSS服务
            if not self.oss_service.configure(
                endpoint=channel.oss_endpoint,
                access_key_id=channel.oss_access_key_id,
                access_key_secret=channel.oss_access_key_secret,
                bucket_name=channel.oss_bucket_name,
                folder_path=channel.oss_folder_path or "reports"
            ):
                logger.error(f"OSS配置失败 - 通道: {channel.name}")
                return None
            
            # 生成远程文件名（包含时间戳）
            import os
            from datetime import datetime
            file_name = os.path.basename(report_file_path)
            name, ext = os.path.splitext(file_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            remote_file_name = f"{name}_{timestamp}{ext}"
            
            # 上传文件并获取下载链接
            success, message, download_url = self.oss_service.upload_and_get_url(
                local_file_path=report_file_path,
                remote_file_name=remote_file_name,
                expires_in_hours=24  # 链接有效期24小时
            )
            
            if success:
                logger.info(f"OSS上传成功 - 通道: {channel.name}, URL: {download_url}")
                return download_url
            else:
                logger.error(f"OSS上传失败 - 通道: {channel.name}, 错误: {message}")
                return None
                
        except Exception as e:
            logger.error(f"OSS上传异常 - 通道: {channel.name}, 错误: {str(e)}")
            return None
    
    def _simplify_error_message(self, error_msg):
        """简化错误信息，提供用户友好的错误描述"""
        if not error_msg:
            return "ssh连接失败，请检查！"
        
        error_msg_lower = error_msg.lower()
        
        # 常见错误模式匹配
        if "working outside of application context" in error_msg:
            return "ssh连接失败，请检查！"
        elif "认证失败" in error_msg or "authentication" in error_msg_lower:
            return "认证失败，请检查用户名和密码！"
        elif "连接超时" in error_msg or "timeout" in error_msg_lower:
            return "连接超时，请检查网络！"
        elif "网络连接" in error_msg or "network" in error_msg_lower or "connection" in error_msg_lower:
            return "网络连接失败，请检查！"
        elif "ssh" in error_msg_lower:
            return "ssh连接失败，请检查！"
        elif "无法加载私钥" in error_msg or "private key" in error_msg_lower:
            return "私钥文件错误，请检查！"
        else:
            # 如果错误信息太长，截取前面部分
            if len(error_msg) > 50:
                return "ssh连接失败，请检查！"
            else:
                return error_msg
    
    def _generate_notification_content(self, monitor_result):
        """生成通知内容"""
        try:
            # 基本信息
            monitor_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            total_servers = monitor_result.get('total_servers', 0)
            success_count = monitor_result.get('success_count', 0)
            warning_count = monitor_result.get('warning_count', 0)
            failed_count = monitor_result.get('failed_count', 0)
            
            # 判断整体状态
            if failed_count > 0:
                overall_status = "异常"
            elif warning_count > 0:
                overall_status = "告警"
            else:
                overall_status = "无异常"
            
            # 构建通知内容
            content = f"主机巡检结果\n时间: {monitor_time}\n结果: {overall_status}"
            
            # 添加统计信息
            if total_servers > 0:
                content += f"\n服务器总数: {total_servers}"
                content += f"\n正常: {success_count}, 告警: {warning_count}, 异常: {failed_count}"
            
            # 添加告警详情
            alert_details = []
            failed_details = []
            
            for result in monitor_result.get('results', []):
                server_name = result.get('server_name', '未知')
                server_ip = result.get('server_ip', '未知IP')
                
                if result.get('status') == 'failed':
                    error_msg = result.get('error_message', '连接失败')
                    # 使用简化的错误信息
                    simplified_error = self._simplify_error_message(error_msg)
                    failed_details.append(f"{server_name}({server_ip}): {simplified_error}")
                elif result.get('status') == 'warning' and result.get('alerts'):
                    for alert in result.get('alerts', []):
                        alert_type = alert.get('type', '').upper()
                        message = alert.get('message', '')
                        alert_details.append(f"{server_name}({server_ip}): {alert_type} - {message}")
            
            # 添加告警信息
            if alert_details:
                content += "\n\n告警信息:"
                for detail in alert_details:  # 显示所有告警
                    content += f"\n- {detail}"
            
            # 添加异常信息
            if failed_details:
                content += "\n\n异常信息:"
                for detail in failed_details:  # 显示所有异常
                    content += f"\n- {detail}"
            
            # 移除报告下载链接占位符，用户可在请求体模板中自定义
            
            return content
            
        except Exception as e:
            logger.error(f"生成通知内容失败: {str(e)}")
            return f"主机巡检结果\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n结果: 处理异常"
    
    def _send_to_channel(self, channel, content, url=None):
        """发送通知到指定通道"""
        try:
            if channel.method.upper() == 'GET':
                # GET请求，将内容作为参数发送
                params = {'message': content}
                response = requests.get(
                    channel.webhook_url,
                    params=params,
                    timeout=channel.timeout
                )
            else:
                # POST请求
                if channel.request_body:
                    # 使用自定义请求体模板
                    try:
                        body_template = json.loads(channel.request_body)
                        # 递归替换所有字符串值中的变量
                        body = self._replace_variables_in_dict(body_template, content, url)
                        headers = {'Content-Type': 'application/json'}
                        response = requests.post(
                            channel.webhook_url,
                            json=body,
                            headers=headers,
                            timeout=channel.timeout
                        )
                    except json.JSONDecodeError:
                        # 如果不是有效JSON，直接作为文本发送
                        request_body = channel.request_body.replace('#context#', content)
                        if url is not None:
                            request_body = request_body.replace('#url#', url)
                        response = requests.post(
                            channel.webhook_url,
                            data=request_body,
                            timeout=channel.timeout
                        )
                else:
                    # 默认JSON格式
                    data = {'message': content}
                    headers = {'Content-Type': 'application/json'}
                    response = requests.post(
                        channel.webhook_url,
                        json=data,
                        headers=headers,
                        timeout=channel.timeout
                    )
            
            # 检查响应状态
            if response.status_code in [200, 201, 204]:
                logger.info(f"通知发送成功 - 通道: {channel.name}")
                return True
            else:
                logger.warning(f"通知发送失败 - 通道: {channel.name}, 状态码: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"网络请求失败 - 通道: {channel.name}, 错误: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"发送通知异常 - 通道: {channel.name}, 错误: {str(e)}")
            return False
    
    def _replace_variables_in_dict(self, data, content, url=None):
        """递归替换字典中的变量"""
        if isinstance(data, dict):
            return {k: self._replace_variables_in_dict(v, content, url) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables_in_dict(item, content, url) for item in data]
        elif isinstance(data, str):
            result = data.replace('#context#', content)
            if url is not None:
                result = result.replace('#url#', url)
            return result
        else:
            return data