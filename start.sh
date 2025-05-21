#!/bin/bash

# 打印环境变量以供调试
echo "启动无头Chrome爬虫服务..."
echo "Redis配置: ${REDIS_HOST}:${REDIS_PORT}"
echo "最大并发任务数: ${MAX_CONCURRENT_TASKS}"

# 确保日志目录存在
mkdir -p /logs
chmod 777 /logs

# 检查chromedriver是否存在
if ! command -v chromedriver &> /dev/null; then
    echo "chromedriver未找到，正在安装..."
    apt-get update
    apt-get install -y chromium-driver
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver
    chmod +x /usr/local/bin/chromedriver
fi

# 启动爬虫服务
python /app/crawler.py
