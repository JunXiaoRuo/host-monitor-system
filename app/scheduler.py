from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from app.models import db, ScheduleTask
from app.monitor import HostMonitor
from app.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

def execute_monitor_task_static(task_id: int, database_url: str, report_dir: str):
    """静态任务执行函数，避免序列化问题"""
    logger.info(f"开始执行计划任务 ID: {task_id}")
    
    try:
        # 更新任务最后执行时间
        from app.models import db, ScheduleTask, MonitorReport
        from flask import current_app
        
        # 使用当前应用上下文，避免重新创建应用实例
        if current_app:
            app = current_app
        else:
            # 如果没有当前应用上下文，创建一个最小化的应用实例
            from flask import Flask
            from config import Config
            app = Flask(__name__)
            app.config.from_object(Config)
            
            # 只初始化数据库，不初始化调度器和服务监控
            from app.models import db as database
            database.init_app(app)
            
        with app.app_context():
            # 创建新的服务实例（在应用上下文中）
            from app.monitor import HostMonitor
            from app.report_generator import ReportGenerator
            
            host_monitor = HostMonitor()
            report_generator = ReportGenerator(report_dir)
            
            task = ScheduleTask.query.get(task_id)
            if not task:
                logger.error(f"任务 ID {task_id} 不存在")
                return
            
            task.last_run = datetime.now()
            
            # 更新下次执行时间 - 从调度器获取
            try:
                from app.scheduler import SchedulerService
                scheduler_service = SchedulerService.get_instance()
                if scheduler_service and scheduler_service.scheduler and scheduler_service.scheduler.running:
                    job_id = f"task_{task_id}"
                    job = scheduler_service.scheduler.get_job(job_id)
                    if job and job.next_run_time:
                        # 将UTC时间转换为本地时间
                        from datetime import timezone, timedelta
                        china_tz = timezone(timedelta(hours=8))
                        next_run_local = job.next_run_time.astimezone(china_tz).replace(tzinfo=None)
                        task.next_run = next_run_local
                        logger.info(f"任务 {task.name} 下次执行时间更新为: {task.next_run}")
                    else:
                        logger.warning(f"无法获取任务 {task.name} 的下次执行时间")
                else:
                    logger.warning("调度器未运行，无法更新下次执行时间")
            except Exception as update_error:
                logger.error(f"更新下次执行时间失败: {str(update_error)}")
            
            db.session.commit()
            
            logger.info(f"开始执行计划任务: {task.name}")
            
            # 执行监控（确保在应用上下文中）
            monitor_result = host_monitor.monitor_all_servers()
            
            logger.info(f"监控完成，结果: 总数={monitor_result['total_servers']}, 成功={monitor_result['success_count']}, 告警={monitor_result['warning_count']}, 失败={monitor_result['failed_count']}")
            
            # 生成报告
            report_name = f"scheduled_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_path = report_generator.generate_html_report(
                monitor_result, 
                report_name
            )
            
            # 保存报告记录
            if report_path:
                report = MonitorReport(
                    report_name=report_name,
                    report_type='scheduled',
                    report_path=report_path,
                    server_count=monitor_result['total_servers'],
                    success_count=monitor_result['success_count'],
                    failed_count=monitor_result['failed_count'],
                    warning_count=monitor_result['warning_count']
                )
                db.session.add(report)
                db.session.commit()
                logger.info(f"报告保存成功: {report_path}")
            
            # 发送通知
            notification_success = False
            notification_message = ""
            try:
                from app.notification_service import NotificationService
                notification_service = NotificationService()
                notification_success, notification_message = notification_service.send_notification(monitor_result, report_path)
                logger.info(f"计划任务通知发送结果: {notification_message}")
            except Exception as notify_error:
                logger.error(f"计划任务发送通知失败: {str(notify_error)}")
                notification_message = f"通知发送失败: {str(notify_error)}"
            
            logger.info(f"计划任务 {task.name} 执行完成")
            
    except Exception as e:
        logger.error(f"执行计划任务失败: {str(e)}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

class SchedulerService:
    """计划任务调度服务"""
    
    _instance = None  # 类变量用于单例模式
    _initialized = False  # 标记是否已初始化
    
    def __new__(cls, database_url: Optional[str] = None, report_dir: str = "reports"):
        """实现单例模式，防止重复初始化"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, database_url: Optional[str] = None, report_dir: str = "reports"):
        # 防止重复初始化
        if self._initialized:
            logger.debug("调度器已初始化，跳过重复初始化")
            return
            
        self.scheduler = None
        self.host_monitor = HostMonitor()
        self.report_generator = ReportGenerator(report_dir)
        self.database_url = database_url or 'sqlite:///host_monitor.db'
        self._setup_scheduler()
        self._initialized = True
    
    @classmethod
    def get_instance(cls, database_url: Optional[str] = None, report_dir: str = "reports"):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(database_url, report_dir)
        return cls._instance
    
    def _setup_scheduler(self):
        """设置调度器"""
        try:
            logger.info(f"开始初始化调度器，数据库URL: {self.database_url}")
            
            # 配置作业存储
            jobstores = {
                'default': SQLAlchemyJobStore(url=self.database_url)
            }
            
            # 配置执行器
            executors = {
                'default': ThreadPoolExecutor(20),
            }
            
            # 作业默认设置
            job_defaults = {
                'coalesce': False,
                'max_instances': 3
            }
            
            # 创建调度器
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='Asia/Shanghai'
            )
            
            logger.info("调度器初始化成功")
            
        except Exception as e:
            logger.error(f"调度器初始化失败: {str(e)}")
            import traceback
            logger.error(f"调度器初始化错误详情: {traceback.format_exc()}")
            # 不抛出异常，允许应用继续运行
            self.scheduler = None
    
    def start_scheduler(self):
        """启动调度器"""
        try:
            if not self.scheduler:
                logger.error("调度器未初始化，无法启动")
                # 尝试重新初始化
                logger.info("尝试重新初始化调度器")
                self._setup_scheduler()
                if not self.scheduler:
                    logger.error("重新初始化调度器失败")
                    return False
                
            if not self.scheduler.running:
                logger.info("启动调度器中...")
                self.scheduler.start()
                logger.info(f"调度器已启动，状态: {self.scheduler.running}")
                
                # 加载数据库中的计划任务
                self.load_tasks_from_database()
                return True
            else:
                logger.info("调度器已经在运行")
                return True
        except Exception as e:
            logger.error(f"启动调度器失败: {str(e)}")
            import traceback
            logger.error(f"启动调度器错误详情: {traceback.format_exc()}")
            return False
    
    def stop_scheduler(self):
        """停止调度器"""
        try:
            if not self.scheduler:
                logger.debug("调度器未初始化，无需停止")
                return
                
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("调度器已停止")
            else:
                logger.debug("调度器未运行，无需停止")
        except Exception as e:
            logger.error(f"停止调度器失败: {str(e)}")
    
    def load_tasks_from_database(self):
        """从数据库加载计划任务"""
        try:
            active_tasks = ScheduleTask.query.filter_by(is_active=True).all()
            
            for task in active_tasks:
                try:
                    self._add_job_to_scheduler(task)
                    logger.info(f"加载计划任务: {task.name}")
                except Exception as e:
                    logger.error(f"加载计划任务 {task.name} 失败: {str(e)}")
            
            logger.info(f"从数据库加载了 {len(active_tasks)} 个计划任务")
            
        except Exception as e:
            logger.error(f"从数据库加载计划任务失败: {str(e)}")
    
    def _add_job_to_scheduler(self, task: ScheduleTask):
        """将任务添加到调度器"""
        try:
            if not self.scheduler:
                logger.error("调度器未初始化，无法添加任务")
                return
                
            config = task.get_schedule_config()
            logger.info(f"正在添加任务 {task.name}，类型: {task.task_type}，配置: {config}")
            
            trigger = self._create_trigger(task.task_type, config)
            
            if trigger:
                job_id = f"task_{task.id}"
                
                # 安全移除已存在的作业
                try:
                    if self.scheduler.get_job(job_id):
                        self.scheduler.remove_job(job_id)
                        logger.info(f"移除已存在的任务: {job_id}")
                except Exception as e:
                    # 忽略任务不存在的错误
                    logger.debug(f"移除任务时出现错误（可忽略）: {str(e)}")
                
                # 添加新作业
                self.scheduler.add_job(
                    func=execute_monitor_task_static,
                    trigger=trigger,
                    id=job_id,
                    name=task.name,
                    args=[task.id, self.database_url, self.report_generator.report_dir],
                    replace_existing=True
                )
                
                # 更新下次执行时间
                job = self.scheduler.get_job(job_id)
                if job and job.next_run_time:
                    # 将UTC时间转换为本地时间
                    from datetime import timezone, timedelta
                    china_tz = timezone(timedelta(hours=8))
                    next_run_local = job.next_run_time.astimezone(china_tz).replace(tzinfo=None)
                    task.next_run = next_run_local
                    db.session.commit()
                    logger.info(f"任务 {task.name} 下次执行时间: {job.next_run_time}")
                
                logger.info(f"任务 {task.name} 已成功添加到调度器")
            else:
                logger.error(f"无法为任务 {task.name} 创建触发器，类型: {task.task_type}，配置: {config}")
                
        except Exception as e:
            logger.error(f"添加任务到调度器失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _create_trigger(self, task_type: str, config: Dict[str, Any]):
        """创建触发器"""
        try:
            if task_type == 'daily':
                # 每日执行
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return CronTrigger(hour=hour, minute=minute)
            
            elif task_type == 'weekly':
                # 每周执行
                day_of_week = config.get('day_of_week', 0)  # 0=周一, 6=周日
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
            
            elif task_type == 'monthly':
                # 每月执行
                day = config.get('day', 1)  # 月中的某一天
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return CronTrigger(day=day, hour=hour, minute=minute)
            
            elif task_type == 'interval':
                # 间隔执行
                interval_type = config.get('interval_type', 'hours')  # hours, minutes, days
                interval_value = config.get('interval_value', 1)
                
                if interval_type == 'hours':
                    return IntervalTrigger(hours=interval_value)
                elif interval_type == 'minutes':
                    return IntervalTrigger(minutes=interval_value)
                elif interval_type == 'days':
                    return IntervalTrigger(days=interval_value)
            
            elif task_type == 'cron':
                # 自定义cron表达式
                cron_expr = config.get('cron_expression', '0 0 * * *')
                # 解析cron表达式
                parts = cron_expr.split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    return CronTrigger(
                        minute=minute if minute != '*' else None,
                        hour=hour if hour != '*' else None,
                        day=day if day != '*' else None,
                        month=month if month != '*' else None,
                        day_of_week=day_of_week if day_of_week != '*' else None
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"创建触发器失败: {str(e)}")
            return None
    
    def _execute_monitor_task(self, task_id: int):
        """执行监控任务"""
        logger.info(f"开始执行计划任务 ID: {task_id}")
        
        try:
            # 使用新的数据库会话防止线程问题
            from app.models import db, ScheduleTask, MonitorReport
            
            # 更新任务最后执行时间和下次执行时间
            task = ScheduleTask.query.get(task_id)
            if not task:
                logger.error(f"任务 ID {task_id} 不存在")
                return
            
            task.last_run = datetime.now()
            
            # 更新下次执行时间
            job_id = f"task_{task_id}"
            if self.scheduler and self.scheduler.running:
                job = self.scheduler.get_job(job_id)
                if job and job.next_run_time:
                    # 将UTC时间转换为本地时间
                    from datetime import timezone, timedelta
                    # 中国时区 UTC+8
                    china_tz = timezone(timedelta(hours=8))
                    next_run_local = job.next_run_time.astimezone(china_tz).replace(tzinfo=None)
                    task.next_run = next_run_local
                    logger.info(f"任务 {task.name} 下次执行时间更新为: {task.next_run}")
            
            db.session.commit()
            
            logger.info(f"开始执行计划任务: {task.name}")
            
            # 执行监控
            monitor_result = self.host_monitor.monitor_all_servers()
            
            logger.info(f"监控完成，结果: 总数={monitor_result['total_servers']}, 成功={monitor_result['success_count']}, 告警={monitor_result['warning_count']}, 失败={monitor_result['failed_count']}")
            
            # 生成报告
            report_name = f"scheduled_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            report_path = self.report_generator.generate_html_report(
                monitor_result, 
                report_name
            )
            
            # 保存报告记录
            if report_path:
                report = MonitorReport(
                    report_name=report_name,
                    report_type='scheduled',
                    report_path=report_path,
                    server_count=monitor_result['total_servers'],
                    success_count=monitor_result['success_count'],
                    failed_count=monitor_result['failed_count'],
                    warning_count=monitor_result['warning_count']
                )
                db.session.add(report)
                db.session.commit()
                logger.info(f"报告保存成功: {report_path}")
            
            # 发送通知
            notification_success = False
            notification_message = ""
            try:
                from app.notification_service import NotificationService
                notification_service = NotificationService()
                notification_success, notification_message = notification_service.send_notification(monitor_result, report_path)
                logger.info(f"计划任务通知发送结果: {notification_message}")
            except Exception as notify_error:
                logger.error(f"计划任务发送通知失败: {str(notify_error)}")
                notification_message = f"通知发送失败: {str(notify_error)}"
            
            logger.info(f"计划任务 {task.name} 执行完成")
            
        except Exception as e:
            logger.error(f"执行计划任务失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            try:
                db.session.rollback()
            except:
                pass
    
    def create_schedule_task(self, task_data: Dict[str, Any]) -> Tuple[bool, str, Optional[ScheduleTask]]:
        """
        创建计划任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            (success, message, task)
        """
        try:
            # 验证必填字段
            if not task_data.get('name'):
                return False, "任务名称不能为空", None
            
            if not task_data.get('task_type'):
                return False, "任务类型不能为空", None
            
            # 检查任务名称是否已存在
            existing_task = ScheduleTask.query.filter_by(name=task_data['name']).first()
            if existing_task:
                return False, "任务名称已存在", None
            
            # 验证调度配置
            schedule_config = task_data.get('schedule_config', {})
            if not self._validate_schedule_config(task_data['task_type'], schedule_config):
                return False, "调度配置无效", None
            
            # 创建任务
            task = ScheduleTask(
                name=task_data['name'],
                task_type=task_data['task_type'],
                is_active=task_data.get('is_active', True)
            )
            task.set_schedule_config(schedule_config)
            
            db.session.add(task)
            db.session.commit()
            
            # 如果任务是激活状态，添加到调度器
            if task.is_active and self.scheduler and self.scheduler.running:
                self._add_job_to_scheduler(task)
            
            logger.info(f"计划任务创建成功: {task.name}")
            return True, "计划任务创建成功", task
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建计划任务失败: {str(e)}")
            return False, f"创建计划任务失败: {str(e)}", None
    
    def _validate_schedule_config(self, task_type: str, config: Dict[str, Any]) -> bool:
        """验证调度配置"""
        try:
            if task_type == 'daily':
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return 0 <= hour <= 23 and 0 <= minute <= 59
            
            elif task_type == 'weekly':
                day_of_week = config.get('day_of_week', 0)
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return (0 <= day_of_week <= 6 and 
                       0 <= hour <= 23 and 
                       0 <= minute <= 59)
            
            elif task_type == 'monthly':
                day = config.get('day', 1)
                hour = config.get('hour', 0)
                minute = config.get('minute', 0)
                return (1 <= day <= 31 and 
                       0 <= hour <= 23 and 
                       0 <= minute <= 59)
            
            elif task_type == 'interval':
                interval_type = config.get('interval_type', 'hours')
                interval_value = config.get('interval_value', 1)
                return (interval_type in ['hours', 'minutes', 'days'] and 
                       interval_value > 0)
            
            elif task_type == 'cron':
                cron_expr = config.get('cron_expression', '')
                parts = cron_expr.split()
                return len(parts) == 5
            
            return False
            
        except Exception:
            return False
    
    def update_schedule_task(self, task_id: int, task_data: Dict[str, Any]) -> Tuple[bool, str, Optional[ScheduleTask]]:
        """
        更新计划任务
        
        Args:
            task_id: 任务ID
            task_data: 更新的任务数据
            
        Returns:
            (success, message, task)
        """
        try:
            task = ScheduleTask.query.get(task_id)
            if not task:
                return False, "任务不存在", None
            
            # 检查任务名称冲突
            if 'name' in task_data and task_data['name'] != task.name:
                existing_task = ScheduleTask.query.filter_by(name=task_data['name']).first()
                if existing_task:
                    return False, "任务名称已存在", None
            
            # 更新字段
            if 'name' in task_data:
                task.name = task_data['name']
            if 'task_type' in task_data:
                task.task_type = task_data['task_type']
            if 'is_active' in task_data:
                task.is_active = task_data['is_active']
            if 'schedule_config' in task_data:
                if self._validate_schedule_config(task.task_type, task_data['schedule_config']):
                    task.set_schedule_config(task_data['schedule_config'])
                else:
                    return False, "调度配置无效", None
            
            db.session.commit()
            
            # 更新调度器中的任务
            if self.scheduler and self.scheduler.running:
                job_id = f"task_{task.id}"
                
                # 移除旧任务
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                
                # 如果任务激活，重新添加
                if task.is_active:
                    self._add_job_to_scheduler(task)
            
            logger.info(f"计划任务更新成功: {task.name}")
            return True, "计划任务更新成功", task
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新计划任务失败: {str(e)}")
            return False, f"更新计划任务失败: {str(e)}", None
    
    def delete_schedule_task(self, task_id: int) -> Tuple[bool, str]:
        """
        删除计划任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            (success, message)
        """
        try:
            task = ScheduleTask.query.get(task_id)
            if not task:
                return False, "任务不存在"
            
            task_name = task.name
            
            # 从调度器中移除任务
            if self.scheduler and self.scheduler.running:
                job_id = f"task_{task.id}"
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
            
            # 从数据库删除
            db.session.delete(task)
            db.session.commit()
            
            logger.info(f"计划任务删除成功: {task_name}")
            return True, "计划任务删除成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"删除计划任务失败: {str(e)}")
            return False, f"删除计划任务失败: {str(e)}"
    
    def get_task_list(self) -> List[Dict[str, Any]]:
        """获取任务列表"""
        try:
            tasks = ScheduleTask.query.order_by(ScheduleTask.created_at.desc()).all()
            
            task_list = []
            for task in tasks:
                task_dict = task.to_dict()
                
                # 添加调度器状态信息
                if self.scheduler and self.scheduler.running:
                    job_id = f"task_{task.id}"
                    job = self.scheduler.get_job(job_id)
                    if job:
                        task_dict['scheduler_status'] = 'running'
                        task_dict['next_run_time'] = job.next_run_time.isoformat() if job.next_run_time else None
                    else:
                        task_dict['scheduler_status'] = 'stopped'
                        task_dict['next_run_time'] = None
                else:
                    task_dict['scheduler_status'] = 'scheduler_not_running'
                    task_dict['next_run_time'] = None
                
                task_list.append(task_dict)
            
            return task_list
            
        except Exception as e:
            logger.error(f"获取任务列表失败: {str(e)}")
            return []
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        try:
            if not self.scheduler:
                return {
                    'running': False,
                    'jobs_count': 0,
                    'jobs': []
                }
            
            jobs = []
            if self.scheduler.running:
                for job in self.scheduler.get_jobs():
                    jobs.append({
                        'id': job.id,
                        'name': job.name,
                        'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                        'trigger': str(job.trigger)
                    })
            
            return {
                'running': self.scheduler.running,
                'jobs_count': len(jobs),
                'jobs': jobs
            }
            
        except Exception as e:
            logger.error(f"获取调度器状态失败: {str(e)}")
            return {
                'running': False,
                'jobs_count': 0,
                'jobs': []
            }