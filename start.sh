#!/bin/bash

# 打印环境变量以供调试
echo "启动无头Chrome爬虫服务..."
echo "Redis配置: ${REDIS_HOST}:${REDIS_PORT}"
echo "最大并发任务数: ${MAX_CONCURRENT_TASKS}"

# 启动爬虫服务
python /app/crawler.py
