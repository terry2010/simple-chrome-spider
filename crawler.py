#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Optional, List
import threading
import redis
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("HeadlessChromeService")

class Config:
    """配置类，从环境变量读取配置"""
    
    def __init__(self):
        # Redis配置
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # 任务队列配置
        self.task_queue_key = os.getenv("TASK_QUEUE_KEY", "headless_chrome_tasks")
        self.result_queue_key = os.getenv("RESULT_QUEUE_KEY", "headless_chrome_results")
        
        # 并发控制
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
        
        # Chrome配置
        self.chrome_scroll_interval = float(os.getenv("CHROME_SCROLL_INTERVAL", "3.0"))
        self.chrome_task_duration = int(os.getenv("CHROME_TASK_DURATION", "60"))
        self.chrome_idle_timeout = int(os.getenv("CHROME_IDLE_TIMEOUT", "300"))
        self.chrome_max_memory = os.getenv("CHROME_MAX_MEMORY", "1GB")

class ChromeTask:
    """Chrome任务类，管理单个Chrome任务的生命周期"""
    
    def __init__(self, task_id: str, url: str, config: Config):
        self.task_id = task_id
        self.url = url
        self.config = config
        self.driver = None
        self.start_time = None
        self.end_time = None
        self.status = "pending"
        self.error = None
        self.scroll_count = 0
        
    def setup_driver(self):
        """设置并启动Chrome驱动"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"--disable-extensions")
        chrome_options.add_argument(f"--memory-limit={self.config.chrome_max_memory}")
        chrome_options.add_argument("--window-size=1920,1080")
        
        logger.info(f"启动Chrome任务: {self.task_id}, URL: {self.url}")
        
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def execute(self):
        """执行Chrome任务"""
        try:
            self.status = "running"
            self.start_time = datetime.now()
            
            # 启动浏览器
            self.setup_driver()
            
            # 访问URL
            self.driver.get(self.url)
            logger.info(f"成功访问URL: {self.url}")
            
            end_time = time.time() + self.config.chrome_task_duration
            
            # 每隔指定时间向下滚动，直到达到总时长
            while time.time() < end_time:
                # 向下滚动
                self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                self.scroll_count += 1
                logger.info(f"Task {self.task_id} - 滚动第 {self.scroll_count} 次")
                
                # 等待滚动间隔
                time.sleep(self.config.chrome_scroll_interval)
            
            self.status = "completed"
            
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error(f"任务 {self.task_id} 执行失败: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info(f"关闭Chrome浏览器实例: {self.task_id}")
            
            self.end_time = datetime.now()
            
    def get_result(self) -> Dict:
        """获取任务执行结果"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        
        return {
            "task_id": self.task_id,
            "url": self.url,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": duration,
            "status": self.status,
            "error": self.error,
            "scroll_count": self.scroll_count
        }

class HeadlessChromeService:
    """无头Chrome服务，管理任务队列和Chrome实例"""
    
    def __init__(self):
        self.config = Config()
        self.redis_client = self._connect_redis()
        self.active_tasks: Dict[str, threading.Thread] = {}
        self.active_tasks_lock = threading.Lock()
        self.running = True
        self.last_activity_time = time.time()
        
        # 设置信号处理
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info(f"无头Chrome服务初始化完成，最大并发任务数: {self.config.max_concurrent_tasks}")
        
    def _connect_redis(self) -> redis.Redis:
        """连接到Redis"""
        try:
            client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                password=self.config.redis_password,
                db=self.config.redis_db,
                decode_responses=True
            )
            client.ping()
            logger.info(f"成功连接到Redis: {self.config.redis_host}:{self.config.redis_port}")
            return client
        except redis.ConnectionError as e:
            logger.error(f"无法连接到Redis: {str(e)}")
            sys.exit(1)
    
    def _handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info("接收到关闭信号，正在优雅退出...")
        self.running = False
        
        # 等待所有活跃任务完成
        logger.info("等待所有活跃任务完成...")
        for task_id, thread in list(self.active_tasks.items()):
            thread.join()
            
        logger.info("服务已退出")
        sys.exit(0)
    
    def _check_idle_timeout(self):
        """检查空闲超时"""
        current_time = time.time()
        if current_time - self.last_activity_time > self.config.chrome_idle_timeout:
            if not self.active_tasks:
                logger.info(f"服务空闲超过 {self.config.chrome_idle_timeout} 秒，退出...")
                self.running = False
                return True
        return False
    
    def _fetch_task(self) -> Optional[Dict]:
        """从Redis队列获取任务"""
        try:
            task_data = self.redis_client.lpop(self.config.task_queue_key)
            if task_data:
                self.last_activity_time = time.time()
                try:
                    return json.loads(task_data)
                except json.JSONDecodeError as e:
                    logger.error(f"无法解析任务数据: {task_data}, 错误: {str(e)}")
            return None
        except redis.RedisError as e:
            logger.error(f"从Redis获取任务时出错: {str(e)}")
            return None
    
    def _save_result(self, result: Dict):
        """将结果保存到Redis"""
        try:
            self.redis_client.rpush(self.config.result_queue_key, json.dumps(result))
            logger.info(f"结果已保存到Redis: {result['task_id']}")
        except redis.RedisError as e:
            logger.error(f"保存结果到Redis时出错: {str(e)}")
    
    def _process_task(self, task_data: Dict):
        """处理单个任务"""
        task_id = str(int(time.time() * 1000))  # 使用时间戳作为任务ID
        url = task_data.get("url")
        
        if not url:
            logger.error(f"任务缺少URL: {task_data}")
            return
        
        logger.info(f"处理任务: {task_id}, URL: {url}")
        
        # 创建并执行Chrome任务
        task = ChromeTask(task_id, url, self.config)
        task.execute()
        
        # 保存结果
        result = task.get_result()
        self._save_result(result)
        
        # 清理任务
        with self.active_tasks_lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
                
        logger.info(f"任务完成: {task_id}, 状态: {result['status']}")
    
    def _start_task_thread(self, task_data: Dict):
        """启动任务线程"""
        task_id = str(int(time.time() * 1000))
        
        # 创建线程
        thread = threading.Thread(
            target=self._process_task,
            args=(task_data,),
            name=f"task-{task_id}"
        )
        
        # 注册线程
        with self.active_tasks_lock:
            self.active_tasks[task_id] = thread
        
        # 启动线程
        thread.start()
        logger.info(f"启动任务线程: {task_id}")
    
    def run(self):
        """运行服务主循环"""
        logger.info("无头Chrome服务启动...")
        
        while self.running:
            try:
                # 检查空闲超时
                if self._check_idle_timeout():
                    break
                
                # 检查是否可以接受新任务
                with self.active_tasks_lock:
                    active_task_count = len(self.active_tasks)
                
                if active_task_count >= self.config.max_concurrent_tasks:
                    logger.debug(f"当前活跃任务数 {active_task_count} 已达到最大值 {self.config.max_concurrent_tasks}，等待...")
                    time.sleep(1)
                    continue
                
                # 获取任务
                task_data = self._fetch_task()
                
                if not task_data:
                    # 没有任务，等待一段时间
                    time.sleep(1)
                    continue
                
                # 启动任务
                self._start_task_thread(task_data)
                
            except Exception as e:
                logger.error(f"服务循环中出现未处理的异常: {str(e)}")
                time.sleep(5)  # 避免错误循环过快
        
        logger.info("服务主循环结束")

if __name__ == "__main__":
    service = HeadlessChromeService()
    service.run()
