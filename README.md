# 主机巡视系统

一个功能完整的基于Web的服务器监控平台，提供实时监控、自动化巡检、告警通知和报告生成等功能。

## 🌟 系统概述

主机巡视系统是专为系统管理员和运维人员设计的监控平台，通过SSH连接收集服务器的关键性能指标，支持多服务器并发监控，提供直观的Web界面和完善的报告机制。

### 核心特性

- 🖥️ **多服务器管理**: 支持SSH连接的服务器增删改查，密码和私钥双重认证
- 📊 **实时性能监控**: CPU、内存、磁盘使用率实时监控，可配置告警阈值
- 🔧 **服务进程监控**: 监控指定服务进程状态，支持自定义进程名称
- ⏰ **智能任务调度**: 支持每日、每周、每月等多种自动调度方式
- 📋 **详细监控报告**: 生成HTML格式监控报告，支持历史数据查询
- 🔔 **多渠道通知**: 支持Webhook通知，可推送到企业微信、钉钉等
- 📈 **完整历史记录**: 监控历史、执行日志、系统状态变化记录
- 🔐 **安全认证机制**: 管理员登录认证，密码加密存储，会话管理
- 🎯 **响应式界面**: Bootstrap构建的现代化响应式Web界面
- 🚀 **高并发处理**: 多线程并发监控，提高监控效率

## 📋 系统要求

### 运行环境
- **Python版本**: 3.8
- **操作系统**: Windows/Linux/macOS
- **网络要求**: 能够SSH连接到被监控服务器
- **端口要求**: 5000（默认Web端口，可配置）
- **存储空间**: 至少100MB（用于数据库、日志和报告）

### 被监控服务器要求
- SSH服务正常运行
- 监控用户具有执行系统命令的权限
- 支持标准Linux/Unix命令（top、free、df等）

## 🛠️ 快速开始

### 1. 环境准备

```bash
# 克隆项目（如果从Git获取）
git clone https://github.com/JunXiaoRuo/host-monitor-system
cd 主机巡视

# 或直接解压项目包到目录
```

### 2. 环境配置

```bash
# 复制环境配置模板
cp .env.example .env

# 编辑.env文件，修改相关配置
# 重要：修改SECRET_KEY和ENCRYPTION_KEY为强密码
# 密钥生成命令：python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**必要的配置项**：
- `SECRET_KEY`: Flask应用的安全密钥
- `ENCRYPTION_KEY`: 数据加密密钥
- `HOST`: 监听IP地址（默认0.0.0.0）
- `PORT`: 监听端口（默认5000）


### 3. 安装依赖

```bash
# 安装Python依赖包
pip install -r requirements.txt
```

### 4. 启动系统

```bash
# 快速启动脚本
windows用户双击start.bat
macOS/Linux用户执行start.sh

# 开发环境启动
python run.py

# 生产环境启动
python start_production.py
```

### 5. 系统初始化

1. 浏览器访问: `http://localhost:5000`
2. 首次访问会自动跳转到初始化页面
3. 创建管理员账户：
   - 用户名：3-20位字符（字母、数字、下划线）
   - 密码：至少8位，建议包含字母和数字
4. 登录系统开始使用

## 🌐 内网离线部署

对于无法连接外网的内网环境，系统提供了完整的离线部署方案。

### 在有网络的机器上准备依赖包

#### 方式一：使用自动化脚本（推荐）

```bash
# 运行依赖包下载脚本
python quick_prepare.py
```

#### 方式二：使用批处理脚本

```bash
# Windows环境
double-click download_packages.bat

# 或手动执行
pip download -r requirements.txt --dest python-packages
```

#### 方式三：手动下载主要依赖

```bash
# 创建依赖包目录
mkdir python-packages

# 下载主要依赖包
pip download Flask==2.3.3 Flask-SQLAlchemy==3.0.5 paramiko==3.3.1 APScheduler==3.10.4 Jinja2==3.1.2 Werkzeug==2.3.7 cryptography==41.0.4 psutil==5.9.6 requests==2.31.0 python-dotenv==1.0.0 pandas==2.0.3 openpyxl==3.1.2 --dest python-packages
```

### 在内网机器上部署

#### 1. 传输文件
将整个项目文件夹（包含python-packages目录）复制到内网机器。

#### 2. 离线安装依赖

```bash
# Windows环境：双击运行
install_offline.bat

# Linux/Mac环境
pip install --no-index --find-links python-packages -r requirements.txt
```

#### 3. 配置和启动

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置（如果需要）
vim .env

# 启动服务
python run.py
```

### 离线部署验证

1. **检查依赖安装**：
   ```bash
   python -c "import flask; print('Flask:', flask.__version__)"
   python -c "import paramiko; print('Paramiko 已安装')"
   python -c "import pandas; print('Pandas 已安装')"
   ```

2. **访问系统**：浏览器打开 `http://localhost:5000`

3. **功能测试**：登录后添加测试服务器，执行监控验证

### 离线部署注意事项

- **Python版本**：内网机器需要预装Python 3.8+
- **端口检查**：确保5000端口未被占用
- **权限设置**：确保有文件读写权限
- **依赖完整性**：确保python-packages目录包含所有.whl文件

### 离线部署故障排除

1. **pip不是内部命令**：
   - 重新安装Python，勾选"Add Python to PATH"
   - 手动添加Python路径到环境变量

2. **依赖安装失败**：
   ```bash
   # 重新下载依赖包
   pip download -r requirements.txt --dest python-packages --force-reinstall
   
   # 手动安装主要包
   pip install python-packages/*.whl --force-reinstall
   ```

3. **权限问题**：
   ```bash
   # Linux/Mac环境
   chmod 755 install_offline.sh
   chmod -R 755 python-packages/
   ```

## 🔑 密码管理

### 重置管理员密码

如果忘记密码，使用命令行工具重置：

```bash
# 查看所有用户
python reset_password.py --list

# 重置密码
python reset_password.py <用户名> <新密码>

# 示例
python reset_password.py admin newpassword123
```

### 密码要求

- 最低长度：8位
- 建议组合：字母 + 数字
- 避免简单密码如：12345678

## 🔧 系统配置

### 技术架构

- **前端**: Bootstrap + JavaScript (响应式界面)
- **后端**: Flask + SQLAlchemy
- **数据库**: SQLite (轻量级，无需额外配置)
- **任务调度**: APScheduler
- **SSH连接**: paramiko
- **加密**: cryptography (密码加密存储)

### 目录结构

```
主机巡视/
├── app/                          # 应用核心模块
│   ├── __init__.py              # Flask应用工厂和路由定义
│   ├── models.py                # 数据库模型定义
│   ├── auth_service.py          # 用户认证服务
│   ├── monitor.py               # 主机监控核心逻辑
│   ├── service_monitor.py       # 服务进程监控功能
│   ├── services.py              # 业务逻辑服务层
│   ├── scheduler.py             # 任务调度器服务
│   ├── ssh_manager.py           # SSH连接管理器
│   ├── notification_service.py  # 通知推送服务
│   ├── report_generator.py      # 监控报告生成器
│   └── batch_import_service.py  # 批量导入服务
├── templates/                   # HTML模板文件
│   ├── index.html              # 主页面模板（包含所有功能面板）
│   ├── login.html              # 登录页面模板
│   └── setup.html              # 初始化设置页面
├── static/                      # 静态资源文件
│   └── js/
│       └── main.js             # 主要JavaScript逻辑
├── instance/                    # Flask实例配置目录
│   └── host_monitor.db         # SQLite数据库文件
├── reports/                     # 生成的监控报告
│   ├── manual_report_*.html    # 手动执行的监控报告
│   ├── scheduled_report_*.html # 计划任务生成的报告
│   └── *.html                  # 其他监控报告文件
├── logs/                        # 系统日志目录
│   ├── flask.log               # Flask应用日志
│   ├── flask-error.log         # Flask应用错误日志
│   ├── run.log                 # 开发环境运行日志
│   ├── run-error.log           # 开发环境错误日志
│   ├── production.log          # 生产环境运行日志
│   └── production-error.log    # 生产环境错误日志
├── python-packages/             # 离线部署依赖包目录（运行quick_prepare.py后生成）
│   └── *.whl                   # Python依赖包文件
├── config.py                    # 应用配置文件
├── log_config.py                # 日志配置文件
├── requirements.txt             # Python依赖包列表
├── quick_prepare.py             # 离线部署依赖包准备脚本
├── install_offline.bat          # 内网环境离线安装脚本
├── .env                         # 环境配置文件（包含敏感信息）
├── .env.example                 # 环境配置模板
├── .gitignore                   # Git忽略文件配置
├── run.py                       # 开发环境启动脚本
├── start_production.py         # 生产环境启动脚本
├── reset_password.py           # 管理员密码重置工具
├── app_simple.py               # 简化版应用启动器
├── start.bat                   # Windows启动脚本
├── start.sh                    # Linux/Mac启动脚本
├── README.md                   # 项目说明文档
└── LICENSE                     # 开源许可证文件
```

### 文件功能说明

**核心模块 (app/)**:
- **`__init__.py`**: Flask应用工厂，包含所有路由定义和API接口
- **`models.py`**: 数据库模型定义，包含10个核心数据表
- **`monitor.py`**: 主机监控核心功能，CPU/内存/磁盘监控
- **`service_monitor.py`**: 服务进程监控功能，支持自定义进程名监控
- **`scheduler.py`**: 任务调度器，支持每日/每周/每月计划任务
- **`auth_service.py`**: 用户认证服务，密码加密和会话管理
- **`notification_service.py`**: 通知推送服务，支持Webhook通知
- **`report_generator.py`**: 监控报告生成器，生成HTML格式报告
- **`ssh_manager.py`**: SSH连接管理器，支持密码和私钥认证
- **`services.py`**: 业务逻辑服务层，封装数据库操作
- **`batch_import_service.py`**: 批量导入服务，支持服务器和服务配置批量导入

**前端文件**:
- **`templates/index.html`**: 主页面模板，包含所有功能面板（含服务配置）
- **`templates/login.html`**: 用户登录页面
- **`templates/setup.html`**: 系统初始化设置页面
- **`static/js/main.js`**: 前端主JavaScript逻辑

**配置文件**:
- **`config.py`**: 应用主配置，支持从环境变量读取配置
- **`log_config.py`**: 日志系统配置，支持按天分割和智能轮转
- **`.env`**: 环境配置文件，包含敏感信息（密钥、数据库、端口等）
- **`.env.example`**: 环境配置模板，不包含敏感信息
- **`.gitignore`**: Git忽略文件配置，排除敏感文件
- **`requirements.txt`**: Python依赖包列表，新增python-dotenv支持

**启动脚本**:
- **`run.py`**: 开发环境启动脚本，支持从.env读取配置
- **`start_production.py`**: 生产环境启动脚本，支持后台运行
- **`app_simple.py`**: 简化版启动器，用于测试和调试
- **`start.bat`**: Windows启动脚本，支持交互式选择运行模式
- **`start.sh`**: Linux/Mac启动脚本，支持交互式选择运行模式

**工具脚本**:
- **`reset_password.py`**: 管理员密码重置工具，支持用户列表和密码修改

**系统文件**:
- **`instance/host_monitor.db`**: SQLite数据库，存储所有系统数据
- **`logs/`**: 系统日志目录，按天分割存储，支持错误日志分离
- **`reports/`**: 监控报告存储目录，支持手动和自动报告生成

### 配置文件

**环境配置 (.env)**:
系统使用`.env`文件管理所有环境配置和敏感信息：

```bash
# 复制模板文件
cp .env.example .env

# 编辑.env文件
vim .env  # 或使用其他编辑器
```

**主要配置项**:

| 配置项 | 默认值 | 说明 |
|---------|---------|--------|
| `SECRET_KEY` | (需要设置) | Flask应用安全密钥 |
| `ENCRYPTION_KEY` | (需要设置) | 数据加密密钥 |
| `HOST` | 0.0.0.0 | 监听IP地址 |
| `PORT` | 5000 | 监听端口 |
| `DEBUG` | True | 调试模式 |
| `DATABASE_URL` | SQLite | 数据库连接地址 |
| `SSH_TIMEOUT` | 30 | SSH连接超时(秒) |
| `DEFAULT_CPU_THRESHOLD` | 90.0 | CPU告警阈值(%) |
| `DEFAULT_MEMORY_THRESHOLD` | 90.0 | 内存告警阈值(%) |
| `DEFAULT_DISK_THRESHOLD` | 90.0 | 磁盘告警阈值(%) |

**数据库配置示例**:
```bash
# SQLite (默认)
DATABASE_URL=sqlite:///instance/host_monitor.db

# MySQL
DATABASE_URL=mysql://username:password@localhost:3306/host_monitor

# PostgreSQL
DATABASE_URL=postgresql://username:password@localhost:5432/host_monitor
```

**工具脚本**:
- **`reset_password.py`** (12.5KB): 管理员密码重置工具，支持用户列表和密码修改

**系统文件**:
- **`instance/host_monitor.db`**: SQLite数据库文件
- **`host_monitor.log`**: 系统运行日志
- **`reports/`**: 监控报告存储目录

## 🚨 故障排除

### 常见问题

1. **依赖安装失败**
	```bash
	# 升级pip
	python -m pip install --upgrade pip

	# 使用国内镜像
	pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
	```
	
	
2. **端口被占用**
	修改 `.env` 文件中的 PORT 配置:
	```env
	PORT=8080
	```
	
	
3. **Linux权限问题**
	确保有写入权限:
	```bash
	chmod 755 run.py start_production.py
	chmod 755 instance/ logs/ reports/
	```	
4. **Linux防火墙设置**
	确保防火墙允许配置的端口访问:
	```bash
	# CentOS/RHEL
	firewall-cmd --permanent --add-port=5000/tcp
	firewall-cmd --reload

	# Ubuntu
	ufw allow 5000
	```


5. **启动失败**
   ```bash
   # 检查Python版本
   python --version
   
   # 重新安装依赖
   pip install -r requirements.txt
   ```
   


6. **Flask环境变量警告**
   如果看到`'FLASK_ENV' is deprecated`警告：
   - 检查`.env`文件是否使用`FLASK_DEBUG=True`而不是`FLASK_ENV=development`
   - 如果仍有问题，请更新Flask到最新版本

7. **密码解密失败**
   如果看到`密码解密失败`错误：
   - 检查`.env`文件中的`ENCRYPTION_KEY`是否正确设置
   - 确保密钥是44位的Base64编码字符串
   - 如果是旧数据，可能需要重新添加服务器

8. **SSH连接失败**
   - 检查服务器IP和端口
   - 验证用户名密码或私钥
   - 确认SSH服务运行正常
   - 检查网络连通性

9. **通知发送失败**
   - 验证Webhook URL正确性
   - 检查网络连接
   - 查看日志文件错误信息

10. **监控异常**
   - 检查被监控服务器SSH权限
   - 确认服务器系统命令可用
   - 查看 `host_monitor.log` 日志

11. **SSH Shell兼容性错误**
   系统已对常见的shell配置错误进行了智能处理，以下错误将被自动忽略：
   
   **已忽略的非关键错误**：
   - `then: then/endif not found` - csh/tcsh shell语法错误
   - `if: Expression Syntax` - shell表达式语法错误
   - `Badly placed ()` - shell语法错误
   - `: not found` - 缺少命令或文件
   - `: Undefined variable` - 环境变量未定义
   - `LINX_PTS: Undefined variable` - 特定环境变量错误
   - `No such file or directory` - 配置文件不存在
   - `Permission denied` - 权限问题（非关键情况）
   
   **如何工作**：
   - 系统使用`/bin/sh -c`执行命令，避免不同shell的兼容性问题
   - 当检测到上述错误时，如果同时有有效输出，将忽略错误继续处理
   - 只有在关键错误或无效输出时才会报告失败
   
   **监控日志示例**：
   ```
   2025-08-27 21:44:56 - app.service_monitor - INFO - 开始监控服务器 Ⅲ区DAS主机，共 1 个服务
   2025-08-27 21:44:57 - app.service_monitor - WARNING - 检测到非关键错误（已忽略）: LINX_PTS: Undefined variable.
   2025-08-27 21:44:57 - app.service_monitor - INFO - 忽略非关键错误，继续处理有效输出
   2025-08-27 21:44:58 - app.service_monitor - INFO - 服务器 Ⅲ区DAS主机 服务监控完成，监控了 1 个服务
   ```

   **用户自定义修改指导**：
   
   如果你遇到新的shell错误需要忽略，可以按以下步骤修改代码：
   
   1. **定位错误处理代码**：
      编辑 `app/service_monitor.py` 文件，找到第443行附近的 `non_critical_errors` 列表。
   
   2. **添加新的错误模式**：
      ```python
      non_critical_errors = [
          'then: then/endif not found',
          'if: Expression Syntax',
          'Badly placed ()',
          ': not found',
          ': Undefined variable',
          'LINX_PTS: Undefined variable',
          'No such file or directory',
          'Permission denied',
          # 在这里添加你的新错误模式
          'your_new_error_pattern_here',
      ]
      ```
   
   3. **错误模式匹配原则**：
      - 使用部分字符串匹配，不需要完整错误信息
      - 如错误信息为 `bash: /usr/bin/id: No such file or directory`，只需添加 `'No such file or directory'`
      - 如错误信息为 `csh: syntax error near unexpected token`，可以添加 `'syntax error'`
   
   4. **测试和验证**：
      修改后重启系统，再次执行监控，查看日志中是否出现：
      ```
      WARNING - 检测到非关键错误（已忽略）: your_error_message
      INFO - 忽略非关键错误，继续处理有效输出
      ```
   
   5. **注意事项**：
      - 只忽略真正非关键的错误（即有SSH输出但有shell配置错误）
      - 不要忽略关键的系统错误（如真正的权限问题、命令不存在等）
      - 建议先在测试环境中验证再应用到生产环境
   
   6. **高级配置**：
      如果需要更精细的控制，可以修改错误判断逻辑（第456-465行）：
      ```python
      # 自定义错误判断逻辑
      is_critical_error = True
      for non_critical in non_critical_errors:
          if non_critical in error:
              # 可以在这里添加额外的条件判断
              if some_additional_condition:
                  is_critical_error = False
                  logger.warning(f"检测到非关键错误（已忽略）: {error}")
                  break
      ```

### 日志管理

系统采用先进的按天分割日志管理策略，解决了命令窗口日志占用过高的问题。

#### 日志文件结构

所有日志文件保存在 `logs/` 目录下，按日期和类型分类：

```
logs/
├── run-20250826.log           # 开发环境日志（run.py）
├── run-error-20250826.log      # 开发环境错误日志
├── production-20250826.log     # 生产环境日志（start_production.py）
├── production-error-20250826.log # 生产环境错误日志
├── flask-20250826.log          # Flask应用日志
└── flask-error-20250826.log    # Flask应用错误日志
```

#### 日志特性

- **按天自动分割**：每天午夜自动创建新的日志文件，文件名格式为`appname-YYYYMMDD.log`
- **分类存储**：普通日志和错误日志分开存储
- **自动清理**：自动保留最近30天的日志文件
- **多级日志**：支持DEBUG、INFO、WARNING、ERROR等级别
- **UTF-8编码**：支持中文日志内容
- **正确轮转**：修复了日志轮转时文件命名不正确的问题，确保生成正确的文件名格式

#### 控制台日志配置

**开发环境（run.py）**:
- ✅ 启用控制台输出，INFO及以上级别在控制台显示
- 所有级别日志保存到文件

**生产环境（start_production.py）**:
- ❌ 自动禁用控制台输出（避免占用过高）
- 日志只保存到文件，适合后台运行
- 自动设置 `CONSOLE_LOG_ENABLED=False`，无需手动配置

#### 日志配置选项

在 `.env` 文件中配置日志参数：

```env
# 日志配置
LOG_LEVEL=INFO                    # 日志级别
LOG_DIR=logs                      # 日志目录
LOG_RETENTION_DAYS=30             # 日志保留天数
CONSOLE_LOG_ENABLED=True          # 控制台日志开关
CONSOLE_LOG_LEVEL=INFO            # 控制台日志级别
```

#### 查看日志

**实时查看日志**:
```bash
# 查看最新的运行日志
tail -f logs/run.log

# 查看最新的生产环境日志
tail -f logs/production.log

# 查看最新的Flask应用日志
tail -f logs/flask.log

# 查看最新的错误日志
tail -f logs/run-error.log
```

**查看历史日志**:
```bash
# 查看指定日期的日志
cat logs/run-20250825.log

# 查看指定日期的Flask日志
cat logs/flask-20250825.log

# 搜索包含特定关键词的日志
grep "错误" logs/*.log

# 查看最近的错误日志
find logs -name "*error*.log" -exec tail -n 20 {} \;
```

**日志文件说明**:
- `run.log`: 开发环境运行日志
- `production.log`: 生产环境运行日志
- `flask.log`: Flask应用日志（包含Web请求、路由访问等信息）
- `*-error.log`: 错误日志（按应用类型分类存储）
- `*-YYYYMMDD.log`: 按天轮转的历史日志文件

#### 避免命令窗口占用过高

**问题说明**: 开发环境下运行 `run.py` 时，控制台会显示大量日志输出

**解决方案**:

1. **使用生产环境脚本（推荐）**：
   ```bash
   # 自动禁用控制台日志，无需手动配置
   python start_production.py
   ```
   ✅ **优点**：自动设置 `CONSOLE_LOG_ENABLED=False`，无需修改.env文件

2. **修改开发环境配置**：
   在 `.env` 文件中设置：
   ```env
   CONSOLE_LOG_ENABLED=False
   ```

3. **重定向到文件**：
   ```bash
   # 将控制台输出重定向到文件
   python run.py > run_output.log 2>&1
   
   # Windows后台运行
   start /B python start_production.py
   ```

#### 日志维护

系统自动进行日志维护：
- **自动轮转**: 每天午夜自动创建新日志文件
- **自动清理**: 删除超过30天的旧日志文件
- **错误隔离**: 错误日志单独存储，便于问题排查

**手动维护**：
```bash
# 清理旧日志（7天前）
find logs -name "*.log" -mtime +7 -delete

# Windows
forfiles /p logs /s /m *.log /d -7 /c "cmd /c del @path"

# 压缩历史日志
find logs -name "*.log" -mtime +7 -exec gzip {} \;

# 查看日志文件大小
du -h logs/          # Linux/Mac
dir logs\ /s         # Windows
```

#### 故障排除

**常见问题**：

1. **日志文件不存在**
   - 检查 `logs` 目录是否存在
   - 确认应用已正常启动
   - 查看是否有权限问题

2. **日志文件过大**
   - 检查是否启用了自动轮转
   - 考虑降低日志级别
   - 增加日志清理频率

3. **找不到错误日志**
   - 错误日志只在有ERROR级别日志时才创建
   - 检查文件名是否正确（包含 `-error-`）

4. **中文乱码**
   - 确认文件以UTF-8编码保存
   - 使用支持UTF-8的文本编辑器查看

5. **日志轮转文件命名不正确**
   - 系统已修复此问题，确保生成正确的文件名格式（如flask-20250827.log）
   - 如果发现不正确的命名文件，可以手动删除并重启系统

**调试技巧**：
```bash
# 启用调试日志（在.env文件中设置）
LOG_LEVEL=DEBUG

# 实时监控所有日志
tail -f logs/*.log                    # Linux/Mac
Get-Content logs\*.log -Wait          # Windows

# 快速查找错误
grep -r "ERROR" logs/*$(date +%Y%m%d)*.log
grep -r "SSH" logs/flask-*.log | tail -10
```

#### 最佳实践

1. **生产环境**：始终使用 `start_production.py` 启动
2. **开发环境**：如果不需要调试，设置 `CONSOLE_LOG_ENABLED=False`
3. **监控**：定期检查错误日志文件
4. **备份**：重要环境下定期备份日志文件
5. **清理**：在磁盘空间有限时手动清理旧日志

### 性能优化

1. **监控频率**: 根据需求调整监控间隔
2. **并发数量**: 大量服务器时可调整并发线程数
3. **数据清理**: 定期清理过期日志和报告
4. **资源监控**: 确保运行环境有足够资源

## 🔒 安全建议

### 生产环境部署

1. **访问控制**
   - 仅在可信网络运行
   - 考虑配置HTTPS
   - 限制访问IP范围

2. **数据安全**
   - 定期备份数据库 `instance/host_monitor.db`
   - 保护SSH私钥文件
   - 使用强密码策略
   - **重要**: 保护`.env`文件安全，不要提交到版本控制系统
   - 生产环境中更改默认的`SECRET_KEY`和`ENCRYPTION_KEY`

3. **权限管理**
   - SSH用户使用最小必要权限
   - 定期更换认证凭据
   - 监控系统访问日志

## 📊 监控指标

### 收集的指标

- **CPU使用率**: 通过top命令获取
- **内存使用率**: 通过free命令计算
- **磁盘使用率**: 通过df命令获取各分区使用情况
- **系统信息**: 主机名、运行时间、系统版本等
- **负载信息**: 系统负载平均值

### 告警条件

- CPU使用率超过设定阈值
- 内存使用率超过设定阈值  
- 任意磁盘分区使用率超过设定阈值
- SSH连接失败或命令执行超时
