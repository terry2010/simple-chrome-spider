#!/bin/bash

# 设置变量
REPOSITORY="terry2010/simple-chrome-spider"
TAG_PREFIX="$(date +'%Y%m%d%H%M%S')"
LATEST_TAG="$REPOSITORY:latest"
VERSION_TAG="$REPOSITORY:$TAG_PREFIX"

# 显示构建信息
echo "========================================"
echo "构建并推送Docker镜像"
echo "========================================"
echo "仓库: $REPOSITORY"
echo "标签: $TAG_PREFIX (latest 和 $TAG_PREFIX)"
echo ""

# 步骤1: 构建Docker镜像
echo "步骤1/4: 正在构建Docker镜像..."
docker build -t "$LATEST_TAG" -t "$VERSION_TAG" .

# 检查构建是否成功
if [ $? -ne 0 ]; then
    echo "错误: Docker镜像构建失败"
    exit 1
fi

# 步骤2: 登录Docker Hub
echo -e "\n步骤2/4: 登录Docker Hub..."
docker login

# 检查登录是否成功
if [ $? -ne 0 ]; then
    echo "错误: Docker Hub登录失败"
    exit 1
fi

# 步骤3: 推送latest标签
echo -e "\n步骤3/4: 推送 latest 标签..."
docker push "$LATEST_TAG"

# 检查推送是否成功
if [ $? -ne 0 ]; then
    echo "错误: 推送 latest 标签失败"
    exit 1
fi

# 步骤4: 推送带时间戳的标签
echo -e "\n步骤4/4: 推送 $TAG_PREFIX 标签..."
docker push "$VERSION_TAG"

# 检查推送是否成功
if [ $? -ne 0 ]; then
    echo "错误: 推送 $TAG_PREFIX 标签失败"
    exit 1
fi

# 完成
echo -e "\n========================================"
echo "镜像已成功推送到Docker Hub!"
echo "最新版本: $LATEST_TAG"
echo "带时间戳版本: $VERSION_TAG"
echo "========================================"

# 显示拉取命令
echo "您可以使用以下命令拉取镜像:"
echo "  docker pull $LATEST_TAG"
echo "  或"
echo "  docker pull $VERSION_TAG"
echo "========================================"
