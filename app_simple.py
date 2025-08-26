#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化版的主机巡视系统启动文件
用于解决模板加载问题
"""

import os
import sys
from flask import Flask, render_template, jsonify

# 添加项目根目录到Python路径
basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

# 创建Flask应用
app = Flask(__name__, 
            template_folder=os.path.join(basedir, 'templates'),
            static_folder=os.path.join(basedir, 'static'))

# 基本配置
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///host_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"模板目录: {app.template_folder}")
print(f"静态文件目录: {app.static_folder}")

# 检查模板文件是否存在
template_path = os.path.join(app.template_folder, 'index.html')
print(f"模板文件: {template_path}")
print(f"模板文件存在: {os.path.exists(template_path)}")

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/dashboard')
def dashboard():
    """仪表板数据 - 简化版"""
    return jsonify({
        'success': True,
        'data': {
            'total_servers': 0,
            'success_count': 0,
            'warning_count': 0,
            'failed_count': 0,
            'server_status': {}
        }
    })

@app.route('/api/servers')
def get_servers():
    """获取服务器列表 - 简化版"""
    return jsonify({
        'success': True,
        'data': {
            'servers': [],
            'total': 0,
            'pages': 0,
            'current_page': 1,
            'has_prev': False,
            'has_next': False
        }
    })

@app.route('/api/thresholds')
def get_thresholds():
    """获取阈值配置 - 简化版"""
    return jsonify({
        'success': True,
        'data': {
            'cpu_threshold': 80.0,
            'memory_threshold': 80.0,
            'disk_threshold': 80.0
        }
    })

if __name__ == '__main__':
    print("启动简化版主机巡视系统...")
    print("请在浏览器中访问: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)