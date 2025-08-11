import sqlite3
import logging
from contextlib import contextmanager

DATABASE_URL = "openrouter_proxy.db"
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """提供一个数据库连接的上下文管理器，确保连接在使用后关闭。"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"数据库连接错误: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """初始化数据库，创建所有必要的表。"""
    logger.info("正在初始化数据库...")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # API Keys表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_name TEXT NOT NULL,
                    api_key TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    daily_limit INTEGER DEFAULT -1,
                    daily_usage INTEGER DEFAULT 0,
                    last_reset_time TIMESTAMP
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
                    is_active BOOLEAN DEFAULT TRUE,
                    context_length INTEGER,
                    parameters TEXT
                )
            ''')
            
            # 为现有表添加新字段（如果不存在）
            try:
                cursor.execute('ALTER TABLE free_models ADD COLUMN context_length INTEGER')
            except sqlite3.OperationalError:
                pass  # 字段已存在
            
            try:
                cursor.execute('ALTER TABLE free_models ADD COLUMN parameters TEXT')
            except sqlite3.OperationalError:
                pass  # 字段已存在
            
            conn.commit()
        logger.info("✅ 数据库初始化成功。")
    except sqlite3.Error as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        raise
