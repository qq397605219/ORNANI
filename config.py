import json
import os
from typing import Dict, Any, Optional

class AppConfig:
    """用于封装和访问应用配置的类。"""
    def __init__(self, config_data: Dict[str, Any]):
        self._config = config_data

    def get(self, key: str, default: Any = None) -> Any:
        """通过点表示法获取嵌套的配置值，例如 'server.port'。"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

def load_config(path: str = "config.json") -> AppConfig:
    """
    从JSON文件加载配置。
    如果文件不存在或格式错误，将引发异常。
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 允许通过环境变量覆盖特定值
        admin_password = os.getenv("ADMIN_PASSWORD")
        if admin_password:
            config_data['admin']['password'] = admin_password
            
        port = os.getenv("PORT")
        if port:
            config_data['server']['port'] = int(port)
            
        return AppConfig(config_data)
    except FileNotFoundError:
        raise RuntimeError(f"配置文件 '{path}' 未找到。请确保该文件存在。")
    except json.JSONDecodeError:
        raise RuntimeError(f"配置文件 '{path}' 格式错误。请检查JSON语法。")
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"配置文件 '{path}' 缺少必要的键或结构错误: {e}")

# 创建一个全局配置实例，供整个应用使用
config = load_config()