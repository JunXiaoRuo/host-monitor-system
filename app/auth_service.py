"""
认证服务模块
负责管理员账户的创建、验证、登录等功能
"""

import os
import secrets
from datetime import datetime, timedelta
from flask import session
from app.models import db, AdminUser
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """认证服务类"""
    
    def __init__(self):
        self.session_timeout = 24 * 60 * 60  # 24小时session超时时间
    
    def has_admin_user(self):
        """检查是否已存在管理员账户"""
        try:
            return AdminUser.query.filter_by(is_active=True).first() is not None
        except Exception as e:
            logger.error(f"检查管理员账户失败: {str(e)}")
            return False
    
    def create_admin_user(self, username, password):
        """创建管理员账户"""
        try:
            # 检查用户名是否已存在
            existing_user = AdminUser.query.filter_by(username=username).first()
            if existing_user:
                return False, "用户名已存在"
            
            # 创建新用户
            admin_user = AdminUser(username=username)
            admin_user.set_password(password)
            
            db.session.add(admin_user)
            db.session.commit()
            
            logger.info(f"管理员账户创建成功: {username}")
            return True, "管理员账户创建成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建管理员账户失败: {str(e)}")
            return False, f"创建管理员账户失败: {str(e)}"
    
    def authenticate(self, username, password):
        """验证用户登录"""
        try:
            user = AdminUser.query.filter_by(username=username, is_active=True).first()
            
            if not user:
                logger.warning(f"登录失败：用户不存在或已禁用 - {username}")
                return False, None, "用户名或密码错误"
            
            if not user.check_password(password):
                logger.warning(f"登录失败：密码错误 - {username}")
                return False, None, "用户名或密码错误"
            
            # 更新最后登录时间
            user.last_login = datetime.now()
            db.session.commit()
            
            logger.info(f"用户登录成功: {username}")
            return True, user, "登录成功"
            
        except Exception as e:
            logger.error(f"用户认证失败: {str(e)}")
            return False, None, f"认证失败: {str(e)}"
    
    def login_user(self, user):
        """用户登录，设置session"""
        try:
            session['user_id'] = user.id
            session['username'] = user.username
            session['login_time'] = datetime.now().isoformat()
            session['session_token'] = secrets.token_hex(16)
            session.permanent = True
            
            logger.info(f"用户session创建成功: {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"创建用户session失败: {str(e)}")
            return False
    
    def logout_user(self):
        """用户登出，清除session"""
        try:
            username = session.get('username', 'Unknown')
            session.clear()
            logger.info(f"用户登出成功: {username}")
            return True
            
        except Exception as e:
            logger.error(f"用户登出失败: {str(e)}")
            return False
    
    def is_logged_in(self):
        """检查用户是否已登录"""
        try:
            if 'user_id' not in session or 'login_time' not in session:
                return False
            
            # 检查session是否过期
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(seconds=self.session_timeout):
                self.logout_user()
                return False
            
            # 检查用户是否仍然存在且激活
            user = AdminUser.query.filter_by(
                id=session['user_id'], 
                is_active=True
            ).first()
            
            if not user:
                self.logout_user()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {str(e)}")
            return False
    
    def get_current_user(self):
        """获取当前登录用户"""
        try:
            if not self.is_logged_in():
                return None
            
            user = AdminUser.query.filter_by(
                id=session['user_id'],
                is_active=True
            ).first()
            
            return user
            
        except Exception as e:
            logger.error(f"获取当前用户失败: {str(e)}")
            return None
    
    def change_password(self, username, old_password, new_password):
        """修改密码"""
        try:
            user = AdminUser.query.filter_by(username=username, is_active=True).first()
            
            if not user:
                return False, "用户不存在"
            
            if not user.check_password(old_password):
                return False, "原密码错误"
            
            user.set_password(new_password)
            user.updated_at = datetime.now()
            db.session.commit()
            
            logger.info(f"用户密码修改成功: {username}")
            return True, "密码修改成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"修改密码失败: {str(e)}")
            return False, f"修改密码失败: {str(e)}"
    
    def reset_password(self, username, new_password):
        """重置密码（用于命令行工具）"""
        try:
            user = AdminUser.query.filter_by(username=username).first()
            
            if not user:
                return False, "用户不存在"
            
            user.set_password(new_password)
            user.updated_at = datetime.now()
            user.is_active = True  # 确保用户是激活状态
            db.session.commit()
            
            logger.info(f"用户密码重置成功: {username}")
            return True, "密码重置成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"重置密码失败: {str(e)}")
            return False, f"重置密码失败: {str(e)}"
    
    def get_all_users(self):
        """获取所有用户列表"""
        try:
            users = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
            return [user.to_dict() for user in users]
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}")
            return []
    
    def toggle_user_status(self, user_id, is_active):
        """切换用户激活状态"""
        try:
            user = AdminUser.query.get(user_id)
            
            if not user:
                return False, "用户不存在"
            
            user.is_active = is_active
            user.updated_at = datetime.now()
            db.session.commit()
            
            status_text = "激活" if is_active else "禁用"
            logger.info(f"用户状态修改成功: {user.username} - {status_text}")
            return True, f"用户已{status_text}"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"修改用户状态失败: {str(e)}")
            return False, f"修改用户状态失败: {str(e)}"