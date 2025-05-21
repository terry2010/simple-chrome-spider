#!/bin/bash

# 设置版本号
VERSION=$(date +%Y%m%d%H%M)
IMAGE_NAME="headless-chrome-crawler"
FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"

echo "构建 Docker 镜像: ${FULL_IMAGE_NAME}"
docker build -t ${FULL_IMAGE_NAME} .

echo "为方便使用，也标记为 latest 版本"
docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:latest

echo "构建完成！"
echo "---------------------------------------------"
echo "您可以使用以下命令运行容器:"
echo "docker run -d \\
  --name headless-chrome-crawler \\
  -e REDIS_HOST=<redis_host> \\
  -e REDIS_PORT=<redis_port> \\
  -e REDIS_PASSWORD=<redis_password> \\
  -e REDIS_DB=0 \\
  -e MAX_CONCURRENT_TASKS=3 \\
  -e TASK_QUEUE_KEY=headless_chrome_tasks \\
  -e RESULT_QUEUE_KEY=headless_chrome_results \\
  -e CHROME_SCROLL_INTERVAL=3.0 \\
  -e CHROME_TASK_DURATION=60 \\
  -e CHROME_IDLE_TIMEOUT=300 \\
  -e CHROME_MAX_MEMORY=1GB \\
  ${IMAGE_NAME}:latest"
