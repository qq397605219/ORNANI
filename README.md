# OpenRouter API Proxy

一个基于FastAPI的OpenRouter API代理服务，支持多API Key轮询、免费模型过滤、智能Token管理和使用统计。

## ✨ 功能特性

- 🔄 **多Key轮询**: 支持多个OpenRouter API Key的负载均衡
- 🆓 **免费模型过滤**: 仅允许使用免费模型，节省成本
- 🧠 **智能Token管理**: 根据模型上下文长度动态设置max_tokens
- 📊 **使用统计**: 详细记录API使用情况和Token消耗
- 🔐 **访问控制**: 统一密码访问，保护API资源
- 🎨 **Web管理界面**: 美观的后台管理系统，支持模型信息展示
- 📈 **模型信息展示**: 显示模型参数量、最大上下文长度等详细信息

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置服务

编辑 `config.json` 文件，配置您的设置：

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "admin": {
    "password": "admin123"
  },
  "openrouter": {
    "base_url": "https://openrouter.ai/api/v1",
    "http_referer": "https://your-domain.com",
    "x_title": "OpenRouter Proxy",
    "auto_update_models_on_startup": true
  }
}
```

### 3. 启动服务

```bash
# 方式1: 直接启动
python main.py

# 方式2: 使用启动脚本
python start.py

# 方式3: 使用批处理文件 (Windows)
start.bat
```

### 4. 访问管理后台

打开浏览器访问: http://localhost:8000/admin

默认管理员密码: `admin123`

## 📖 API使用

### 聊天完成接口

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer admin123" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-2-9b-it:free",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

**智能Token管理特性：**
- 如果不指定 `max_tokens`，系统会根据模型的上下文长度和输入消息自动计算
- 使用tiktoken库精确估算Token数量
- 确保不会超出模型的上下文限制

### 获取模型列表

```bash
curl -X GET "http://localhost:8000/v1/models" \
  -H "Authorization: Bearer admin123"
```

## 🎯 支持的免费模型

系统会在启动时自动从OpenRouter获取所有免费模型（带有`:free`后缀的模型），包括但不限于：

- `qwen/qwen3-coder:free` - Qwen3 Coder (Free)
- `google/gemma-2-9b-it:free` - Gemma 2 9B (Free)
- `meta-llama/llama-3.1-8b-instruct:free` - Llama 3.1 8B (Free)
- `microsoft/phi-3-mini-128k-instruct:free` - Phi-3 Mini (Free)
- `openai/gpt-oss-20b:free` - GPT OSS 20B (Free)
- `moonshotai/kimi-k2:free` - Kimi K2 (Free)
- `z-ai/glm-4.5-air:free` - GLM 4.5 Air (Free)
- 以及其他50+个免费模型...

**🔄 动态更新特性：**
- 启动时自动获取最新免费模型列表
- 支持手动刷新模型列表
- 无需维护硬编码的模型列表
- 自动识别所有带有`:free`后缀的模型

**🧠 智能Token管理：**
- 自动获取每个模型的上下文长度限制
- 根据输入消息长度动态计算合适的max_tokens
- 使用tiktoken库精确估算Token数量
- 避免超出模型上下文限制，提高API成功率

## ⚙️ 配置说明

### 环境变量

- `ADMIN_PASSWORD`: 管理员密码 (默认: admin123)
- `PORT`: 服务端口 (默认: 8000)

### 配置文件

编辑 `config.json` 文件可以修改更多配置:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "admin": {
    "password": "admin123"
  },
  "database": {
    "url": "openrouter_proxy.db"
  },
  "openrouter": {
    "base_url": "https://openrouter.ai/api/v1",
    "http_referer": "https://your-domain.com",
    "x_title": "OpenRouter Proxy",
    "free_model_suffix": ":free",
    "auto_update_models_on_startup": true,
    "model_cache_timeout": 3600,
    "request_timeout": 60.0
  },
  "proxy": {
    "load_balance_strategy": "round_robin"
  }
}
```

## 🔧 管理功能

### API Key管理

- 添加/删除OpenRouter API Key
- 查看Key使用统计和每日限制
- 启用/禁用特定Key
- 自动重置每日使用量

### 免费模型管理

- 查看所有免费模型列表
- 显示模型参数量和最大上下文长度
- 启用/禁用特定模型
- 手动刷新模型列表

### 使用统计

- 今日请求数统计
- Token使用量统计
- 模型使用分布
- 详细使用日志
- 分页和筛选功能

## 🛡️ 安全特性

- 统一访问密码控制
- API Key安全存储
- 请求日志记录
- 免费模型限制

## 📁 项目结构

```
openrouter-proxy/
├── main.py                    # 主应用文件
├── config.py                  # 配置管理模块
├── config.json                # 配置文件
├── start.py                   # 启动脚本
├── start.bat                  # Windows批处理启动文件
├── requirements.txt           # 依赖列表
├── migrate_db.py              # 数据库迁移脚本
├── test_max_tokens.py         # Token管理测试脚本
├── app/                       # 应用核心模块
│   ├── __init__.py
│   ├── crud.py                # 数据库操作
│   ├── database.py            # 数据库连接和初始化
│   ├── schemas.py             # 数据模型
│   ├── routers/               # 路由模块
│   │   ├── admin.py           # 管理后台API
│   │   └── proxy.py           # 代理服务API
│   └── services/              # 服务模块
│       ├── key_manager.py     # API Key管理
│       └── openrouter_client.py # OpenRouter客户端
├── templates/                 # HTML模板
│   └── admin.html             # 管理后台界面
└── openrouter_proxy.db        # SQLite数据库 (自动创建)
```

## 🛠️ 技术栈

- **后端框架**: FastAPI
- **数据库**: SQLite
- **HTTP客户端**: httpx
- **Token计算**: tiktoken
- **前端**: 原生HTML/CSS/JavaScript
- **部署**: uvicorn ASGI服务器

## 🔄 负载均衡策略

目前支持以下负载均衡策略:

1. **轮询** (默认): 按顺序轮流使用API Key
2. **最少使用**: 优先使用使用次数最少的API Key
3. **随机**: 随机选择可用的API Key

可在 `config.json` 中的 `proxy.load_balance_strategy` 字段配置。

## 📝 使用记录

系统会自动记录以下信息:

- 使用的API Key
- 请求的模型
- Token使用量 (prompt + completion + total)
- 请求时间和响应状态
- 详细的请求日志
- 支持按Key、模型、状态、日期筛选
- 分页显示，便于查看历史记录

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📄 许可证

本项目采用 WTFPL (Do What The F*ck You Want To Public License) 许可证。

```
            DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE
                    Version 2, December 2004

 Copyright (C) 2004 Sam Hocevar <sam@hocevar.net>

 Everyone is permitted to copy and distribute verbatim or modified
 copies of this license document, and changing it is allowed as long
 as the name is changed.

            DO WHAT THE F*CK YOU WANT TO PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. You just DO WHAT THE F*CK YOU WANT TO.
```

简单来说：你想怎么用就怎么用！ 🎉