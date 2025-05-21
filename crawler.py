#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import signal
import sys
import subprocess
from datetime import datetime
from typing import Dict, Optional, List
import threading
import redis
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

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
        
        # 状态统计配置
        self.stats_log_path = os.getenv("STATS_LOG_PATH", "/logs/statics.log")
        self.stats_update_interval = int(os.getenv("STATS_UPDATE_INTERVAL", "10"))  # 每10秒更新一次状态

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
        
        # 确保 chromedriver 存在并可执行
        try:
            # 检查chromedriver是否存在
            subprocess.run(["which", "chromedriver"], check=True, stdout=subprocess.PIPE)
            logger.info("chromedriver已安装并在PATH中")
        except subprocess.CalledProcessError:
            logger.warning("chromedriver不在PATH中，尝试安装")
            try:
                # 尝试安装chromedriver
                subprocess.run(["apt-get", "update"], check=True)
                subprocess.run(["apt-get", "install", "-y", "chromium-driver"], check=True)
                subprocess.run(["ln", "-sf", "/usr/bin/chromedriver", "/usr/local/bin/chromedriver"], check=True)
                subprocess.run(["chmod", "+x", "/usr/local/bin/chromedriver"], check=True)
                logger.info("chromedriver安装成功")
            except Exception as e:
                logger.error(f"chromedriver安装失败: {str(e)}")
                raise
        
        # 使用系统已安装的chromedriver
        try:
            # 先尝试使用系统路径
            service = Service()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.warning(f"使用默认路径失败: {str(e)}, 尝试指定路径")
            # 如果失败，尝试指定路径
            service = Service(executable_path="/usr/local/bin/chromedriver")
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
                
                # 更新任务详情中的滚动次数
                self._update_task_details()
                
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
            
    def _update_task_details(self):
        """更新服务中的任务详情"""
        try:
            # 获取HeadlessChromeService实例
            service = self._get_service_instance()
            if service and hasattr(service, 'task_details') and self.task_id in service.task_details:
                with service.active_tasks_lock:
                    service.task_details[self.task_id]['scroll_count'] = self.scroll_count
                    service.task_details[self.task_id]['status'] = self.status
        except Exception as e:
            logger.error(f"更新任务详情时出错: {str(e)}")
    
    def _get_service_instance(self):
        """获取HeadlessChromeService实例"""
        # 尝试从当前线程中获取服务实例
        for thread in threading.enumerate():
            if hasattr(thread, '_target') and thread._target and hasattr(thread._target, '__self__'):
                target_self = thread._target.__self__
                if isinstance(target_self, HeadlessChromeService):
                    return target_self
        return None
            
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
        self.task_details = {}  # 存储正在运行的任务详情
        self.stats_timer = None  # 状态更新定时器
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.config.stats_log_path), exist_ok=True)
        
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
        """检查空闲超时，关闭Chrome实例但不退出服务"""
        current_time = time.time()
        if current_time - self.last_activity_time > self.config.chrome_idle_timeout:
            if not self.active_tasks:
                logger.info(f"服务空闲超过 {self.config.chrome_idle_timeout} 秒，清理资源...")
                self._cleanup_chrome_processes()
                # 不退出服务，保持运行
                return False
        return False
        
    def _cleanup_chrome_processes(self):
        """清理所有Chrome进程"""
        try:
            import subprocess
            import os
            import signal
            
            # 查找所有Chrome进程
            logger.info("检查并清理所有Chrome进程...")
            
            # 使用ps命令查找Chrome相关进程
            ps_cmd = "ps aux | grep -E 'chrome|chromedriver' | grep -v grep"
            process = subprocess.Popen(ps_cmd, shell=True, stdout=subprocess.PIPE)
            output, _ = process.communicate()
            
            if output:
                lines = output.decode('utf-8').strip().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            pid = int(pid)
                            os.kill(pid, signal.SIGTERM)
                            logger.info(f"终止Chrome相关进程: PID {pid}")
                        except (ValueError, ProcessLookupError) as e:
                            logger.error(f"无法终止进程 {pid}: {str(e)}")
                logger.info("所有Chrome相关进程已清理")
            else:
                logger.info("没有发现运行中的Chrome进程")
                
        except Exception as e:
            logger.error(f"清理Chrome进程时出错: {str(e)}")
            # 即使出错也不影响主服务运行
    
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
        
        # 记录任务详情
        with self.active_tasks_lock:
            self.task_details[task_id] = {
                "url": url,
                "start_time": datetime.now().isoformat(),
                "status": "running",
                "scroll_count": 0
            }
        
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
            if task_id in self.task_details:
                del self.task_details[task_id]
                
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
    
    def _write_stats_to_log(self):
        """将当前状态写入日志文件"""
        try:
            current_time = datetime.now().isoformat()
            with self.active_tasks_lock:
                active_count = len(self.active_tasks)
                task_info = list(self.task_details.values())
            
            # 获取系统资源信息
            mem_info = self._get_memory_usage()
            cpu_info = self._get_cpu_usage()
            
            # 构建状态信息
            stats = {
                "timestamp": current_time,
                "active_tasks": active_count,
                "memory_usage_mb": mem_info,
                "cpu_usage_percent": cpu_info,
                "running_tasks": task_info
            }
            
            # 写入日志文件
            with open(self.config.stats_log_path, 'w') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
                
            logger.debug(f"已将状态信息写入: {self.config.stats_log_path}")
            
            # 设置下一次状态更新
            self.stats_timer = threading.Timer(self.config.stats_update_interval, self._write_stats_to_log)
            self.stats_timer.daemon = True
            self.stats_timer.start()
            
        except Exception as e:
            logger.error(f"写入状态日志时出错: {str(e)}")
            # 即使出错也要继续定时器
            self.stats_timer = threading.Timer(self.config.stats_update_interval, self._write_stats_to_log)
            self.stats_timer.daemon = True
            self.stats_timer.start()
    
    def _get_memory_usage(self):
        """获取当前内存使用情况"""
        try:
            # 使用ps命令获取内存使用情况
            cmd = "ps -o rss= -p %d" % os.getpid()
            output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
            memory_kb = int(output)
            memory_mb = memory_kb / 1024  # 转换为MB
            return round(memory_mb, 2)
        except Exception as e:
            logger.error(f"获取内存使用情况时出错: {str(e)}")
            return 0
    
    def _get_cpu_usage(self):
        """获取CPU使用率"""
        try:
            # 使用top命令获取CPU使用率
            cmd = f"top -b -n 1 -p {os.getpid()} | grep {os.getpid()}"
            output = subprocess.check_output(cmd, shell=True).decode('utf-8')
            cpu_usage = float(output.split()[8])
            return cpu_usage
        except Exception as e:
            logger.error(f"获取CPU使用率时出错: {str(e)}")
            return 0
    
    def run(self):
        """运行服务主循环，永久运行"""
        logger.info("无头Chrome服务启动...")
        
        # 启动时清理可能存在的Chrome进程
        self._cleanup_chrome_processes()
        
        # 启动状态统计定时器
        self._write_stats_to_log()
        
        while True:  # 永久运行，不使用self.running标志
            try:
                # 检查空闲超时，只清理资源不退出
                self._check_idle_timeout()
                
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
                
                # 即使出错也继续运行
        
        # 注意：这行代码实际上永远不会执行，因为我们使用了无限循环
        logger.info("服务主循环结束")

if __name__ == "__main__":
    service = HeadlessChromeService()
    service.run()
