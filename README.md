# 无头Chrome爬虫服务

这是一个基于Docker的无头Chrome爬虫服务，用于自动访问URL并模拟页面滚动行为。

## 功能特点

- 基于无头Chrome和Selenium实现的自动化浏览
- 从Redis队列读取任务URL
- 自动模拟页面滚动行为（每3秒滚动一次）
- 访问时长控制（默认1分钟后关闭）
- 并发任务控制（可配置最大同时运行的Chrome实例数）
- 资源优化（闲置时自动关闭，节省服务器资源）
- 结果反馈（将处理结果存入Redis队列）

## 快速开始

### 前提条件

- Docker
- Redis服务器

### 构建Docker镜像

```bash
# 给构建脚本执行权限
chmod +x build_and_deploy.sh

# 运行构建脚本
./build_and_deploy.sh
```

### 运行容器

```bash
docker run -d \
  --name headless-chrome-crawler \
  -e REDIS_HOST=<redis_host> \
  -e REDIS_PORT=<redis_port> \
  -e REDIS_PASSWORD=<redis_password> \
  -e REDIS_DB=0 \
  -e MAX_CONCURRENT_TASKS=3 \
  -e TASK_QUEUE_KEY=headless_chrome_tasks \
  -e RESULT_QUEUE_KEY=headless_chrome_results \
  -e CHROME_SCROLL_INTERVAL=3.0 \
  -e CHROME_TASK_DURATION=60 \
  -e CHROME_IDLE_TIMEOUT=300 \
  -e CHROME_MAX_MEMORY=1GB \
  headless-chrome-crawler:latest
```

## 配置参数

| 环境变量 | 说明 | 默认值 |
|------------|-------------|-------------|
| REDIS_HOST | Redis服务器地址 | localhost |
| REDIS_PORT | Redis服务器端口 | 6379 |
| REDIS_PASSWORD | Redis密码 | (空) |
| REDIS_DB | Redis数据库编号 | 0 |
| TASK_QUEUE_KEY | 任务队列的key | headless_chrome_tasks |
| RESULT_QUEUE_KEY | 结果队列的key | headless_chrome_results |
| MAX_CONCURRENT_TASKS | 最大并发任务数 | 3 |
| CHROME_SCROLL_INTERVAL | 页面滚动间隔(秒) | 3.0 |
| CHROME_TASK_DURATION | 任务执行时长(秒) | 60 |
| CHROME_IDLE_TIMEOUT | 空闲超时时间(秒) | 300 |
| CHROME_MAX_MEMORY | Chrome最大内存 | 1GB |

## 数据格式

### 输入任务格式 (Redis队列: TASK_QUEUE_KEY)

```json
{
  "url": "http://example.com",
  "add_time": "2023-01-01 12:00:00"  // 这个字段不会被处理
}
```

### 输出结果格式 (Redis队列: RESULT_QUEUE_KEY)

```json
{
  "task_id": "1620000000000",
  "url": "http://example.com",
  "start_time": "2023-01-01T12:00:00",
  "end_time": "2023-01-01T12:01:00",
  "duration": 60,
  "status": "completed",
  "error": null,
  "scroll_count": 20
}
```

## 监控和调试

查看容器日志:

```bash
docker logs -f headless-chrome-crawler
```
