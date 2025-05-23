#!/bin/bash

# 无头Chrome爬虫服务启动脚本

# 设置默认值
REDIS_HOST=${1:-"localhost"}
REDIS_PASSWORD=${2:-""}
MAX_CONCURRENT_TASKS=${3:-5}
REDIS_PORT=${4:-6379}
REDIS_DB=${5:-0}
TASK_QUEUE=${6:-"chrome_crawler_tasks"}
RESULT_QUEUE=${7:-"chrome_crawler_results"}
LOG_DIR=${8:-"/var/log/headless-chrome-crawler"}

# 显示配置信息
echo "========================================"
echo "启动无头Chrome爬虫服务"
echo "========================================"
echo "Redis服务器: $REDIS_HOST:$REDIS_PORT"
echo "Redis密码: ${REDIS_PASSWORD:+已设置}"
echo "Redis数据库: $REDIS_DB"
echo "任务队列: $TASK_QUEUE"
echo "结果队列: $RESULT_QUEUE"
echo "最大并发任务数: $MAX_CONCURRENT_TASKS"
echo "日志目录: $LOG_DIR"
echo "========================================"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 停止并移除已存在的容器（如果有）
if docker ps -a | grep -q "headless-chrome-crawler"; then
    echo "正在停止并移除已存在的容器..."
    docker stop headless-chrome-crawler >/dev/null 2>&1 || true
    docker rm headless-chrome-crawler >/dev/null 2>&1 || true
fi

# 启动Docker容器
echo "正在启动容器..."
docker run -d \
    --name headless-chrome-crawler \
    --restart unless-stopped \
    -e REDIS_HOST="$REDIS_HOST" \
    -e REDIS_PORT="$REDIS_PORT" \
    -e REDIS_PASSWORD="$REDIS_PASSWORD" \
    -e REDIS_DB="$REDIS_DB" \
    -e TASK_QUEUE="$TASK_QUEUE" \
    -e RESULT_QUEUE="$RESULT_QUEUE" \
    -e MAX_CONCURRENT_TASKS="$MAX_CONCURRENT_TASKS" \
    -v "$LOG_DIR:/logs" \
    headless-chrome-crawler:latest

# 检查容器是否成功启动
if [ $? -eq 0 ]; then
    CONTAINER_ID=$(docker ps -q -f name=headless-chrome-crawler)
    echo "容器已成功启动！"
    echo "容器ID: $CONTAINER_ID"
    echo "查看日志: docker logs -f headless-chrome-crawler"
    echo "========================================"
else
    echo "容器启动失败！请检查错误信息。"
    echo "========================================"
    exit 1
fi

# 显示状态
echo "服务状态:"
docker ps -f name=headless-chrome-crawler
echo "========================================"
