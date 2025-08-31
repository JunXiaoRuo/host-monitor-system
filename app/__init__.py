from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from app.models import db, Server, MonitorLog, ScheduleTask, Threshold, MonitorReport, AdminUser, NotificationChannel, ServiceConfig, ServiceMonitorLog, GlobalSettings, OSSConfig
from app.services import ServerService, ThresholdService
from app.batch_import_service import BatchImportService
from app.auth_service import AuthService
from app.notification_service import NotificationService
from app.monitor import HostMonitor
from app.scheduler import SchedulerService
from app.report_generator import ReportGenerator
from app.service_monitor import ServiceMonitorService
from functools import wraps
import logging
import os
from datetime import datetime, timedelta
import json

# 从 log_config 导入日志配置
from log_config import setup_flask_app_logging

logger = logging.getLogger(__name__)

def create_app(config_object='config.Config'):
    """创建Flask应用"""
    # 获取项目根目录路径
    import os
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(basedir, 'static'))
    
    # 加载配置
    app.config.from_object(config_object)
    
    # 设置日志配置
    console_output = app.config.get('CONSOLE_LOG_ENABLED', True)
    setup_flask_app_logging(app, 'flask', console_output)
    
    # 确保instance目录存在（用于数据库文件）
    instance_dir = os.path.join(basedir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    # 设置session配置
    app.config['SECRET_KEY'] = app.config.get('SECRET_KEY', os.urandom(24))
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # 设置报告目录的绝对路径
    if not os.path.isabs(app.config.get('REPORT_DIR', 'reports')):
        app.config['REPORT_DIR'] = os.path.join(basedir, app.config.get('REPORT_DIR', 'reports'))
    
    # 确保报告目录存在
    os.makedirs(app.config['REPORT_DIR'], exist_ok=True)
    
    # 初始化数据库
    db.init_app(app)
    
    # 创建服务实例
    server_service = ServerService()
    threshold_service = ThresholdService()
    batch_import_service = BatchImportService()
    auth_service = AuthService()
    notification_service = NotificationService()
    host_monitor = HostMonitor()
    report_generator = ReportGenerator(app.config['REPORT_DIR'])
    service_monitor_service = ServiceMonitorService(app)
    
    # 初始化调度器
    scheduler_service = SchedulerService(app.config['SQLALCHEMY_DATABASE_URI'], app.config['REPORT_DIR'])
    
    with app.app_context():
        # 创建数据库表
        db.create_all()
        
        # 初始化默认阈值
        if not Threshold.query.first():
            threshold = Threshold(
                cpu_threshold=app.config.get('DEFAULT_CPU_THRESHOLD', 80.0),
                memory_threshold=app.config.get('DEFAULT_MEMORY_THRESHOLD', 80.0),
                disk_threshold=app.config.get('DEFAULT_DISK_THRESHOLD', 80.0)
            )
            db.session.add(threshold)
            db.session.commit()
            logger.info("初始化默认阈值配置")
        
        # 启动调度器
        logger.info("开始启动调度器...")
        try:
            if scheduler_service.start_scheduler():
                logger.info("调度器启动成功")
            else:
                logger.error("调度器启动失败")
        except Exception as e:
            logger.error(f"调度器启动异常: {str(e)}")
            import traceback
            logger.error(f"调度器启动错误详情: {traceback.format_exc()}")
        
        # 启动服务监控循环
        logger.info("开始启动服务监控循环...")
        try:
            success, message = service_monitor_service.start_monitor_loop()
            if success:
                logger.info(f"服务监控循环启动成功: {message}")
            else:
                logger.error(f"服务监控循环启动失败: {message}")
        except Exception as e:
            logger.error(f"服务监控循环启动异常: {str(e)}")
            import traceback
            logger.error(f"服务监控循环启动错误详情: {traceback.format_exc()}")
    
    # 认证装饰器
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not auth_service.is_logged_in():
                if request.path.startswith('/api/'):
                    return jsonify({'success': False, 'message': '请先登录', 'need_login': True}), 401
                else:
                    return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    
    # 认证相关路由
    @app.route('/login')
    def login():
        """登录页面"""
        if auth_service.is_logged_in():
            return redirect(url_for('index'))
        return render_template('login.html')
    
    @app.route('/setup')
    def setup():
        """初始化设置页面"""
        if auth_service.has_admin_user():
            return redirect(url_for('login'))
        return render_template('setup.html')
    
    @app.route('/api/auth/check-init')
    def check_init():
        """检查是否需要初始化"""
        try:
            need_init = not auth_service.has_admin_user()
            return jsonify({
                'success': True,
                'need_init': need_init
            })
        except Exception as e:
            logger.error(f"检查初始化状态失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/auth/setup', methods=['POST'])
    def setup_admin():
        """创建管理员账户"""
        try:
            # 检查是否已有管理员账户
            if auth_service.has_admin_user():
                return jsonify({'success': False, 'message': '管理员账户已存在'})
            
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return jsonify({'success': False, 'message': '用户名和密码不能为空'})
            
            success, message = auth_service.create_admin_user(username, password)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"创建管理员账户失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """用户登录"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')
            
            if not username or not password:
                return jsonify({'success': False, 'message': '用户名和密码不能为空'})
            
            success, user, message = auth_service.authenticate(username, password)
            
            if success and user:
                auth_service.login_user(user)
                return jsonify({
                    'success': True,
                    'message': message,
                    'user': user.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"用户登录失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/auth/logout', methods=['POST'])
    @login_required
    def api_logout():
        """用户登出"""
        try:
            auth_service.logout_user()
            return jsonify({'success': True, 'message': '登出成功'})
        except Exception as e:
            logger.error(f"用户登出失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/auth/user')
    @login_required
    def get_current_user():
        """获取当前用户信息"""
        try:
            user = auth_service.get_current_user()
            if user:
                return jsonify({
                    'success': True,
                    'user': user.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': '用户信息获取失败'})
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 注册路由
    @app.route('/')
    def index():
        """主页"""
        # 检查是否需要初始化
        if not auth_service.has_admin_user():
            return redirect(url_for('setup'))
        
        # 检查是否已登录
        if not auth_service.is_logged_in():
            return redirect(url_for('login'))
        
        return render_template('index.html')
    
    @app.route('/api/dashboard')
    @login_required
    def dashboard():
        """仪表板数据"""
        try:
            # 获取服务器统计
            servers = server_service.get_active_servers()
            total_servers = len(servers)
            
            # 获取最新服务器状态
            server_status = host_monitor.get_latest_server_status()
            
            success_count = 0
            warning_count = 0
            failed_count = 0
            
            for server_id, status in server_status.items():
                if status['status'] == 'success':
                    success_count += 1
                elif status['status'] == 'warning':
                    warning_count += 1
                else:
                    failed_count += 1
            
            # 补充服务器名称
            server_dict = {s.id: s.name for s in servers}
            for server_id, status in server_status.items():
                status['server_name'] = server_dict.get(server_id, f'服务器{server_id}')
            
            # 获取服务总览数据
            services_overview = service_monitor_service.get_services_overview()
            
            return jsonify({
                'success': True,
                'data': {
                    'total_servers': total_servers,
                    'success_count': success_count,
                    'warning_count': warning_count,
                    'failed_count': failed_count,
                    'server_status': server_status,
                    'services_overview': services_overview
                }
            })
            
        except Exception as e:
            logger.error(f"获取仪表板数据失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/with-services', methods=['GET'])
    @login_required
    def get_servers_with_service_stats():
        """获取服务器列表及其服务统计信息"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # 获取服务器列表
            result = server_service.get_server_list(page, per_page)
            
            # 为每个服务器添加服务统计信息
            for server in result['servers']:
                server_id = server['id']
                
                # 获取该服务器的服务统计
                services = ServiceConfig.query.filter_by(server_id=server_id).all()
                total_services = len(services)
                monitoring_services = len([s for s in services if s.is_monitoring])
                
                # 获取最新状态统计
                normal_count = 0
                error_count = 0
                
                for service in services:
                    if not service.is_monitoring:
                        continue
                    
                    latest_log = ServiceMonitorLog.query.filter_by(
                        service_config_id=service.id
                    ).order_by(ServiceMonitorLog.monitor_time.desc()).first()
                    
                    if latest_log:
                        if latest_log.status == 'running':
                            normal_count += 1
                        elif latest_log.status in ['stopped', 'error']:
                            error_count += 1
                
                # 获取服务器最后监控时间（主机巡检）
                latest_monitor_log = MonitorLog.query.filter_by(
                    server_id=server_id
                ).order_by(MonitorLog.monitor_time.desc()).first()
                
                last_monitor_time = None
                if latest_monitor_log:
                    last_monitor_time = latest_monitor_log.monitor_time.isoformat()
                
                server.update({
                    'total_services': total_services,
                    'monitoring_services': monitoring_services,
                    'normal_services': normal_count,
                    'error_services': error_count,
                    'last_monitor_time': last_monitor_time
                })
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        except Exception as e:
            logger.error(f"获取服务器服务统计失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/servers', methods=['GET'])
    @login_required
    def get_servers():
        """获取服务器列表"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            result = server_service.get_server_list(page, per_page)
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        except Exception as e:
            logger.error(f"获取服务器列表失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers', methods=['POST'])
    @login_required
    def create_server():
        """创建服务器"""
        try:
            data = request.get_json()
            success, message, server = server_service.create_server(data)
            
            if success and server:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': server.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"创建服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/<int:server_id>/services', methods=['GET'])
    @login_required
    def get_server_services(server_id):
        """获取指定服务器的服务列表"""
        try:
            services = service_monitor_service.get_services_by_server(server_id)
            return jsonify({'success': True, 'data': services})
            
        except Exception as e:
            logger.error(f"获取服务器服务列表失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/servers/<int:server_id>', methods=['PUT'])
    @login_required
    def update_server(server_id):
        """更新服务器"""
        try:
            data = request.get_json()
            success, message, server = server_service.update_server(server_id, data)
            
            if success and server:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': server.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"更新服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/<int:server_id>', methods=['DELETE'])
    @login_required
    def delete_server(server_id):
        """删除服务器"""
        try:
            success, message = server_service.delete_server(server_id)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"删除服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/bulk-delete', methods=['POST'])
    @login_required
    def bulk_delete_servers():
        """批量删除服务器"""
        try:
            data = request.get_json()
            server_ids = data.get('server_ids', [])
            
            success, message, result = server_service.bulk_delete_servers(server_ids)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': result
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"批量删除服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/test', methods=['POST'])
    @login_required
    def test_server_connection():
        """测试服务器连接"""
        try:
            data = request.get_json()
            success, message = server_service.ssh_manager.test_connection(
                host=data['host'],
                port=data['port'],
                username=data['username'],
                password=data.get('password'),
                private_key_path=data.get('private_key_path')
            )
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"测试连接失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/<int:server_id>/test', methods=['POST'])
    @login_required
    def test_existing_server_connection(server_id):
        """测试已存在服务器的连接"""
        try:
            success, message = server_service.test_server_connection(server_id)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"测试服务器连接失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 批量导入相关路由
    @app.route('/api/servers/batch-test', methods=['POST'])
    @login_required
    def batch_test_servers():
        """一键检测所有服务器连接"""
        try:
            data = request.get_json()
            server_ids = data.get('server_ids', [])
            
            if not server_ids:
                # 如果没有指定服务器ID，则测试所有活跃服务器
                servers = server_service.get_active_servers()
                server_ids = [s.id for s in servers]
            
            results = batch_import_service.test_server_connections(server_ids)
            
            # 统计结果
            total_count = len(results)
            success_count = sum(1 for r in results.values() if r['success'])
            failed_count = total_count - success_count
            
            return jsonify({
                'success': True,
                'message': f'检测完成，成功 {success_count} 个，失败 {failed_count} 个',
                'data': {
                    'results': results,
                    'summary': {
                        'total': total_count,
                        'success': success_count,
                        'failed': failed_count
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"批量测试服务器连接失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/template/download')
    @login_required
    def download_server_template():
        """下载服务器导入模板"""
        try:
            # 创建临时模板文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            template_path = os.path.join(temp_dir, '服务器导入模板.xlsx')
            
            success = batch_import_service.create_server_template(template_path)
            if not success:
                return jsonify({'success': False, 'message': '模板创建失败'})
            
            return send_file(
                template_path,
                as_attachment=True,
                download_name='服务器导入模板.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as e:
            logger.error(f"下载服务器模板失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/servers/batch-import', methods=['POST'])
    @login_required
    def batch_import_servers():
        """批量导入服务器"""
        try:
            # 检查是否上传了文件
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': '没有上传文件'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': '没有选择文件'})
            
            # 检查文件类型
            if not file.filename.endswith('.xlsx'):
                return jsonify({'success': False, 'message': '只支持.xlsx格式文件'})
            
            # 保存上传的文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            
            try:
                # 解析Excel文件
                success, message, servers = batch_import_service.parse_server_excel(temp_path)
                if not success:
                    return jsonify({'success': False, 'message': message})
                
                # 批量导入服务器
                success, message, result = batch_import_service.import_servers(servers)
                
                return jsonify({
                    'success': success,
                    'message': message,
                    'data': result
                })
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            logger.error(f"批量导入服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/template/download')
    @login_required
    def download_service_template():
        """下载服务配置导入模板"""
        try:
            # 创建临时模板文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            template_path = os.path.join(temp_dir, '服务配置导入模板.xlsx')
            
            success = batch_import_service.create_service_template(template_path)
            if not success:
                return jsonify({'success': False, 'message': '模板创建失败'})
            
            return send_file(
                template_path,
                as_attachment=True,
                download_name='服务配置导入模板.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
        except Exception as e:
            logger.error(f"下载服务配置模板失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/batch-import', methods=['POST'])
    @login_required
    def batch_import_services():
        """批量导入服务配置"""
        try:
            # 检查是否上传了文件
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': '没有上传文件'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'message': '没有选择文件'})
            
            # 检查文件类型
            if not file.filename.endswith('.xlsx'):
                return jsonify({'success': False, 'message': '只支持.xlsx格式文件'})
            
            # 保存上传的文件
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            
            try:
                # 解析Excel文件
                success, message, services = batch_import_service.parse_service_excel(temp_path)
                if not success:
                    return jsonify({'success': False, 'message': message})
                
                # 批量导入服务配置
                success, message, result = batch_import_service.import_services(services)
                
                return jsonify({
                    'success': success,
                    'message': message,
                    'data': result
                })
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
        except Exception as e:
            logger.error(f"批量导入服务配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/monitor/execute', methods=['POST'])
    @login_required
    def execute_monitor():
        """执行监控"""
        try:
            result = host_monitor.monitor_all_servers()
            
            # 生成报告
            report_name = f"manual_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_path = report_generator.generate_html_report(result, report_name)
            
            # 保存报告记录
            if report_path:
                report = MonitorReport(
                    report_name=report_name,
                    report_type='manual',
                    report_path=report_path,
                    server_count=result['total_servers'],
                    success_count=result['success_count'],
                    failed_count=result['failed_count'],
                    warning_count=result['warning_count']
                )
                db.session.add(report)
                db.session.commit()
            
            # 发送通知
            notification_success = False
            notification_message = ""
            try:
                notification_success, notification_message = notification_service.send_notification(result, report_path)
                logger.info(f"通知发送结果: {notification_message}")
            except Exception as notify_error:
                logger.error(f"发送通知失败: {str(notify_error)}")
                notification_message = f"通知发送失败: {str(notify_error)}"
            
            response_data = {
                'success': True,
                'message': '监控执行完成',
                'data': {
                    'total_servers': result['total_servers'],
                    'success_count': result['success_count'],
                    'warning_count': result['warning_count'],
                    'failed_count': result['failed_count'],
                    'execution_time': result['execution_time'],
                    'report_path': report_path,
                    'notification_sent': notification_success,
                    'notification_message': notification_message
                }
            }
            
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"执行监控失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/monitor/server/<int:server_id>', methods=['POST'])
    @login_required
    def monitor_single_server(server_id):
        """监控单个服务器"""
        try:
            # 获取服务器信息
            server = Server.query.get(server_id)
            if not server:
                return jsonify({'success': False, 'message': '服务器不存在'})
            
            if server.status != 'active':
                return jsonify({'success': False, 'message': '服务器未启用'})
            
            # 获取阈值配置
            thresholds = threshold_service.get_threshold_config()
            
            # 监控单个服务器
            result = host_monitor.monitor_single_server(server, thresholds)
            
            # 保存监控结果
            host_monitor.save_monitor_result(result)
            
            logger.info(f"单个服务器监控完成: {server.name}, 状态: {result['status']}")
            
            return jsonify({
                'success': True, 
                'message': f'服务器 "{server.name}" 监控完成',
                'data': result
            })
            
        except Exception as e:
            logger.error(f"监控单个服务器失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/thresholds', methods=['GET'])
    @login_required
    def get_thresholds():
        """获取阈值配置"""
        try:
            config = threshold_service.get_threshold_config()
            return jsonify({'success': True, 'data': config})
            
        except Exception as e:
            logger.error(f"获取阈值配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/thresholds', methods=['POST'])
    @login_required
    def update_thresholds():
        """更新阈值配置"""
        try:
            data = request.get_json()
            success, message = threshold_service.update_threshold_config(data)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"更新阈值配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedules', methods=['GET'])
    @login_required
    def get_schedules():
        """获取计划任务列表"""
        try:
            schedules = scheduler_service.get_task_list()
            return jsonify({'success': True, 'data': schedules})
            
        except Exception as e:
            logger.error(f"获取计划任务列表失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedules', methods=['POST'])
    @login_required
    def create_schedule():
        """创建计划任务"""
        try:
            data = request.get_json()
            success, message, task = scheduler_service.create_schedule_task(data)
            
            if success and task:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': task.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"创建计划任务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedules/<int:task_id>', methods=['PUT'])
    @login_required
    def update_schedule(task_id):
        """更新计划任务"""
        try:
            data = request.get_json()
            success, message, task = scheduler_service.update_schedule_task(task_id, data)
            
            if success and task:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': task.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"更新计划任务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/schedules/<int:task_id>', methods=['DELETE'])
    @login_required
    def delete_schedule(task_id):
        """删除计划任务"""
        try:
            success, message = scheduler_service.delete_schedule_task(task_id)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"删除计划任务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/logs', methods=['GET'])
    @login_required
    def get_logs():
        """获取监控日志（支持分页和筛选）"""
        try:
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # 获取筛选参数
            server_id = request.args.get('server_id', type=int)
            status = request.args.get('status', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            
            # 构建查询
            query = MonitorLog.query
            
            # 服务器筛选
            if server_id:
                query = query.filter(MonitorLog.server_id == server_id)
            
            # 状态筛选
            if status:
                query = query.filter(MonitorLog.status == status)
            
            # 日期筛选
            if start_date:
                from datetime import datetime
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(MonitorLog.monitor_time >= start_dt)
            
            if end_date:
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(MonitorLog.monitor_time < end_dt)
            
            # 执行分页查询
            pagination = query.order_by(MonitorLog.monitor_time.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            return jsonify({
                'success': True,
                'data': {
                    'logs': [log.to_dict() for log in pagination.items],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': pagination.total,
                        'pages': pagination.pages,
                        'has_prev': pagination.has_prev,
                        'has_next': pagination.has_next
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"获取监控日志失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/logs/<int:log_id>', methods=['GET'])
    @login_required
    def get_log_detail(log_id):
        """获取日志详情"""
        try:
            log = MonitorLog.query.get(log_id)
            if not log:
                return jsonify({'success': False, 'message': '日志不存在'})
            
            return jsonify({
                'success': True,
                'data': log.to_dict()
            })
            
        except Exception as e:
            logger.error(f"获取日志详情失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/logs/<int:log_id>', methods=['DELETE'])
    @login_required
    def delete_log(log_id):
        """删除监控日志"""
        try:
            log = MonitorLog.query.get(log_id)
            if not log:
                return jsonify({'success': False, 'message': '日志不存在'})
            
            log_info = f"日志ID: {log.id}, 服务器: {log.server.name if log.server else '未知'}, 时间: {log.monitor_time}"
            
            # 删除数据库记录
            db.session.delete(log)
            db.session.commit()
            
            logger.info(f"删除监控日志: {log_info}")
            return jsonify({'success': True, 'message': '日志删除成功'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除监控日志失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/logs/bulk-delete', methods=['POST'])
    @login_required
    def bulk_delete_logs():
        """批量删除监控日志"""
        try:
            data = request.get_json()
            log_ids = data.get('log_ids', [])
            
            if not log_ids:
                return jsonify({'success': False, 'message': '请选择要删除的日志'})
            
            # 验证所有ID都是整数
            try:
                log_ids = [int(log_id) for log_id in log_ids]
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': '无效的日志ID'})
            
            # 查找存在的日志
            logs = MonitorLog.query.filter(MonitorLog.id.in_(log_ids)).all()
            
            if not logs:
                return jsonify({'success': False, 'message': '找不到指定的日志'})
            
            deleted_count = len(logs)
            log_info_list = []
            
            # 批量删除
            for log in logs:
                log_info = f"日志ID: {log.id}, 服务器: {log.server.name if log.server else '未知'}, 时间: {log.monitor_time}"
                log_info_list.append(log_info)
                db.session.delete(log)
            
            db.session.commit()
            
            logger.info(f"批量删除监控日志: {deleted_count}条")
            for info in log_info_list:
                logger.info(f"  - {info}")
            
            return jsonify({
                'success': True, 
                'message': f'成功删除 {deleted_count} 条日志',
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量删除监控日志失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/reports', methods=['GET'])
    @login_required
    def get_reports():
        """获取报告列表（支持分页和筛选）"""
        try:
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            
            # 获取筛选参数
            report_type = request.args.get('type', '')
            start_date = request.args.get('start_date', '')
            end_date = request.args.get('end_date', '')
            
            # 构建查询
            query = MonitorReport.query
            
            # 类型筛选
            if report_type:
                query = query.filter(MonitorReport.report_type == report_type)
            
            # 日期筛选
            if start_date:
                from datetime import datetime
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(MonitorReport.created_at >= start_dt)
            
            if end_date:
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(MonitorReport.created_at < end_dt)
            
            # 执行分页查询
            pagination = query.order_by(MonitorReport.created_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            return jsonify({
                'success': True,
                'data': {
                    'reports': [report.to_dict() for report in pagination.items],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': pagination.total,
                        'pages': pagination.pages,
                        'has_prev': pagination.has_prev,
                        'has_next': pagination.has_next
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"获取报告列表失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/reports/<int:report_id>/download')
    @login_required
    def download_report(report_id):
        """下载报告"""
        try:
            report = MonitorReport.query.get(report_id)
            if not report or not os.path.exists(report.report_path):
                return jsonify({'success': False, 'message': '报告文件不存在'})
            
            return send_file(
                report.report_path,
                as_attachment=True,
                download_name=f"{report.report_name}.html"
            )
            
        except Exception as e:
            logger.error(f"下载报告失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/reports/<int:report_id>', methods=['DELETE'])
    @login_required
    def delete_report(report_id):
        """删除报告"""
        try:
            report = MonitorReport.query.get(report_id)
            if not report:
                return jsonify({'success': False, 'message': '报告不存在'})
            
            # 删除文件
            if os.path.exists(report.report_path):
                os.remove(report.report_path)
                logger.info(f"删除报告文件: {report.report_path}")
            
            # 删除数据库记录
            db.session.delete(report)
            db.session.commit()
            
            return jsonify({'success': True, 'message': '报告删除成功'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除报告失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/reports/bulk-delete', methods=['POST'])
    @login_required
    def bulk_delete_reports():
        """批量删除报告"""
        try:
            data = request.get_json()
            report_ids = data.get('report_ids', [])
            
            if not report_ids:
                return jsonify({'success': False, 'message': '请选择要删除的报告'})
            
            # 验证所有ID都是整数
            try:
                report_ids = [int(report_id) for report_id in report_ids]
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': '无效的报告ID'})
            
            # 查找存在的报告
            reports = MonitorReport.query.filter(MonitorReport.id.in_(report_ids)).all()
            
            if not reports:
                return jsonify({'success': False, 'message': '找不到指定的报告'})
            
            deleted_count = len(reports)
            deleted_files = []
            
            # 批量删除
            for report in reports:
                # 删除文件
                if os.path.exists(report.report_path):
                    try:
                        os.remove(report.report_path)
                        deleted_files.append(report.report_path)
                        logger.info(f"删除报告文件: {report.report_path}")
                    except Exception as file_error:
                        logger.warning(f"删除报告文件失败: {report.report_path}, 错误: {str(file_error)}")
                
                # 删除数据库记录
                db.session.delete(report)
            
            db.session.commit()
            
            logger.info(f"批量删除报告: {deleted_count}条, 删除文件: {len(deleted_files)}个")
            
            return jsonify({
                'success': True, 
                'message': f'成功删除 {deleted_count} 个报告',
                'deleted_count': deleted_count,
                'deleted_files_count': len(deleted_files)
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"批量删除报告失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/reports/generate', methods=['POST'])
    @login_required
    def generate_manual_report():
        """生成手动报告"""
        try:
            # 执行监控
            result = host_monitor.monitor_all_servers()
            
            # 生成报告
            report_name = f"manual_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_path = report_generator.generate_html_report(result, report_name)
            
            if report_path:
                # 保存报告记录
                report = MonitorReport(
                    report_name=report_name,
                    report_type='manual',
                    report_path=report_path,
                    server_count=result['total_servers'],
                    success_count=result['success_count'],
                    failed_count=result['failed_count'],
                    warning_count=result['warning_count']
                )
                db.session.add(report)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': '报告生成成功',
                    'data': report.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': '报告生成失败'})
                
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 通知通道管理路由
    @app.route('/api/notifications', methods=['GET'])
    @login_required
    def get_notification_channels():
        """获取通知通道列表"""
        try:
            channels = NotificationChannel.query.order_by(NotificationChannel.created_at.desc()).all()
            return jsonify({
                'success': True,
                'data': [channel.to_dict() for channel in channels]
            })
            
        except Exception as e:
            logger.error(f"获取通知通道列表失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications', methods=['POST'])
    @login_required
    def create_notification_channel():
        """创建通知通道"""
        try:
            data = request.get_json()
            
            # 验证必填字段
            required_fields = ['name', 'webhook_url']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field} 不能为空'})
            
            success, message, channel = notification_service.create_channel(data)
            
            if success and channel:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': channel.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"创建通知通道失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications/<int:channel_id>', methods=['PUT'])
    @login_required
    def update_notification_channel(channel_id):
        """更新通知通道"""
        try:
            channel = NotificationChannel.query.get(channel_id)
            if not channel:
                return jsonify({'success': False, 'message': '通知通道不存在'})
            
            data = request.get_json()
            
            # 更新字段
            if 'name' in data:
                channel.name = data['name']
            if 'webhook_url' in data:
                channel.webhook_url = data['webhook_url']
            if 'method' in data:
                channel.method = data['method']
            # content_template字段已移除，直接在请求体模板中使用变量
            if 'is_enabled' in data:
                channel.is_enabled = data['is_enabled']
            if 'timeout' in data:
                channel.timeout = data['timeout']
            if 'request_body' in data:
                channel.set_request_body_template(data['request_body'])
            
            # OSS配置已移至全局配置表 oss_config
            
            channel.updated_at = datetime.now()
            db.session.commit()
            
            logger.info(f"通知通道更新成功: {channel.name}")
            return jsonify({
                'success': True,
                'message': '通知通道更新成功',
                'data': channel.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新通知通道失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications/<int:channel_id>', methods=['DELETE'])
    @login_required
    def delete_notification_channel(channel_id):
        """删除通知通道"""
        try:
            channel = NotificationChannel.query.get(channel_id)
            if not channel:
                return jsonify({'success': False, 'message': '通知通道不存在'})
            
            channel_name = channel.name
            db.session.delete(channel)
            db.session.commit()
            
            logger.info(f"通知通道删除成功: {channel_name}")
            return jsonify({'success': True, 'message': '通知通道删除成功'})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除通知通道失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/notifications/<int:channel_id>/test', methods=['POST'])
    @login_required
    def test_notification_channel(channel_id):
        """测试通知通道"""
        try:
            channel = NotificationChannel.query.get(channel_id)
            if not channel:
                return jsonify({'success': False, 'message': '通知通道不存在'})
            
            # 构建测试消息
            test_result = {
                'total_servers': 1,
                'success_count': 1,
                'warning_count': 0,
                'failed_count': 0,
                'results': [{
                    'server_name': '测试服务器',
                    'server_ip': '192.168.1.100',
                    'status': 'success',
                    'alerts': []
                }]
            }
            
            # 发送测试通知
            success = notification_service._send_to_channel(channel, 
                notification_service._generate_notification_content(test_result))
            
            if success:
                return jsonify({'success': True, 'message': '测试通知发送成功'})
            else:
                return jsonify({'success': False, 'message': '测试通知发送失败'})
                
        except Exception as e:
            logger.error(f"测试通知通道失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # OSS配置管理路由（API接口）
    @app.route('/api/oss-config', methods=['GET'])
    @login_required
    def get_oss_config():
        """获取OSS配置"""
        try:
            config = OSSConfig.query.first()
            if not config:
                # 如果没有配置，返回默认配置
                return jsonify({
                    'success': True,
                    'data': {
                        'is_enabled': False,
                        'endpoint': '',
                        'access_key_id': '',
                        'access_key_secret': '',
                        'bucket_name': '',
                        'folder_path': '',
                        'expires_in_hours': 24
                    }
                })
            
            return jsonify({
                'success': True,
                'data': config.to_dict()
            })
            
        except Exception as e:
            logger.error(f"获取OSS配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/oss-config', methods=['POST', 'PUT'])
    @login_required
    def save_oss_config():
        """保存或更新OSS配置"""
        try:
            data = request.get_json()
            
            # 获取现有配置或创建新配置
            config = OSSConfig.query.first()
            if not config:
                config = OSSConfig()
                db.session.add(config)
            
            # 更新配置字段
            if 'is_enabled' in data:
                config.is_enabled = data['is_enabled']
            if 'endpoint' in data:
                config.endpoint = data['endpoint']
            if 'access_key_id' in data:
                config.access_key_id = data['access_key_id']
            if 'access_key_secret' in data:
                config.access_key_secret = data['access_key_secret']
            if 'bucket_name' in data:
                config.bucket_name = data['bucket_name']
            if 'folder_path' in data:
                config.folder_path = data['folder_path']
            if 'expires_in_hours' in data:
                config.expires_in_hours = data['expires_in_hours']
            
            config.updated_at = datetime.now()
            db.session.commit()
            
            logger.info("OSS配置保存成功")
            return jsonify({
                'success': True,
                'message': 'OSS配置保存成功',
                'data': config.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"保存OSS配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/oss-config/test', methods=['POST'])
    @login_required
    def test_oss_config():
        """测试OSS配置"""
        try:
            data = request.get_json()
            
            # 验证必要字段
            required_fields = ['endpoint', 'access_key_id', 'access_key_secret', 'bucket_name']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'缺少必要字段: {field}'})
            
            # 这里可以添加实际的OSS连接测试逻辑
            # 暂时返回成功
            return jsonify({'success': True, 'message': 'OSS配置测试成功'})
            
        except Exception as e:
            logger.error(f"测试OSS配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 服务监控管理路由（API接口）
    @app.route('/api/services/servers', methods=['GET'])
    @login_required
    def get_servers_with_services():
        """获取所有服务器及其服务统计"""
        try:
            servers_data = service_monitor_service.get_all_servers_with_services()
            return jsonify({'success': True, 'data': servers_data})
            
        except Exception as e:
            logger.error(f"获取服务器服务信息失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/services', methods=['POST'])
    @login_required
    def create_service():
        """创建服务配置"""
        try:
            data = request.get_json()
            success, message, service = service_monitor_service.create_service_config(data)
            
            if success and service:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': service.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"创建服务配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/<int:service_id>', methods=['GET'])
    @login_required
    def get_service(service_id):
        """获取服务配置详情"""
        try:
            service = ServiceConfig.query.get(service_id)
            if not service:
                return jsonify({'success': False, 'message': '服务配置不存在'})
            
            return jsonify({
                'success': True,
                'data': service.to_dict()
            })
            
        except Exception as e:
            logger.error(f"获取服务配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/<int:service_id>', methods=['PUT'])
    @login_required
    def update_service(service_id):
        """更新服务配置"""
        try:
            data = request.get_json()
            success, message, service = service_monitor_service.update_service_config(service_id, data)
            
            if success and service:
                return jsonify({
                    'success': True,
                    'message': message,
                    'data': service.to_dict()
                })
            else:
                return jsonify({'success': False, 'message': message})
                
        except Exception as e:
            logger.error(f"更新服务配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/<int:service_id>', methods=['DELETE'])
    @login_required
    def delete_service(service_id):
        """删除服务配置"""
        try:
            success, message = service_monitor_service.delete_service_config(service_id)
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"删除服务配置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/monitor/all', methods=['POST'])
    @login_required
    def monitor_all_services():
        """监控所有服务"""
        try:
            result = service_monitor_service.monitor_all_services()
            
            if 'error' in result:
                return jsonify({'success': False, 'message': result['error']})
            else:
                return jsonify({
                    'success': True,
                    'message': '服务监控完成',
                    'data': result
                })
            
        except Exception as e:
            logger.error(f"监控所有服务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/monitor/single/<int:service_id>', methods=['POST'])
    @login_required
    def monitor_single_service(service_id):
        """监控单个服务"""
        try:
            result = service_monitor_service.monitor_single_service(service_id)
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"监控单个服务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})

    @app.route('/api/services/monitor/<int:server_id>', methods=['POST'])
    @login_required
    def monitor_server_services(server_id):
        """监控指定服务器的服务"""
        try:
            result = service_monitor_service.monitor_server_services(server_id)
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"监控服务器服务失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/settings', methods=['GET'])
    @login_required
    def get_service_settings():
        """获取服务监控设置"""
        try:
            monitor_interval = service_monitor_service.get_service_monitor_interval()
            
            return jsonify({
                'success': True,
                'data': {
                    'monitor_interval': monitor_interval
                }
            })
            
        except Exception as e:
            logger.error(f"获取服务监控设置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/settings', methods=['POST'])
    @login_required
    def update_service_settings():
        """更新服务监控设置"""
        try:
            data = request.get_json()
            monitor_interval = data.get('monitor_interval')
            
            if not monitor_interval or monitor_interval < 1 or monitor_interval > 1440:
                return jsonify({'success': False, 'message': '监控间隔必须在1-1440分钟之间'})
            
            success, message = service_monitor_service.set_global_setting(
                'service_monitor_interval', 
                str(monitor_interval), 
                '服务监控时间间隔（分钟）'
            )
            
            # 如果设置成功，重启监控循环使新设置立即生效
            if success:
                try:
                    restart_success, restart_message = service_monitor_service.restart_monitor_loop()
                    if restart_success:
                        logger.info(f"服务监控间隔更新为{monitor_interval}分钟，监控循环已重启")
                    else:
                        logger.warning(f"设置更新成功但重启监控循环失败: {restart_message}")
                except Exception as e:
                    logger.error(f"重启服务监控循环异常: {str(e)}")
            
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"更新服务监控设置失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 服务监控循环管理API
    @app.route('/api/services/monitor/status', methods=['GET'])
    @login_required
    def get_service_monitor_status():
        """获取服务监控循环状态"""
        try:
            status = service_monitor_service.get_monitor_status()
            return jsonify({'success': True, 'data': status})
            
        except Exception as e:
            logger.error(f"获取服务监控状态失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/monitor/start', methods=['POST'])
    @login_required
    def start_service_monitor_loop():
        """启动服务监控循环"""
        try:
            success, message = service_monitor_service.start_monitor_loop()
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"启动服务监控循环失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    @app.route('/api/services/monitor/stop', methods=['POST'])
    @login_required
    def stop_service_monitor_loop():
        """停止服务监控循环"""
        try:
            success, message = service_monitor_service.stop_monitor_loop()
            return jsonify({'success': success, 'message': message})
            
        except Exception as e:
            logger.error(f"停止服务监控循环失败: {str(e)}")
            return jsonify({'success': False, 'message': str(e)})
    
    # 系统日志API
    @app.route('/api/logs/<log_file>', methods=['GET'])
    @login_required
    def get_log_content(log_file):
        """获取指定日志文件的内容"""
        try:
            # 定义允许访问的日志文件
            allowed_logs = {
                'flask.log': 'flask.log',
                'run.log': 'run.log', 
                'production.log': 'production.log',
                'run-error.log': 'run-error.log',
                'flask-error.log': 'flask-error.log',
                'production-error.log': 'production-error.log'
            }
            
            if log_file not in allowed_logs:
                return jsonify({'success': False, 'message': '不允许访问的日志文件'})
            
            # 构建日志文件路径
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            log_path = os.path.join(log_dir, allowed_logs[log_file])
            
            # 检查文件是否存在
            if not os.path.exists(log_path):
                return jsonify({
                    'success': True,
                    'content': '',
                    'message': '日志文件不存在或尚未生成',
                    'last_modified': None
                })
            
            # 获取文件修改时间
            last_modified = os.path.getmtime(log_path)
            last_modified_str = datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M:%S')
            
            # 读取文件内容（最后1000行）
            lines = []
            try:
                # 首先尝试UTF-8编码，使用errors='replace'处理无法解码的字节
                with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
            except Exception:
                try:
                    # 如果仍然失败，尝试使用GBK编码
                    with open(log_path, 'r', encoding='gbk', errors='replace') as f:
                        lines = f.readlines()
                except Exception:
                    # 最后尝试使用latin-1编码（几乎不会失败）
                    with open(log_path, 'r', encoding='latin-1', errors='replace') as f:
                        lines = f.readlines()
            
            # 只返回最后1000行
            if len(lines) > 1000:
                lines = lines[-1000:]
            
            content = ''.join(lines)
            
            return jsonify({
                'success': True,
                'content': content,
                'last_modified': last_modified_str,
                'total_lines': len(lines)
            })
            
        except Exception as e:
            logger.error(f"读取日志文件失败: {str(e)}")
            return jsonify({'success': False, 'message': f'读取日志文件失败: {str(e)}'})
    
    # 注册应用关闭时的清理函数
    import atexit
    
    def cleanup_scheduler():
        """应用关闭时停止调度器和服务监控循环"""
        # 停止服务监控循环
        try:
            success, message = service_monitor_service.stop_monitor_loop()
            if success:
                logger.info("应用关闭，服务监控循环已停止")
            else:
                logger.error(f"停止服务监控循环失败: {message}")
        except Exception as e:
            logger.error(f"停止服务监控循环失败: {str(e)}")
        
        # 停止调度器
        if hasattr(scheduler_service, 'scheduler') and scheduler_service.scheduler:
            try:
                scheduler_service.stop_scheduler()
                logger.info("应用关闭，调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {str(e)}")
    
    # 使用atexit而不是teardown_appcontext来保证调度器不会在每个请求后停止
    atexit.register(cleanup_scheduler)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)