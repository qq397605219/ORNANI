#!/usr/bin/env python3
"""
测试动态max_tokens功能的脚本
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:8000"
API_TOKEN = "admin123"  # 使用配置中的admin密码

def test_dynamic_max_tokens():
    """测试动态max_tokens功能"""
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 测试用例1: 短消息
    short_message_payload = {
        "model": "openai/gpt-oss-20b:free",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ]
        # 注意：没有指定max_tokens，应该由系统自动计算
    }
    
    # 测试用例2: 长消息
    long_message_payload = {
        "model": "openai/gpt-oss-20b:free", 
        "messages": [
            {"role": "user", "content": "Please write a detailed explanation about artificial intelligence, machine learning, deep learning, neural networks, and their applications in modern technology. Include examples and discuss the future prospects of AI development." * 10}
        ]
        # 注意：没有指定max_tokens，应该由系统自动计算
    }
    
    print("🧪 测试动态max_tokens功能")
    print("=" * 50)
    
    # 测试短消息
    print("\n📝 测试用例1: 短消息")
    print(f"消息内容: {short_message_payload['messages'][0]['content']}")
    print(f"消息长度: {len(short_message_payload['messages'][0]['content'])} 字符")
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers=headers,
            json=short_message_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            usage = data.get("usage", {})
            print(f"✅ 请求成功")
            print(f"📊 Token使用情况:")
            print(f"   - 输入tokens: {usage.get('prompt_tokens', 'N/A')}")
            print(f"   - 输出tokens: {usage.get('completion_tokens', 'N/A')}")
            print(f"   - 总tokens: {usage.get('total_tokens', 'N/A')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
    
    # 测试长消息
    print("\n📝 测试用例2: 长消息")
    print(f"消息长度: {len(long_message_payload['messages'][0]['content'])} 字符")
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers=headers,
            json=long_message_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            usage = data.get("usage", {})
            print(f"✅ 请求成功")
            print(f"📊 Token使用情况:")
            print(f"   - 输入tokens: {usage.get('prompt_tokens', 'N/A')}")
            print(f"   - 输出tokens: {usage.get('completion_tokens', 'N/A')}")
            print(f"   - 总tokens: {usage.get('total_tokens', 'N/A')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

def test_model_context_info():
    """测试模型上下文信息获取"""
    print("\n🔍 测试模型上下文信息")
    print("=" * 50)
    
    # 直接测试数据库函数
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from app import crud
    
    test_models = [
        "openai/gpt-oss-20b:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "google/gemma-3n-e2b-it:free"
    ]
    
    for model in test_models:
        context_length = crud.get_model_context_length(model)
        print(f"📋 模型: {model}")
        print(f"   上下文长度: {context_length if context_length else '未知'}")

if __name__ == "__main__":
    test_model_context_info()
    test_dynamic_max_tokens()