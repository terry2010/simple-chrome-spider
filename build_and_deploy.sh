#!/bin/bash

# 无头Chrome爬虫服务构建和部署脚本

# 确保脚本在出错时退出
set -e

echo "========================================"
echo "构建无头Chrome爬虫服务Docker镜像"
echo "========================================"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 镜像名称和标签
IMAGE_NAME="headless-chrome-crawler"
IMAGE_TAG="latest"

# 构建Docker镜像
echo "正在构建Docker镜像: $IMAGE_NAME:$IMAGE_TAG..."
docker build -t "$IMAGE_NAME:$IMAGE_TAG" .

echo "镜像构建完成!"
echo "========================================"

# 可选：推送到Docker仓库
if [ "$1" == "--push" ]; then
    REGISTRY="$2"
    if [ -z "$REGISTRY" ]; then
        echo "错误: 请指定Docker仓库地址，例如: ./build_and_deploy.sh --push your-registry.com"
        exit 1
    fi
    
    echo "正在将镜像推送到仓库: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG..."
    docker tag "$IMAGE_NAME:$IMAGE_TAG" "$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    docker push "$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    echo "镜像已推送到仓库!"
    echo "========================================"
fi

echo "部署说明:"
echo "--------------------------------------"
echo "要在服务器上运行此容器，请执行以下命令:"
echo ""
echo "docker run -d \\"
echo "  --name headless-chrome-crawler \\"
echo "  -e REDIS_HOST=<redis服务器IP> \\"
echo "  -e REDIS_PORT=6379 \\"
echo "  -e REDIS_PASSWORD=<redis密码> \\"
echo "  -e MAX_CONCURRENT_TASKS=5 \\"
echo "  -v /path/to/logs:/logs \\"
echo "  $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "或者使用 start.sh 脚本启动容器:"
echo "  ./start.sh <redis服务器IP> <redis密码> <最大并发任务数>"
echo "========================================"

echo "构建和部署脚本执行完成!"
