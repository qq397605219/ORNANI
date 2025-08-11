import time
import httpx
import tiktoken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app import crud
from app.services.key_manager import key_manager
from app.services.openrouter_client import openrouter_client
from config import config

def estimate_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """估算文本的token数量"""
    try:
        # 尝试获取模型对应的编码器
        if "gpt-4" in model.lower():
            encoding = tiktoken.encoding_for_model("gpt-4")
        elif "gpt-3.5" in model.lower():
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        else:
            # 对于其他模型，使用cl100k_base编码器作为近似
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))
    except Exception:
        # 如果编码失败，使用简单的字符数估算（通常1个token约等于4个字符）
        return len(text) // 4

def calculate_max_tokens(messages: list, model: str) -> int:
    """根据输入消息和模型计算合理的max_tokens值"""
    # 首先尝试从数据库获取模型的上下文长度
    context_limit = crud.get_model_context_length(model)
    
    # 如果数据库中没有找到，使用默认值
    if context_limit is None:
        context_limit = 4096
    
    # 计算输入消息的总token数
    total_input_tokens = 0
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            total_input_tokens += estimate_tokens(content, model)
        elif isinstance(content, list):
            # 处理多模态内容
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    total_input_tokens += estimate_tokens(item.get("text", ""), model)
    
    # 预留一些token用于系统消息和格式化
    reserved_tokens = 100
    available_tokens = context_limit - total_input_tokens - reserved_tokens
    
    # 确保max_tokens在合理范围内
    if available_tokens <= 0:
        return 512  # 最小值
    elif available_tokens > 4096:
        return 4096  # 最大值，避免生成过长的回复
    else:
        return min(available_tokens, 2048)  # 通常情况下的合理上限

router = APIRouter()
security = HTTPBearer()

def verify_access_token(token: str) -> bool:
    """验证访问令牌是否有效。"""
    return token == config.get('admin.password')

async def authenticate(request: Request):
    """依赖项，用于验证请求头中的Bearer Token。"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少或无效的Authorization头")
    
    token = auth_header.split(" ")[1]
    if not verify_access_token(token):
        raise HTTPException(status_code=401, detail="无效的访问令牌")
    return token

@router.post("/v1/chat/completions", dependencies=[Depends(authenticate)])
async def chat_completions(request: Request):
    """
    处理聊天补全请求的核心代理端点。
    """
    try:
        body = await request.json()
        model = body.get("model", "")
        
        # 验证模型是否在允许的免费模型列表中
        if model not in crud.get_free_models():
            raise HTTPException(
                status_code=400,
                detail=config.get('messages.model_not_allowed_error', "模型 '{model}' 不被允许。只支持免费模型。").format(model=model)
            )

        # 如果请求中没有指定max_tokens，则根据模型上下文长度动态计算
        if "max_tokens" not in body or body["max_tokens"] is None:
            messages = body.get("messages", [])
            calculated_max_tokens = calculate_max_tokens(messages, model)
            body["max_tokens"] = calculated_max_tokens

        # 获取下一个可用的API Key
        api_key_info = key_manager.get_next_key()
        if not api_key_info:
            raise HTTPException(status_code=503, detail=config.get('messages.no_available_key_error', "没有可用的API Key"))

        # 准备请求头
        headers = {
            "Authorization": f"Bearer {api_key_info['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": config.get('openrouter.http_referer'),
            "X-Title": config.get('openrouter.x_title')
        }
        
        stream = body.get("stream", False)
        if stream:
            # 确保流式请求包含usage信息
            if "stream_options" not in body:
                body["stream_options"] = {}
            body["stream_options"]["include_usage"] = True
            
            # 添加适当的响应头
            return StreamingResponse(
                openrouter_client.stream_chat_completions(body, headers, api_key_info, model),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                }
            )
        else:
            async with httpx.AsyncClient(timeout=config.get('openrouter.request_timeout', 60.0)) as client:
                response = await client.post(
                    f"{config.get('openrouter.base_url')}/chat/completions",
                    json=body,
                    headers=headers
                )
            
            key_manager.update_key_usage(api_key_info['id'])
            
            try:
                response_data = response.json()
            except Exception:
                response_data = {"error": response.text}
            
            usage = response_data.get("usage", {}) if response.status_code == 200 else {}
            crud.log_usage(
                api_key_id=api_key_info['id'],
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost=0.0,
                status=response.status_code
            )
            
            return JSONResponse(content=response_data, status_code=response.status_code)
            
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=config.get('messages.internal_server_error', "内部服务器错误: {e}").format(e=e))

@router.get("/v1/models", dependencies=[Depends(authenticate)])
async def get_models():
    """
    获取可用的免费模型列表。
    """
    free_models = crud.get_free_models()
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