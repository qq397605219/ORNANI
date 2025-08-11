#!/usr/bin/env python3
"""
OpenRouter API Proxy 启动脚本
"""

import uvicorn
import sys
import os
from config import Config

def main():
    print("🚀 启动 OpenRouter API Proxy...")
    print(f"📍 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"🔧 管理后台: http://{Config.HOST}:{Config.PORT}/admin")
    print(f"🔑 管理员密码: {Config.ADMIN_PASSWORD}")
    print("=" * 50)
    
    try:
        uvicorn.run(
            "main:app",
            host=Config.HOST,
            port=Config.PORT,
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