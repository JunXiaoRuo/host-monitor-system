@echo off
echo 主机巡视系统 - 离线安装
echo ========================

python --version
if errorlevel 1 (
    echo 错误: 请先安装Python 3.8+
    pause
    exit /b 1
)

echo 安装依赖包...
pip install --no-index --find-links python-packages -r requirements.txt

echo 验证安装...
python -c "import flask; print('安装成功!')"

echo 完成! 现在可以运行: python run.py
pause
