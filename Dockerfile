FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装Chrome和依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 安装Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 安装Chromedriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1-3) \
    && CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") \
    && wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip -d /usr/local/bin \
    && rm chromedriver_linux64.zip \
    && chmod +x /usr/local/bin/chromedriver

# 复制需求文件并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建日志目录
RUN mkdir -p /logs && chmod 777 /logs

# 复制代码
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    REDIS_PASSWORD="" \
    REDIS_DB=0 \
    TASK_QUEUE=chrome_crawler_tasks \
    RESULT_QUEUE=chrome_crawler_results \
    MAX_CONCURRENT_TASKS=5 \
    DEFAULT_SCROLL_INTERVAL=3 \
    DEFAULT_VISIT_DURATION=60 \
    BROWSER_TIMEOUT=30 \
    TASK_POLL_INTERVAL=5 \
    STATS_UPDATE_INTERVAL=10

# 容器启动命令
CMD ["python", "crawler.py"]
