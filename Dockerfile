FROM python:3.9-slim

# 安装Chrome和必要的依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-kacst fonts-symbola fonts-noto fonts-freefont-ttf \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 安装Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 直接安装最新版本的ChromeDriver
RUN apt-get update && apt-get install -y \
    chromium-driver \
    && ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制应用代码和依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"

# 设置入口点
ENTRYPOINT ["sh", "./start.sh"]
