#!/bin/bash

# 定义镜像和容器名称
IMAGE_NAME="openrouter-proxy"
CONTAINER_NAME="openrouter-proxy-container"

# 检查 .env 文件是否存在，如果不存在则从 .env.example 创建
if [ ! -f .env ]; then
    echo "创建 .env 文件..."
    cp .env.example .env
fi

# 构建 Docker 镜像
echo "正在构建 Docker 镜像..."
docker build -t $IMAGE_NAME .

# 停止并移除旧的容器（如果存在）
if [ $(docker ps -a -q -f name=^/${CONTAINER_NAME}$) ]; then
    echo "正在停止并移除旧的容器..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# 启动新的 Docker 容器
echo "正在启动新的 Docker 容器..."
docker run -d \
    --name $CONTAINER_NAME \
    -p 8000:8000 \
    --env-file .env \
    $IMAGE_NAME

echo "服务已启动！"
echo "访问 http://localhost:8000"