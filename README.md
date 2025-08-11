# OpenRouter API Proxy

一个基于FastAPI的OpenRouter API代理服务，支持多API Key轮询、免费模型过滤和使用统计管理。

## ✨ 功能特性

- 🔄 **多Key轮询**: 支持多个OpenRouter API Key的负载均衡
- 🆓 **免费模型过滤**: 仅允许使用免费模型，节省成本
- 📊 **使用统计**: 详细记录API使用情况和Token消耗
- 🔐 **访问控制**: 统一密码访问，保护API资源
- 🎨 **Web管理界面**: 美观的后台管理系统

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python start.py
```

### 3. 访问管理后台

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

## ⚙️ 配置说明

### 环境变量

- `ADMIN_PASSWORD`: 管理员密码 (默认: admin123)
- `PORT`: 服务端口 (默认: 8000)

### 配置文件

编辑 `config.py` 文件可以修改更多配置:

- 免费模型列表
- 负载均衡策略
- 请求超时时间
- 等等...

## 🔧 管理功能

### API Key管理

- 添加/删除OpenRouter API Key
- 查看Key使用统计
- 启用/禁用特定Key

### 使用统计

- 今日请求数统计
- Token使用量统计
- 模型使用分布
- 详细使用日志

## 🛡️ 安全特性

- 统一访问密码控制
- API Key安全存储
- 请求日志记录
- 免费模型限制

## 📁 项目结构

```
openrouter-proxy/
├── main.py              # 主应用文件
├── config.py            # 配置文件
├── start.py             # 启动脚本
├── requirements.txt     # 依赖列表
├── templates/           # HTML模板
│   └── admin.html       # 管理后台界面
└── openrouter_proxy.db  # SQLite数据库 (自动创建)
```

## 🔄 负载均衡策略

目前支持以下负载均衡策略:

1. **最少使用** (默认): 优先使用使用次数最少的API Key
2. **轮询**: 按顺序轮流使用API Key
3. **随机**: 随机选择可用的API Key

## 📝 使用记录

系统会自动记录以下信息:

- 使用的API Key
- 请求的模型
- Token使用量 (prompt + completion)
- 请求时间
- 响应状态

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个项目！

## 📄 许可证

MIT License