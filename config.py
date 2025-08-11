import os
from typing import List

class Config:
    # 管理员密码 - 建议从环境变量读取
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # OpenRouter API配置
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # 数据库配置
    DATABASE_URL = "openrouter_proxy.db"
    
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = int(os.getenv("PORT", 8000))
    
    # 免费模型配置
    # 免费模型将从OpenRouter动态获取（所有包含:free后缀的模型）
    FREE_MODEL_SUFFIX = ":free"
    
    # 模型更新配置
    AUTO_UPDATE_MODELS_ON_STARTUP = True
    MODEL_CACHE_TIMEOUT = 3600  # 模型缓存超时时间（秒）
    
    # API限制配置
    MAX_TOKENS_PER_REQUEST = 4096
    REQUEST_TIMEOUT = 60.0
    
    # 负载均衡策略
    LOAD_BALANCE_STRATEGY = "round_robin"  # round_robin, least_used, random