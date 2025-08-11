import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .database import get_db_connection

logger = logging.getLogger(__name__)

# --- API Key CRUD ---

def add_api_key(key_name: str, api_key: str, daily_limit: int) -> None:
    """向数据库中添加一个新的API Key。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO api_keys (key_name, api_key, daily_limit, last_reset_time) VALUES (?, ?, ?, ?)",
            (key_name, api_key, daily_limit, datetime.utcnow())
        )
        conn.commit()

def delete_api_key(key_id: int) -> None:
    """从数据库中删除一个API Key。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()

def update_api_key(key_id: int, key_name: str, daily_limit: int, is_active: bool) -> None:
    """更新数据库中的一个API Key。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_keys SET key_name = ?, daily_limit = ?, is_active = ? WHERE id = ?",
            (key_name, daily_limit, is_active, key_id)
        )
        conn.commit()

def get_api_key_stats() -> List[Dict[str, Any]]:
    """获取所有API Key的统计信息。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, key_name, api_key, usage_count, last_used, is_active, daily_limit, daily_usage FROM api_keys ORDER BY usage_count DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

def get_active_api_keys() -> List[Dict[str, Any]]:
    """获取所有有效的API Key，并重置每日使用量。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 获取所有可能有效的Key
        cursor.execute('SELECT * FROM api_keys WHERE is_active = TRUE')
        keys = [dict(row) for row in cursor.fetchall()]
        
        valid_keys = []
        current_utc_date = datetime.utcnow().date()

        for key in keys:
            # 检查是否需要重置每日使用量
            last_reset_time_str = key.get('last_reset_time')
            last_reset_date = None
            if last_reset_time_str:
                try:
                    if '.' in last_reset_time_str:
                        dt_obj = datetime.fromisoformat(last_reset_time_str.split('.')[0])
                    else:
                        dt_obj = datetime.fromisoformat(last_reset_time_str)
                    last_reset_date = dt_obj.date()
                except (ValueError, TypeError):
                    try:
                        last_reset_date = datetime.strptime(last_reset_time_str, '%Y-%m-%d %H:%M:%S').date()
                    except (ValueError, TypeError):
                        last_reset_date = None

            if last_reset_date != current_utc_date:
                cursor.execute(
                    "UPDATE api_keys SET daily_usage = 0, last_reset_time = ? WHERE id = ?",
                    (datetime.utcnow(), key['id'])
                )
                key['daily_usage'] = 0
            
            # 检查Key是否在每日限额内
            if key['daily_limit'] == -1 or key['daily_usage'] < key['daily_limit']:
                valid_keys.append(key)
        
        conn.commit()
        
        # 按总使用次数排序
        valid_keys.sort(key=lambda x: x.get('usage_count', 0))
        return valid_keys

def update_key_usage(key_id: int) -> None:
    """更新API Key的使用次数和每日使用量。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_keys SET usage_count = usage_count + 1, daily_usage = daily_usage + 1, last_used = CURRENT_TIMESTAMP WHERE id = ?",
            (key_id,)
        )
        conn.commit()

# --- Usage Log CRUD ---

def log_usage(api_key_id: int, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, cost: float, status: int) -> None:
    """记录一次API调用。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO usage_logs (api_key_id, model, prompt_tokens, completion_tokens, total_tokens, cost, response_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (api_key_id, model, prompt_tokens, completion_tokens, total_tokens, cost, status)
        )
        conn.commit()

def get_usage_logs(page: int, page_size: int, **filters) -> Dict[str, Any]:
    """获取带筛选和分页的调用记录。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        where_conditions = []
        params = []
        
        if filters.get("key_filter"):
            where_conditions.append("ul.api_key_id = ?")
            params.append(filters["key_filter"])
        if filters.get("model_filter"):
            where_conditions.append("ul.model = ?")
            params.append(filters["model_filter"])
        if filters.get("status_filter") == "200":
            where_conditions.append("ul.response_status = 200")
        elif filters.get("status_filter") == "400":
            where_conditions.append("ul.response_status >= 400")
        if filters.get("date_filter"):
            where_conditions.append("DATE(ul.request_time) = ?")
            params.append(filters["date_filter"])
            
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        count_query = f"SELECT COUNT(*) FROM usage_logs ul JOIN api_keys ak ON ul.api_key_id = ak.id WHERE {where_clause}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT ul.request_time, ak.key_name, ul.model, ul.prompt_tokens, ul.completion_tokens, ul.total_tokens, ul.cost, ul.response_status
            FROM usage_logs ul
            JOIN api_keys ak ON ul.api_key_id = ak.id
            WHERE {where_clause}
            ORDER BY ul.request_time DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_query, params + [page_size, offset])
        logs = [dict(row) for row in cursor.fetchall()]
        
        return {
            "logs": logs,
            "total_records": total_records,
            "total_pages": (total_records + page_size - 1) // page_size
        }

# --- Free Models CRUD ---

def get_free_models() -> List[str]:
    """获取所有启用的免费模型ID。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT model_id FROM free_models WHERE is_active = TRUE")
        return [row[0] for row in cursor.fetchall()]

def update_free_models(models: List[Dict[str, Any]]) -> None:
    """用新的模型列表更新数据库。"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM free_models")
            
            # 准备插入数据，包含新的字段
            insert_data = []
            for m in models:
                model_id = m.get('id', '')
                model_name = m.get('name', model_id)
                context_length = m.get('context_length')
                
                # 从描述中提取参数量信息
                parameters = _extract_parameters_from_description(m.get('description', ''))
                
                insert_data.append((model_id, model_name, True, context_length, parameters))
            
            cursor.executemany(
                "INSERT INTO free_models (model_id, model_name, is_active, context_length, parameters) VALUES (?, ?, ?, ?, ?)",
                insert_data
            )
            conn.commit()
            logger.info(f"✅ 成功更新了 {len(models)} 个免费模型到数据库。")
    except Exception as e:
        logger.error(f"❌ 更新免费模型失败: {e}")
        raise


def _extract_parameters_from_description(description: str) -> Optional[str]:
    """从模型描述中提取参数量信息。"""
    import re
    
    if not description:
        return None
    
    # 匹配各种参数量格式
    patterns = [
        # 直接的B/M格式
        r'(\d+(?:\.\d+)?)\s*[Bb][\s-]*parameter',  # "21B parameter", "24B-parameter"
        r'(\d+(?:\.\d+)?)\s*[Bb][\s-]*param',      # "21B param"
        r'(\d+(?:\.\d+)?)\s*[Mm][\s-]*parameter',  # "7M parameter"
        r'(\d+(?:\.\d+)?)\s*[Mm][\s-]*param',      # "7M param"
        
        # 数字+单位+parameter格式
        r'(\d+(?:\.\d+)?)\s+billion[\s-]*parameter', # "21 billion parameter"
        r'(\d+(?:\.\d+)?)\s+million[\s-]*parameter', # "7 million parameter"
        r'(\d+(?:\.\d+)?)\s+[Bb][\s-]*parameter',    # "24 B parameter"
        r'(\d+(?:\.\d+)?)\s+[Mm][\s-]*parameter',    # "7 M parameter"
        
        # active parameter格式
        r'(\d+(?:\.\d+)?)\s*[Bb]\s+active\s+parameter', # "13B active parameter"
        r'(\d+(?:\.\d+)?)\s*[Mm]\s+active\s+parameter', # "7M active parameter"
        
        # parameter count格式
        r'(\d+(?:\.\d+)?)\s*[Bb][\s-]*parameter[\s-]*count', # "671 B-parameter"
        r'(\d+(?:\.\d+)?)\s*[Mm][\s-]*parameter[\s-]*count',
        
        # 其他变体
        r'(\d+(?:\.\d+)?)\s*billion\s+param',        # "21 billion param"
        r'(\d+(?:\.\d+)?)\s*million\s+param',        # "7 million param"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, description, re.IGNORECASE)
        if matches:
            # 返回找到的第一个参数量
            param_value = matches[0]
            # 确定单位
            if any(x in pattern.lower() for x in ['b', 'billion']):
                return f"{param_value}B"
            elif any(x in pattern.lower() for x in ['m', 'million']):
                return f"{param_value}M"
            else:
                return f"{param_value}B"  # 默认为B
    
    return None

def get_all_free_models_with_status() -> List[Dict[str, Any]]:
    """获取所有免费模型及其激活状态。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT model_id, model_name, is_active, context_length, parameters FROM free_models ORDER BY model_id")
        return [dict(row) for row in cursor.fetchall()]

def get_model_context_length(model_id: str) -> Optional[int]:
    """获取指定模型的上下文长度。"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_length FROM free_models WHERE model_id = ? AND is_active = 1",
                (model_id,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
    except Exception as e:
        logger.error(f"获取模型 {model_id} 的上下文长度失败: {e}")
        return None

# --- Stats ---

def get_today_stats() -> Dict[str, Any]:
    """获取今日的总体使用统计。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), SUM(total_tokens), COUNT(DISTINCT model)
            FROM usage_logs
            WHERE DATE(request_time) = DATE('now')
        """)
        stats = cursor.fetchone()
        return {
            "total_requests": stats[0] or 0,
            "total_tokens": stats[1] or 0,
            "unique_models": stats[2] or 0
        }

def get_model_stats() -> List[Dict[str, Any]]:
    """获取Top 10模型的使用统计。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT model, COUNT(*) as usage_count, SUM(total_tokens) as total_tokens
            FROM usage_logs
            GROUP BY model
            ORDER BY usage_count DESC
            LIMIT 10
        """)
        return [dict(row) for row in cursor.fetchall()]

# --- Filter Options ---

def get_filter_options() -> Dict[str, List]:
    """获取用于前端筛选的选项。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, key_name FROM api_keys ORDER BY key_name")
        keys = [dict(row) for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT model FROM usage_logs ORDER BY model")
        models = [row[0] for row in cursor.fetchall()]
        return {"keys": keys, "models": models}