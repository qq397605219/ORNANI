from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import json
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, AsyncGenerator
import sqlite3
import hashlib
import secrets
from contextlib import asynccontextmanager
import os
import logging

# 配置详细日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    
    # API Keys表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
    ''')
    
    # 使用记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            cost REAL,
            request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_status INTEGER,
            FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
        )
    ''')
    
    # 免费模型表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS free_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT UNIQUE NOT NULL,
            model_name TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # 免费模型将在启动时动态获取
    
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    
    # 启动时更新免费模型列表
    print("🔄 正在从OpenRouter获取免费模型列表...")
    await update_free_models_cache()
    
    yield

app = FastAPI(
    title="OpenRouter API Proxy",
    description="OpenRouter API代理服务，支持多Key轮询和免费模型过滤",
    version="1.0.0",
    lifespan=lifespan
)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import sys
    start_time = time.time()
    
    # 记录请求信息
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    url = str(request.url)
    headers = dict(request.headers)
    
    # 强制输出到stdout并刷新
    log_msg = f"\n🔍 收到请求:\n"
    log_msg += f"   📍 客户端IP: {client_ip}\n"
    log_msg += f"   🌐 方法: {method}\n"
    log_msg += f"   📡 URL: {url}\n"
    log_msg += f"   📋 Headers:\n"
    for key, value in headers.items():
        # 隐藏敏感信息
        if 'authorization' in key.lower():
            value = f"Bearer {value.split(' ')[-1][:10]}..." if 'Bearer' in value else "***"
        log_msg += f"      {key}: {value}\n"
    
    sys.stdout.write(log_msg)
    sys.stdout.flush()
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应信息
    process_time = time.time() - start_time
    status_code = response.status_code
    
    response_msg = f"   📊 响应状态: {status_code}\n"
    response_msg += f"   ⏱️  处理时间: {process_time:.3f}s\n"
    
    if status_code >= 400:
        response_msg += f"   ❌ 错误响应!\n"
    else:
        response_msg += f"   ✅ 成功响应\n"
    
    response_msg += "-" * 60 + "\n"
    
    sys.stdout.write(response_msg)
    sys.stdout.flush()
    
    return response

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# 静态文件和模板
templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="templates"), name="static")
# 配置
ADMIN_PASSWORD = "admin123"  # 管理员密码，实际使用时应该从环境变量读取
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

security = HTTPBearer()

class APIKeyManager:
    def __init__(self):
        self.current_key_index = 0
    
    def get_active_keys(self) -> List[Dict]:
        conn = sqlite3.connect('openrouter_proxy.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, key_name, api_key, usage_count, last_used 
            FROM api_keys 
            WHERE is_active = TRUE
            ORDER BY usage_count ASC
        ''')
        keys = [
            {
                'id': row[0],
                'key_name': row[1], 
                'api_key': row[2],
                'usage_count': row[3],
                'last_used': row[4]
            } 
            for row in cursor.fetchall()
        ]
        conn.close()
        return keys
    
    def get_next_key(self) -> Optional[Dict]:
        keys = self.get_active_keys()
        if not keys:
            return None
        
        # 简单的轮询策略：选择使用次数最少的key
        return keys[0]
    
    def update_key_usage(self, key_id: int):
        conn = sqlite3.connect('openrouter_proxy.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE api_keys 
            SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (key_id,))
        conn.commit()
        conn.close()

key_manager = APIKeyManager()

async def stream_chat_completions(body: Dict, headers: Dict, api_key_info: Dict, model: str) -> AsyncGenerator[str, None]:
    """处理流式聊天完成请求"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=body,
                headers=headers
            ) as response:
                # 更新Key使用次数
                key_manager.update_key_usage(api_key_info['id'])
                
                # 如果响应不成功，返回错误信息
                if response.status_code != 200:
                    error_data = {
                        "error": {
                            "message": f"OpenRouter API error: {response.status_code}",
                            "type": "api_error",
                            "code": response.status_code
                        }
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    return
                
                # 流式处理响应 - 直接转发原始数据
                async for chunk in response.aiter_bytes():
                    if chunk:
                        # 直接转发原始字节数据，避免JSON解析问题
                        yield chunk.decode('utf-8', errors='ignore')
                
                # 记录使用情况（流式响应无法准确统计token）
                log_usage(
                    api_key_id=api_key_info['id'],
                    model=model,
                    prompt_tokens=0,  # 流式响应无法准确统计
                    completion_tokens=0,
                    total_tokens=0,
                    cost=0.0,
                    status=response.status_code
                )
                
    except Exception as e:
        error_data = {
            "error": {
                "message": f"Stream processing error: {str(e)}",
                "type": "internal_error"
            }
        }
        yield f"data: {json.dumps(error_data)}\n\n"

async def fetch_openrouter_models() -> List[Dict]:
    """从OpenRouter获取所有可用模型"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "HTTP-Referer": "https://your-domain.com",
                    "X-Title": "OpenRouter Proxy"
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
    except Exception as e:
        print(f"获取OpenRouter模型列表失败: {e}")
    return []

async def update_free_models_cache():
    """更新免费模型缓存"""
    models = await fetch_openrouter_models()
    free_models = []
    
    for model in models:
        model_id = model.get('id', '')
        # 检查是否为免费模型（包含:free后缀）
        if ':free' in model_id:
            free_models.append({
                'model_id': model_id,
                'model_name': model.get('name', model_id),
                'context_length': model.get('context_length', 0),
                'pricing': model.get('pricing', {})
            })
    
    # 更新数据库
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    
    # 清空现有免费模型
    cursor.execute('DELETE FROM free_models')
    
    # 插入新的免费模型
    for model in free_models:
        cursor.execute('''
            INSERT INTO free_models (model_id, model_name, is_active) 
            VALUES (?, ?, TRUE)
        ''', (model['model_id'], model['model_name']))
    
    conn.commit()
    conn.close()
    
    print(f"✅ 更新了 {len(free_models)} 个免费模型")
    return free_models

def get_free_models() -> List[str]:
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    cursor.execute('SELECT model_id FROM free_models WHERE is_active = TRUE')
    models = [row[0] for row in cursor.fetchall()]
    conn.close()
    return models

def log_usage(api_key_id: int, model: str, prompt_tokens: int, 
              completion_tokens: int, total_tokens: int, cost: float, status: int):
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usage_logs 
        (api_key_id, model, prompt_tokens, completion_tokens, total_tokens, cost, response_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (api_key_id, model, prompt_tokens, completion_tokens, total_tokens, cost, status))
    conn.commit()
    conn.close()

def verify_admin_password(password: str) -> bool:
    return password == ADMIN_PASSWORD

async def verify_access_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    return credentials.credentials

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        # 获取请求数据
        body = await request.json()
        
        # 验证访问密码
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        access_token = auth_header.split(" ")[1]
        if not verify_admin_password(access_token):
            raise HTTPException(status_code=401, detail="Invalid access token")
        
        # 检查模型是否在免费模型列表中
        model = body.get("model", "")
        free_models = get_free_models()
        
        if model not in free_models:
            raise HTTPException(
                status_code=400, 
                detail=f"Model '{model}' is not allowed. Only free models are supported."
            )
        
        # 获取可用的API Key
        api_key_info = key_manager.get_next_key()
        if not api_key_info:
            raise HTTPException(status_code=503, detail="No available API keys")
        
        # 检查是否请求流式响应
        stream = body.get("stream", False)
        
        # 准备请求头
        headers = {
            "Authorization": f"Bearer {api_key_info['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://your-domain.com",
            "X-Title": "OpenRouter Proxy"
        }
        
        if stream:
            # 流式响应处理
            return StreamingResponse(
                stream_chat_completions(body, headers, api_key_info, model),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        else:
            # 非流式响应处理（保持原有逻辑）
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    json=body,
                    headers=headers
                )
            
            # 更新Key使用次数
            key_manager.update_key_usage(api_key_info['id'])
            
            # 处理响应数据
            try:
                response_data = response.json()
            except Exception:
                # 如果无法解析JSON，返回文本内容
                response_data = {"error": response.text}
            
            # 记录使用情况
            usage = response_data.get("usage", {}) if response.status_code == 200 else {}
            
            log_usage(
                api_key_id=api_key_info['id'],
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=0.0,  # 免费模型成本为0
                status=response.status_code
            )
            
            return JSONResponse(
                content=response_data,
                status_code=response.status_code
            )
        
    except HTTPException:
        # 重新抛出HTTP异常，保持原有状态码
        raise
    except Exception as e:
        # 其他未预期的异常才返回500
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/v1/models")
async def get_models(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取可用的免费模型列表"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    free_models = get_free_models()
    
    models_data = {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openrouter"
            }
            for model_id in free_models
        ]
    }
    
    return models_data

# Web管理界面路由
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if verify_admin_password(password):
        return {"success": True, "message": "登录成功"}
    else:
        raise HTTPException(status_code=401, detail="密码错误")

@app.get("/admin/stats")
async def get_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    
    # 获取API Key统计
    cursor.execute('''
        SELECT k.id, k.key_name, k.api_key, k.usage_count, k.last_used, k.is_active
        FROM api_keys k
        ORDER BY k.usage_count DESC
    ''')
    key_stats = [
        {
            'id': row[0],
            'key_name': row[1],
            'api_key': row[2],
            'usage_count': row[3],
            'last_used': row[4],
            'is_active': row[5]
        }
        for row in cursor.fetchall()
    ]
    
    # 获取使用统计
    cursor.execute('''
        SELECT 
            COUNT(*) as total_requests,
            SUM(total_tokens) as total_tokens,
            COUNT(DISTINCT model) as unique_models
        FROM usage_logs
        WHERE DATE(request_time) = DATE('now')
    ''')
    today_stats = cursor.fetchone()
    
    # 获取模型使用统计
    cursor.execute('''
        SELECT model, COUNT(*) as usage_count, SUM(total_tokens) as total_tokens
        FROM usage_logs
        GROUP BY model
        ORDER BY usage_count DESC
        LIMIT 10
    ''')
    model_stats = [
        {
            'model': row[0],
            'usage_count': row[1],
            'total_tokens': row[2]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    
    return {
        "key_stats": key_stats,
        "today_stats": {
            "total_requests": today_stats[0] or 0,
            "total_tokens": today_stats[1] or 0,
            "unique_models": today_stats[2] or 0
        },
        "model_stats": model_stats
    }

@app.post("/admin/keys")
async def add_api_key(
    key_name: str = Form(...),
    api_key: str = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO api_keys (key_name, api_key) VALUES (?, ?)
    ''', (key_name, api_key))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "API Key添加成功"}

@app.delete("/admin/keys/{key_id}")
async def delete_api_key(key_id: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM api_keys WHERE id = ?', (key_id,))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "API Key删除成功"}

@app.post("/admin/refresh-models")
async def refresh_free_models(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """手动刷新免费模型列表"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    try:
        free_models = await update_free_models_cache()
        return {
            "success": True, 
            "message": f"成功更新 {len(free_models)} 个免费模型",
            "models": [model['model_id'] for model in free_models]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")

@app.get("/admin/usage-logs")
async def get_usage_logs(
    page: int = 1,
    page_size: int = 50,
    key_filter: str = "",
    model_filter: str = "",
    status_filter: str = "",
    date_filter: str = "",
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取详细的调用记录"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    
    # 构建查询条件
    where_conditions = []
    params = []
    
    if key_filter:
        where_conditions.append("ul.api_key_id = ?")
        params.append(key_filter)
    
    if model_filter:
        where_conditions.append("ul.model = ?")
        params.append(model_filter)
    
    if status_filter:
        if status_filter == "200":
            where_conditions.append("ul.response_status = 200")
        elif status_filter == "400":
            where_conditions.append("ul.response_status >= 400")
    
    if date_filter:
        where_conditions.append("DATE(ul.request_time) = ?")
        params.append(date_filter)
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # 获取总记录数
    count_query = f"""
        SELECT COUNT(*)
        FROM usage_logs ul
        JOIN api_keys ak ON ul.api_key_id = ak.id
        WHERE {where_clause}
    """
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()[0]
    total_pages = (total_records + page_size - 1) // page_size
    
    # 获取分页数据
    offset = (page - 1) * page_size
    data_query = f"""
        SELECT 
            ul.request_time,
            ak.key_name,
            ul.model,
            ul.prompt_tokens,
            ul.completion_tokens,
            ul.total_tokens,
            ul.cost,
            ul.response_status
        FROM usage_logs ul
        JOIN api_keys ak ON ul.api_key_id = ak.id
        WHERE {where_clause}
        ORDER BY ul.request_time DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_query, params + [page_size, offset])
    
    logs = [
        {
            'request_time': row[0],
            'key_name': row[1],
            'model': row[2],
            'prompt_tokens': row[3],
            'completion_tokens': row[4],
            'total_tokens': row[5],
            'cost': row[6],
            'response_status': row[7]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    
    return {
        "logs": logs,
        "total_records": total_records,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size
    }

@app.get("/admin/filter-options")
async def get_filter_options(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取筛选选项数据"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    
    # 获取所有API Keys
    cursor.execute('SELECT id, key_name FROM api_keys ORDER BY key_name')
    keys = [{'id': row[0], 'key_name': row[1]} for row in cursor.fetchall()]
    
    # 获取所有使用过的模型
    cursor.execute('SELECT DISTINCT model FROM usage_logs ORDER BY model')
    models = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "keys": keys,
        "models": models
    }

@app.get("/admin/free-models")
async def get_free_models_list(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """获取当前免费模型列表"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    conn = sqlite3.connect('openrouter_proxy.db')
    cursor = conn.cursor()
    cursor.execute('SELECT model_id, model_name, is_active FROM free_models ORDER BY model_id')
    models = [
        {
            'model_id': row[0],
            'model_name': row[1],
            'is_active': row[2]
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    
    return {"models": models}

@app.get("/")
async def root():
    return {"message": "OpenRouter API Proxy is running", "admin_url": "/admin"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)