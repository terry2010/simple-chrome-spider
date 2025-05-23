# 废弃了， 只有prompt有点用


# 无头Chrome爬虫服务

基于Docker的无头Chrome浏览器爬虫服务，用于自动访问URL并模拟页面滚动。服务从Redis队列读取任务，支持自定义任务配置和回调。

## 功能特点

- 使用无头Chrome浏览器自动访问URL
- 支持自定义页面滚动和操作配置
- 可配置访问时长和滚动间隔
- 支持多种数据收集（截图、HTML源码、控制台日志等）
- 结果回调支持
- 并发控制，可设置最大同时运行Chrome任务数
- 闲时自动关闭Chrome进程，节省服务器资源
- 完整的日志和状态监控

## 快速开始

### 部署方式

在支持Docker的CentOS服务器上，只需运行以下命令即可启动服务：

```bash
docker run -d \
  --name headless-chrome-crawler \
  -e REDIS_HOST=<redis服务器IP> \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=<redis密码> \
  -e MAX_CONCURRENT_TASKS=5 \
  -v /path/to/logs:/logs \
  headless-chrome-crawler:latest
```

### 环境变量配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| REDIS_HOST | Redis服务器地址 | localhost |
| REDIS_PORT | Redis服务器端口 | 6379 |
| REDIS_PASSWORD | Redis服务器密码 | "" |
| REDIS_DB | Redis数据库编号 | 0 |
| TASK_QUEUE | 任务队列名称 | chrome_crawler_tasks |
| RESULT_QUEUE | 结果队列名称 | chrome_crawler_results |
| MAX_CONCURRENT_TASKS | 最大并发任务数 | 5 |
| DEFAULT_SCROLL_INTERVAL | 默认滚动间隔(秒) | 3 |
| DEFAULT_VISIT_DURATION | 默认访问时长(秒) | 60 |
| BROWSER_TIMEOUT | 浏览器超时时间(秒) | 30 |
| TASK_POLL_INTERVAL | 任务轮询间隔(秒) | 5 |
| STATS_UPDATE_INTERVAL | 状态更新间隔(秒) | 10 |

## 任务格式

Redis队列中的任务格式为JSON字符串：

```json
{
  "url": "http://example.com",
  "add_time": "2023-01-01T12:00:00",
  "task": [
    {"do": "page_down"},
    {"do": "sleep", "time": 3},
    {"do": "page_down"},
    {"do": "sleep", "time": 3},
    {"do": "screenshot"}
  ],
  "callback_url": "http://callback-server.com/result",
  "callback_data": ["screenshot", "page_source", "title", "console_log"]
}
```

### 任务参数说明

- `url`: 要访问的网址（必填）
- `add_time`: 任务添加时间（可选，不会被处理）
- `task`: 任务操作数组，支持的操作有：
  - `{"do": "page_down"}`: 向下滚动一页
  - `{"do": "sleep", "time": 秒数}`: 等待指定秒数
  - `{"do": "screenshot"}`: 截取页面截图
  - `{"do": "get_title"}`: 获取页面标题
  - `{"do": "get_source"}`: 获取页面源码
  - `{"do": "get_console_log"}`: 获取控制台日志
- `callback_url`: 结果回调URL（可选）
- `callback_data`: 要返回的数据类型数组，支持：
  - `screenshot`: 页面截图（Base64编码）
  - `page_source` 或 `html`: 页面HTML源码
  - `title`: 页面标题
  - `console_log`: 控制台日志

如果不提供`task`数组，将执行默认操作：每3秒向下滚动一次，持续1分钟。

## 结果格式

任务结果将写入Redis结果队列，格式为JSON字符串：

```json
{
  "task_id": "任务ID",
  "url": "访问的URL",
  "start_time": "开始时间",
  "end_time": "结束时间",
  "total_duration": 访问总时长(秒),
  "urls_visited": [
    {"url": "URL1", "time": "访问时间1"},
    {"url": "URL2", "time": "访问时间2"}
  ],
  "final_url": "最终URL",
  "success": true/false,
  "error": "错误信息(如果有)",
  "title": "页面标题",
  "screenshot": "Base64编码的截图(如果请求)",
  "page_source": "HTML源码(如果请求)",
  "console_log": ["控制台日志1", "控制台日志2"](如果请求)
}
```

## 状态监控

服务会将运行状态写入`/logs/statics.log`文件，格式为JSON：

```json
{
  "timestamp": "2023-01-01T12:00:00",
  "running_tasks": 3,
  "max_concurrent_tasks": 5,
  "available_slots": 2,
  "tasks": [
    {
      "task_id": "任务ID1",
      "url": "URL1",
      "start_time": "开始时间1",
      "duration": 25.5
    },
    {
      "task_id": "任务ID2",
      "url": "URL2",
      "start_time": "开始时间2",
      "duration": 10.2
    }
  ]
}
```

## 构建镜像

要构建Docker镜像，请运行：

```bash
./build_and_deploy.sh
```

或手动构建：

```bash
docker build -t headless-chrome-crawler:latest .
```
