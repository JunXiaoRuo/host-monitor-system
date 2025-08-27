"""
通知服务模块
负责webhook通知的发送和管理
"""

import json
import requests
from datetime import datetime
from app.models import db, NotificationChannel
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务类"""
    
    def __init__(self):
        self.default_timeout = 30
    
    def create_channel(self, data):
        """创建通知通道"""
        try:
            channel = NotificationChannel(
                name=data['name'],
                webhook_url=data['webhook_url'],
                method=data.get('method', 'POST'),
                content_template=data.get('content_template', ''),
                timeout=data.get('timeout', self.default_timeout)
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
            if 'content_template' in data:
                channel.content_template = data.get('content_template', '')
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
    
    def send_notification(self, monitor_result):
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
                    if self._send_to_channel(channel, content):
                        success_count += 1
                except Exception as e:
                    logger.error(f"发送通知失败 - 通道: {channel.name}, 错误: {str(e)}")
            
            message = f"通知发送完成，成功 {success_count}/{len(channels)} 个通道"
            logger.info(message)
            return True, message
            
        except Exception as e:
            logger.error(f"发送通知失败: {str(e)}")
            return False, f"发送通知失败: {str(e)}"
    
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
            
            return content
            
        except Exception as e:
            logger.error(f"生成通知内容失败: {str(e)}")
            return f"主机巡检结果\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n结果: 处理异常"
    
    def _send_to_channel(self, channel, content):
        """发送通知到指定通道"""
        try:
            # 替换内容变量
            final_content = content
            if channel.content_template:
                final_content = channel.content_template.replace('#context#', content)
            
            if channel.method.upper() == 'GET':
                # GET请求，将内容作为参数发送
                params = {'message': final_content}
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
                        body = self._replace_variables_in_dict(body_template, final_content)
                        headers = {'Content-Type': 'application/json'}
                        response = requests.post(
                            channel.webhook_url,
                            json=body,
                            headers=headers,
                            timeout=channel.timeout
                        )
                    except json.JSONDecodeError:
                        # 如果不是有效JSON，直接作为文本发送
                        response = requests.post(
                            channel.webhook_url,
                            data=channel.request_body.replace('#context#', final_content),
                            timeout=channel.timeout
                        )
                else:
                    # 默认JSON格式
                    data = {'message': final_content}
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
    
    def _replace_variables_in_dict(self, data, content):
        """递归替换字典中的变量"""
        if isinstance(data, dict):
            return {k: self._replace_variables_in_dict(v, content) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables_in_dict(item, content) for item in data]
        elif isinstance(data, str):
            return data.replace('#context#', content)
        else:
            return data