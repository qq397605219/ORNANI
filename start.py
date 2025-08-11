#!/usr/bin/env python3
"""
OpenRouter API Proxy 启动脚本
"""

import uvicorn
import sys
import os
from config import config

def main():
    host = config.get('server.host')
    port = config.get('server.port')
    admin_password = config.get('admin.password')

    print("🚀 启动 OpenRouter API Proxy...")
    print(f"📍 服务地址: http://{host}:{port}")
    print(f"🔧 管理后台: http://{host}:{port}/admin")
    print(f"🔑 管理员密码: {admin_password}")
    print("=" * 50)
    
    try:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()