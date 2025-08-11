import httpx
import logging
import json
from typing import List, Dict, Any, AsyncGenerator

from app import crud
from app.services.key_manager import key_manager
from config import config

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """
    用于与OpenRouter API进行交互的客户端。
    """
    async def fetch_models(self) -> List[Dict[str, Any]]:
        """从OpenRouter获取所有可用模型。"""
        try:
            async with httpx.AsyncClient(timeout=config.get('openrouter.request_timeout', 30.0)) as client:
                response = await client.get(
                    f"{config.get('openrouter.base_url')}/models",
                    headers={
                        "HTTP-Referer": config.get('openrouter.http_referer'),
                        "X-Title": config.get('openrouter.x_title'),
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get('data', [])
        except httpx.HTTPStatusError as e:
            logger.error(f"获取OpenRouter模型列表失败，状态码: {e.response.status_code}, 响应: {e.response.text}")
        except Exception as e:
            logger.error(f"获取OpenRouter模型列表时发生未知错误: {e}")
        return []

    async def update_free_models_cache(self) -> int:
        """获取最新的免费模型并更新数据库缓存。"""
        models = await self.fetch_models()
        if not models:
            logger.warning("未能获取到任何模型，跳过免费模型更新。")
            return 0
            
        free_models = [
            model for model in models if config.get('openrouter.free_model_suffix') in model.get('id', '')
        ]
        
        crud.update_free_models(free_models)
        logger.info(f"✅ 成功更新了 {len(free_models)} 个免费模型。")
        return len(free_models)

    async def stream_chat_completions(
        self, body: Dict, headers: Dict, api_key_info: Dict, model: str
    ) -> AsyncGenerator[str, None]:
        """处理流式聊天补全请求，并从流中提取usage数据。"""
        usage_data = None
        status_code = 500
        
        # 用于备用token估算的变量
        estimated_prompt_tokens = 0
        estimated_completion_tokens = 0
        completion_content = ""
        
        try:
            # 估算输入token数量（简单估算：4个字符约等于1个token）
            estimated_prompt_tokens = self._estimate_tokens_from_messages(body.get("messages", []))
            
            async with httpx.AsyncClient(timeout=config.get('openrouter.request_timeout', 60.0)) as client:
                async with client.stream(
                    "POST",
                    f"{config.get('openrouter.base_url')}/chat/completions",
                    json=body,
                    headers=headers
                ) as response:
                    key_manager.update_key_usage(api_key_info['id'])
                    status_code = response.status_code

                    if response.status_code != 200:
                        error_content = await response.aread()
                        error_message = error_content.decode('utf-8', errors='ignore')
                        error_data = {
                            "error": {
                                "message": f"OpenRouter API error: {response.status_code} - {error_message}",
                                "type": "api_error",
                                "code": response.status_code
                            }
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        return

                    async for chunk in response.aiter_bytes():
                        if chunk:
                            chunk_str = chunk.decode('utf-8', errors='ignore')
                            yield chunk_str
                            
                            lines = chunk_str.strip().split('\n')
                            for line in lines:
                                if line.startswith('data:'):
                                    data_str = line[len('data:'):].strip()
                                    if data_str == '[DONE]':
                                        continue
                                    try:
                                        data_json = json.loads(data_str)
                                        
                                        # 提取usage数据
                                        if 'usage' in data_json:
                                            usage_data = data_json['usage']
                                            logger.info(f"📊 从流中获取到usage数据: {usage_data}")
                                        
                                        # 收集completion内容用于备用估算
                                        if 'choices' in data_json and len(data_json['choices']) > 0:
                                            choice = data_json['choices'][0]
                                            if 'delta' in choice and 'content' in choice['delta']:
                                                content = choice['delta']['content']
                                                if content:
                                                    completion_content += content
                                                    
                                    except json.JSONDecodeError:
                                        pass
        except Exception as e:
            logger.error(f"流式处理错误: {e}")
            error_data = {
                "error": {"message": f"Stream processing error: {str(e)}", "type": "internal_error"}
            }
            yield f"data: {json.dumps(error_data)}\n\n"
            status_code = 500
        finally:
            # 优先使用API返回的usage数据
            if usage_data:
                prompt_tokens = usage_data.get("prompt_tokens", 0)
                completion_tokens = usage_data.get("completion_tokens", 0)
                total_tokens = usage_data.get("total_tokens", 0)
                logger.info(f"✅ 使用API返回的token统计: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
            else:
                # 备用方案：使用估算的token数量
                estimated_completion_tokens = self._estimate_tokens_from_text(completion_content)
                prompt_tokens = estimated_prompt_tokens
                completion_tokens = estimated_completion_tokens
                total_tokens = prompt_tokens + completion_tokens
                logger.warning(f"⚠️ API未返回usage数据，使用估算值: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
            
            crud.log_usage(
                api_key_id=api_key_info['id'],
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=0.0,
                status=status_code
            )
    
    def _estimate_tokens_from_messages(self, messages: list) -> int:
        """从消息列表估算token数量"""
        total_chars = 0
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    # 处理多模态内容
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            total_chars += len(item.get("text", ""))
        
        # 简单估算：平均4个字符约等于1个token（对中文更准确）
        estimated_tokens = max(1, total_chars // 3)  # 对中文使用更保守的估算
        return estimated_tokens
    
    def _estimate_tokens_from_text(self, text: str) -> int:
        """从文本估算token数量"""
        if not text:
            return 0
        # 简单估算：平均3个字符约等于1个token（对中文更准确）
        return max(1, len(text) // 3)

# 创建一个单例实例
openrouter_client = OpenRouterClient()