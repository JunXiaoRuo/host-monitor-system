#!/usr/bin/env python3
"""
主机巡视系统 - 密码重置工具

使用方法:
python reset_password.py <用户名> <新密码>

示例:
python reset_password.py admin newpassword123
"""

import sys
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime

def get_db_path():
    """获取数据库路径（与Flask应用保持一致）"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 先尝试从环境变量获取数据库URL
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('sqlite:///'):
        # 从 SQLite URL 中提取数据库文件路径
        db_file = database_url.replace('sqlite:///', '')
        if not os.path.isabs(db_file):
            return os.path.join(current_dir, db_file)
        return db_file
    
    # 使用默认配置
    return os.path.join(current_dir, 'host_monitor.db')

def hash_password(password, salt):
    """计算密码哈希"""
    return hashlib.sha256((password + salt).encode()).hexdigest()

def list_users_with_flask():
    """使用Flask应用上下文查询用户（推荐方法）"""
    try:
        # 导入Flask应用
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import create_app
        from app.models import AdminUser
        
        app = create_app()
        
        with app.app_context():
            users = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
            
            if not users:
                print("没有找到任何用户")
                return True
            
            print("\n现有用户列表:")
            print("-" * 70)
            id_header = "ID"
            username_header = "用户名"
            status_header = "状态"
            last_login_header = "最后登录"
            created_header = "创建时间"
            print(f"{id_header:<5} {username_header:<15} {status_header:<8} {last_login_header:<20} {created_header:<20}")
            print("-" * 70)
            
            for user in users:
                status = "激活" if user.is_active else "禁用"
                last_login_str = user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else "从未登录"
                created_at_str = user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else "未知"
                
                print(f"{user.id:<5} {user.username:<15} {status:<8} {last_login_str:<20} {created_at_str:<20}")
            
            print("-" * 70)
            return True
            
    except ImportError as e:
        print(f"错误: 无法导入Flask应用: {e}")
        print("正在使用直接数据库查询方式...")
        return False
    except Exception as e:
        print(f"使用Flask应用查询用户时发生错误: {e}")
        print("正在使用直接数据库查询方式...")
        return False

def reset_password_with_flask(username, new_password):
    """使用Flask应用上下文重置密码（推荐方法）"""
    try:
        # 导入Flask应用
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import create_app
        from app.models import db, AdminUser
        from app.auth_service import AuthService
        
        app = create_app()
        
        with app.app_context():
            # 检查用户是否存在
            user = AdminUser.query.filter_by(username=username).first()
            
            if not user:
                print(f"错误: 用户 '{username}' 不存在")
                return False
            
            # 使用AuthService重置密码
            auth_service = AuthService()
            success, message = auth_service.reset_password(username, new_password)
            
            if success:
                print(f"✓ 用户 '{username}' 的密码已成功重置")
                print(f"✓ 用户已设置为激活状态")
                return True
            else:
                print(f"错误: {message}")
                return False
            
    except ImportError as e:
        print(f"错误: 无法导入Flask应用: {e}")
        print("正在使用直接数据库操作方式...")
        return False
    except Exception as e:
        print(f"使用Flask应用重置密码时发生错误: {e}")
        print("正在使用直接数据库操作方式...")
        return False

def check_and_create_tables():
    """检查并创建必要的数据库表"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 - {db_path}")
        print("请先启动一次主机巡视系统来初始化数据库")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查admin_users表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='admin_users'
        """)
        
        if not cursor.fetchone():
            print("检测到admin_users表不存在，正在创建...")
            
            # 创建admin_users表
            cursor.execute("""
                CREATE TABLE admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    salt VARCHAR(32) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_login DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
            """)
            
            conn.commit()
            print("✓ admin_users表创建成功")
        
        return True
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"检查数据库时发生错误: {e}")
        return False
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass

def reset_password(username, new_password):
    """重置用户密码"""
    # 先检查并创建表
    if not check_and_create_tables():
        return False
    
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 - {db_path}")
        print("请确保在项目根目录下运行此脚本")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查用户是否存在
        cursor.execute("SELECT id, username FROM admin_users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            print(f"错误: 用户 '{username}' 不存在")
            return False
        
        user_id, found_username = user
        
        # 生成新的盐值和密码哈希
        salt = secrets.token_hex(16)
        password_hash = hash_password(new_password, salt)
        
        # 更新密码
        cursor.execute("""
            UPDATE admin_users 
            SET password_hash = ?, salt = ?, updated_at = ?, is_active = 1
            WHERE id = ?
        """, (password_hash, salt, datetime.now().isoformat(), user_id))
        
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"✓ 用户 '{username}' 的密码已成功重置")
            print(f"✓ 用户已设置为激活状态")
            return True
        else:
            print(f"错误: 密码重置失败")
            return False
            
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"重置密码时发生错误: {e}")
        return False
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass

def list_users():
    """列出所有用户"""
    # 先检查并创建表
    if not check_and_create_tables():
        return False
    
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 - {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT username, is_active, last_login, created_at 
            FROM admin_users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("没有找到任何用户")
            return True
        
        print("\n现有用户列表:")
        print("-" * 70)
        print(f"{'用户名':<15} {'状态':<8} {'最后登录':<20} {'创建时间':<20}")
        print("-" * 70)
        
        for username, is_active, last_login, created_at in users:
            status = "激活" if is_active else "禁用"
            last_login_str = last_login[:19] if last_login else "从未登录"
            created_at_str = created_at[:19] if created_at else "未知"
            
            print(f"{username:<15} {status:<8} {last_login_str:<20} {created_at_str:<20}")
        
        print("-" * 70)
        return True
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        return False
    except Exception as e:
        print(f"列出用户时发生错误: {e}")
        return False
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass

def show_help():
    """显示帮助信息"""
    print("主机巡视系统 - 密码重置工具")
    print("=" * 50)
    print()
    print("使用方法:")
    print("  python reset_password.py <用户名> <新密码>    # 重置密码")
    print("  python reset_password.py --list             # 列出所有用户")
    print("  python reset_password.py --help             # 显示帮助")
    print()
    print("示例:")
    print("  python reset_password.py admin newpassword123")
    print("  python reset_password.py user1 mysecret456")
    print()
    print("注意:")
    print("  - 请在项目根目录下运行此脚本")
    print("  - 密码建议至少8位，包含字母和数字")
    print("  - 重置后的用户会自动设置为激活状态")
    print()

def validate_password(password):
    """验证密码强度"""
    if len(password) < 8:
        print("警告: 密码长度少于8位，建议使用更强的密码")
        return False
    
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not has_letter or not has_digit:
        print("警告: 密码建议包含字母和数字")
        return False
    
    return True

def main():
    """主函数"""
    args = sys.argv[1:]
    
    if not args or args[0] in ['--help', '-h', 'help']:
        show_help()
        return
    
    if args[0] == '--list':
        # 优先尝试使用Flask应用方式
        if not list_users_with_flask():
            # 如果失败，使用直接数据库方式
            list_users()
        return
    
    if len(args) != 2:
        print("错误: 参数数量不正确")
        print("使用 'python reset_password.py --help' 查看帮助")
        return
    
    username = args[0].strip()
    new_password = args[1]
    
    if not username:
        print("错误: 用户名不能为空")
        return
    
    if not new_password:
        print("错误: 密码不能为空")
        return
    
    # 验证密码强度
    validate_password(new_password)
    
    # 确认操作
    print(f"即将重置用户 '{username}' 的密码")
    confirm = input("确认继续? (y/N): ").strip().lower()
    
    if confirm not in ['y', 'yes']:
        print("操作已取消")
        return
    
    # 执行密码重置
    # 优先尝试使用Flask应用方式
    success = reset_password_with_flask(username, new_password)
    
    if not success:
        # 如果失败，使用直接数据库方式
        success = reset_password(username, new_password)
    
    if success:
        print("\n密码重置完成!")
        print("现在可以使用新密码登录系统了")
    else:
        print("\n密码重置失败!")
        sys.exit(1)

if __name__ == "__main__":
    main()