import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import admin, proxy
from app.services.openrouter_client import openrouter_client
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理，在启动时执行初始化任务。
    """
    logger.info("🚀 服务启动中...")
    # 1. 初始化数据库
    init_db()
    # 2. 更新免费模型缓存
    logger.info("🔄 正在从OpenRouter获取免费模型列表...")
    await openrouter_client.update_free_models_cache()
    logger.info("✅ 服务启动完成。")
    yield
    logger.info("🛑 服务已关闭。")

app = FastAPI(
    title="OpenRouter API Proxy",
    description="OpenRouter API代理服务，支持多Key轮询和免费模型过滤",
    version="2.0.0",  # 版本升级
    lifespan=lifespan
)

# --- 中间件配置 ---

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求的详细信息。"""
    start_time = time.time()
    
    # 记录请求
    log_msg = f"\n🔍 收到请求: {request.method} {request.url}\n"
    log_msg += f"   - 客户端IP: {request.client.host if request.client else 'N/A'}\n"
    # 可以在这里添加更多需要记录的Header
    
    logger.info(log_msg)
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应
    process_time = time.time() - start_time
    log_msg = f"   - 响应状态: {response.status_code}\n"
    log_msg += f"   - 处理时间: {process_time:.3f}s\n"
    
    if response.status_code >= 400:
        logger.error(f"❌ 错误响应: {log_msg}")
    else:
        logger.info(f"✅ 成功响应: {log_msg}")
        
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 静态文件和路由包含 ---

# 挂载静态文件目录，用于提供admin.html中的CSS和JS
app.mount("/static", StaticFiles(directory="templates"), name="static")

# 包含管理后台和代理服务的路由
app.include_router(admin.router)
app.include_router(proxy.router)

@app.get("/")
async def root():
    """根路径，提供一个简单的欢迎信息。"""
    return {"message": config.get('messages.welcome'), "admin_url": config.get('messages.admin_url_info')}

# --- 启动命令 ---
# 使用 uvicorn main:app --reload --host 0.0.0.0 --port 8000 启动
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.get('server.host'), port=config.get('server.port'))