from typing import Optional, Dict, Any
from app import crud

class APIKeyManager:
    """
    管理API Key的业务逻辑，包括选择下一个可用的Key。
    """
    def get_next_key(self) -> Optional[Dict[str, Any]]:
        """
        获取下一个可用的API Key。
        选择逻辑是：在所有激活且未超每日限额的Key中，选择总使用次数最少的那个。
        """
        # crud.get_active_api_keys() 已经处理了激活状态、每日限额检查和排序
        active_keys = crud.get_active_api_keys()
        
        if not active_keys:
            return None
            
        # 返回使用次数最少的Key
        return active_keys[0]

    def update_key_usage(self, key_id: int):
        """
        更新指定Key的使用记录。
        """
        crud.update_key_usage(key_id)

# 创建一个单例实例，以便在应用中共享
key_manager = APIKeyManager()