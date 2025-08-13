#!/usr/bin/env python3
"""
LMArena Session Dashboard 启动脚本
初始化会话管理器并启动相关服务
"""

import subprocess
import sys
import time
import threading
import signal
import os
from pathlib import Path

def run_command(cmd, name):
    """运行命令并处理输出"""
    print(f"🚀 启动 {name}...")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # 实时输出日志
        for line in process.stdout:
            print(f"[{name}] {line.rstrip()}")
            
        return process
    except Exception as e:
        print(f"❌ 启动 {name} 失败: {e}")
        return None

def check_dependencies():
    """检查依赖项"""
    required_files = [
        'session_manager.py',
        'dashboard.py',
        'api_server.py',
        'init_sessions.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    
    return True

def initialize_sessions():
    """初始化会话管理器"""
    print("🔧 初始化会话管理器...")
    try:
        result = subprocess.run([sys.executable, 'init_sessions.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 会话管理器初始化成功")
            return True
        else:
            print(f"❌ 会话管理器初始化失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🎯 LMArena Session Dashboard 启动器")
    print("=" * 60)
    
    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)
    
    # 初始化会话管理器
    if not initialize_sessions():
        print("⚠️  会话管理器初始化失败，但继续启动服务...")
    
    # 启动服务
    processes = []
    
    # 启动主 API 服务器
    api_process = run_command([sys.executable, 'api_server.py'], "API Server")
    if api_process:
        processes.append(("API Server", api_process))
        print("✅ API 服务器已启动 (端口 5102)")
    
    # 等待一下让 API 服务器完全启动
    time.sleep(2)
    
    # 启动仪表板
    dashboard_process = run_command([sys.executable, 'dashboard.py'], "Dashboard")
    if dashboard_process:
        processes.append(("Dashboard", dashboard_process))
        print("✅ 仪表板已启动 (端口 8080)")
    
    if not processes:
        print("❌ 没有服务成功启动")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 服务启动完成!")
    print("📊 仪表板: http://localhost:8080")
    print("🔌 API 服务器: http://localhost:5102")
    print("📖 文档: SESSION_DASHBOARD_README.md")
    print("=" * 60)
    print("按 Ctrl+C 停止所有服务")
    
    # 信号处理
    def signal_handler(signum, frame):
        print("\n🛑 正在停止服务...")
        for name, process in processes:
            if process and process.poll() is None:
                print(f"停止 {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        print("✅ 所有服务已停止")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 监控进程
    try:
        while True:
            for name, process in processes:
                if process and process.poll() is not None:
                    print(f"❌ {name} 意外退出 (退出码: {process.returncode})")
                    # 可以选择重启服务
                    # new_process = run_command([sys.executable, f'{name.lower().replace(" ", "_")}.py'], name)
                    # if new_process:
                    #     processes[processes.index((name, process))] = (name, new_process)
            time.sleep(5)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()