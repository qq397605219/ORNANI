from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- API Key Schemas ---

class APIKeyBase(BaseModel):
    key_name: str = Field(..., description="API Key的名称")
    daily_limit: int = Field(-1, description="每日使用次数限制, -1表示无限制")

class APIKeyCreate(APIKeyBase):
    api_key: str = Field(..., description="OpenRouter的API Key")

class APIKeyUpdate(APIKeyBase):
    is_active: bool = Field(True, description="是否激活")

class APIKey(APIKeyBase):
    id: int
    api_key: str
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime]
    usage_count: int
    daily_usage: int
    
    class Config:
        orm_mode = True

# --- Usage Log Schemas ---

class UsageLog(BaseModel):
    request_time: datetime
    key_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    response_status: int

    class Config:
        orm_mode = True

# --- Stats Schemas ---

class TodayStats(BaseModel):
    total_requests: int
    total_tokens: int
    unique_models: int

class ModelStat(BaseModel):
    model: str
    usage_count: int
    total_tokens: int

class StatsResponse(BaseModel):
    key_stats: List[APIKey]
    today_stats: TodayStats
    model_stats: List[ModelStat]

# --- Model Schemas ---

class Model(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "openrouter"

class ModelList(BaseModel):
    object: str = "list"
    data: List[Model]

# --- General Response ---

class SuccessResponse(BaseModel):
    success: bool = True
    message: str