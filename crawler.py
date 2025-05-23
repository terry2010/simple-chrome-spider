#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import signal
import sys
import time
import base64
import threading
import traceback
from datetime import datetime
from io import BytesIO
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import redis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/logs/crawler.log')
    ]
)
logger = logging.getLogger(__name__)

# 静态状态日志
STATS_LOG_PATH = '/logs/statics.log'

class Config:
    """配置类，从环境变量读取配置"""
    
    # Redis配置
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # 队列名称
    TASK_QUEUE = os.getenv('TASK_QUEUE', 'chrome_crawler_tasks')
    RESULT_QUEUE = os.getenv('RESULT_QUEUE', 'chrome_crawler_results')
    
    # 爬虫配置
    MAX_CONCURRENT_TASKS = int(os.getenv('MAX_CONCURRENT_TASKS', 5))
    DEFAULT_SCROLL_INTERVAL = int(os.getenv('DEFAULT_SCROLL_INTERVAL', 3))
    DEFAULT_VISIT_DURATION = int(os.getenv('DEFAULT_VISIT_DURATION', 60))
    BROWSER_TIMEOUT = int(os.getenv('BROWSER_TIMEOUT', 30))
    
    # 轮询间隔
    TASK_POLL_INTERVAL = int(os.getenv('TASK_POLL_INTERVAL', 5))
    
    # 日志配置
    STATS_UPDATE_INTERVAL = int(os.getenv('STATS_UPDATE_INTERVAL', 10))

class ChromeTask:
    """Chrome任务类，管理单个Chrome任务"""
    
    def __init__(self, task_data, redis_client):
        self.task_data = task_data
        self.redis_client = redis_client
        self.driver = None
        self.start_time = None
        self.end_time = None
        self.urls_visited = []
        self.current_url = None
        self.browser_logs = []
        self.screenshot = None
        self.page_source = None
        self.page_title = None
        self.console_logs = []
        self.success = False
        self.error = None
        self.custom_result = {}
        
    def start(self):
        """启动Chrome任务"""
        try:
            self.start_time = datetime.now()
            url = self.task_data.get('url')
            if not url:
                raise ValueError("任务中未提供URL")
                
            # 记录初始URL
            self.current_url = url
            self.urls_visited.append({
                'url': url,
                'time': self.start_time.isoformat()
            })
            
            # 启动浏览器
            logger.info(f"启动Chrome访问: {url}")
            self._setup_browser()
            
            # 访问URL
            self.driver.get(url)
            
            # 执行任务配置中的操作
            self._execute_task_actions()
            
            # 收集结果
            self._collect_results()
            
            self.success = True
            
        except Exception as e:
            self.error = str(e)
            logger.error(f"任务执行失败: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            self.end_time = datetime.now()
            self._quit_browser()
            self._save_results()
    
    def _setup_browser(self):
        """设置Chrome浏览器"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # 启用JavaScript和控制台日志记录
        options.add_argument('--enable-logging')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(Config.BROWSER_TIMEOUT)
        
        # 注入JavaScript以捕获控制台日志
        self.driver.execute_cdp_cmd('Runtime.enable', {})
        self.driver.execute_cdp_cmd('Console.enable', {})
        
    def _quit_browser(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {str(e)}")
            finally:
                self.driver = None
    
    def _execute_task_actions(self):
        """执行任务配置中的操作"""
        task_actions = self.task_data.get('task', [])
        
        if not task_actions:
            # 如果没有特定操作，则执行默认操作（滚动页面1分钟）
            self._default_scroll_behavior()
            return
        
        for action in task_actions:
            action_type = action.get('do')
            
            if action_type == 'page_down':
                self._scroll_page_down()
            elif action_type == 'sleep':
                sleep_time = action.get('time', Config.DEFAULT_SCROLL_INTERVAL)
                time.sleep(sleep_time)
            elif action_type == 'screenshot':
                self._take_screenshot()
            elif action_type == 'get_title':
                self.page_title = self.driver.title
            elif action_type == 'get_source':
                self.page_source = self.driver.page_source
            elif action_type == 'get_console_log':
                self._get_console_logs()
            else:
                logger.warning(f"未知的操作类型: {action_type}")
    
    def _default_scroll_behavior(self):
        """默认滚动行为：每3秒滚动一次，持续1分钟"""
        end_time = time.time() + Config.DEFAULT_VISIT_DURATION
        
        while time.time() < end_time:
            self._scroll_page_down()
            time.sleep(Config.DEFAULT_SCROLL_INTERVAL)
            
            # 检查URL是否变化
            if self.driver.current_url != self.current_url:
                self.current_url = self.driver.current_url
                self.urls_visited.append({
                    'url': self.current_url,
                    'time': datetime.now().isoformat()
                })
    
    def _scroll_page_down(self):
        """向下滚动一页"""
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
            logger.debug("页面向下滚动")
        except Exception as e:
            logger.error(f"页面滚动失败: {str(e)}")
    
    def _take_screenshot(self):
        """截取屏幕截图"""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            self.screenshot = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"截图失败: {str(e)}")
    
    def _get_console_logs(self):
        """获取控制台日志"""
        try:
            logs = self.driver.get_log('browser')
            self.console_logs.extend([log['message'] for log in logs])
        except Exception as e:
            logger.error(f"获取控制台日志失败: {str(e)}")
    
    def _collect_results(self):
        """收集任务结果"""
        callback_data = self.task_data.get('callback_data', [])
        
        # 确保始终收集默认数据
        if 'title' in callback_data or True:
            self.page_title = self.driver.title
            
        # 根据callback_data收集自定义结果
        if 'screenshot' in callback_data:
            if not self.screenshot:
                self._take_screenshot()
            self.custom_result['screenshot'] = self.screenshot
            
        if 'page_source' in callback_data or 'html' in callback_data:
            self.page_source = self.driver.page_source
            self.custom_result['page_source'] = self.page_source
            
        if 'console_log' in callback_data:
            if not self.console_logs:
                self._get_console_logs()
            self.custom_result['console_log'] = self.console_logs
    
    def _save_results(self):
        """保存任务结果"""
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        result = {
            'task_id': self.task_data.get('task_id', ''),
            'url': self.task_data.get('url', ''),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_duration': total_duration,
            'urls_visited': self.urls_visited,
            'final_url': self.current_url,
            'success': self.success,
            'error': self.error,
            'title': self.page_title,
        }
        
        # 添加自定义结果
        result.update(self.custom_result)
        
        # 发送回调（如果配置了）
        callback_url = self.task_data.get('callback_url')
        if callback_url:
            try:
                requests.post(callback_url, json=result, timeout=10)
                logger.info(f"已发送回调到: {callback_url}")
            except Exception as e:
                logger.error(f"发送回调失败: {str(e)}")
        
        # 将结果写入Redis队列
        try:
            self.redis_client.lpush(Config.RESULT_QUEUE, json.dumps(result))
            logger.info(f"已将结果写入队列: {Config.RESULT_QUEUE}")
        except Exception as e:
            logger.error(f"写入结果队列失败: {str(e)}")


class CrawlerManager:
    """爬虫管理器，管理所有Chrome任务"""
    
    def __init__(self):
        self.redis_client = None
        self.running_tasks = {}
        self.task_semaphore = threading.Semaphore(Config.MAX_CONCURRENT_TASKS)
        self.stop_event = threading.Event()
        self.stats_thread = None
        
    def connect_redis(self):
        """连接Redis"""
        try:
            logger.info(f"连接Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
            self.redis_client = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                password=Config.REDIS_PASSWORD,
                db=Config.REDIS_DB,
                decode_responses=True
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis连接成功")
            return True
        except Exception as e:
            logger.error(f"Redis连接失败: {str(e)}")
            return False
    
    def start(self):
        """启动爬虫管理器"""
        if not self.connect_redis():
            logger.error("无法连接Redis，退出")
            return False
        
        logger.info(f"爬虫管理器启动，最大并发任务数: {Config.MAX_CONCURRENT_TASKS}")
        
        # 启动状态更新线程
        self.stats_thread = threading.Thread(target=self._update_stats, daemon=True)
        self.stats_thread.start()
        
        # 注册信号处理
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        # 主循环
        while not self.stop_event.is_set():
            try:
                # 检查是否有任务
                if self.task_semaphore._value > 0:  # 还有可用的并发槽
                    task_json = self.redis_client.brpop(Config.TASK_QUEUE, Config.TASK_POLL_INTERVAL)
                    
                    if task_json:
                        _, task_data_str = task_json
                        self._process_task(task_data_str)
                else:
                    # 所有并发槽都在使用中，等待
                    time.sleep(1)
                    
                # 清理已完成的任务
                self._cleanup_finished_tasks()
                
            except Exception as e:
                logger.error(f"主循环发生错误: {str(e)}")
                logger.error(traceback.format_exc())
                time.sleep(Config.TASK_POLL_INTERVAL)
        
        # 关闭所有任务
        self._shutdown()
        return True
    
    def _process_task(self, task_data_str):
        """处理任务"""
        try:
            task_data = json.loads(task_data_str)
            task_id = task_data.get('task_id', str(time.time()))
            
            # 设置task_id如果没有
            if 'task_id' not in task_data:
                task_data['task_id'] = task_id
                
            logger.info(f"收到新任务: {task_id}, URL: {task_data.get('url')}")
            
            # 获取信号量
            self.task_semaphore.acquire()
            
            # 创建并启动任务线程
            task = ChromeTask(task_data, self.redis_client)
            task_thread = threading.Thread(
                target=self._run_task,
                args=(task_id, task),
                daemon=True
            )
            
            self.running_tasks[task_id] = {
                'thread': task_thread,
                'task': task,
                'start_time': datetime.now()
            }
            
            task_thread.start()
            logger.info(f"任务 {task_id} 已启动")
            
        except json.JSONDecodeError:
            logger.error(f"无效的任务数据格式: {task_data_str}")
        except Exception as e:
            logger.error(f"处理任务时出错: {str(e)}")
            logger.error(traceback.format_exc())
            self.task_semaphore.release()  # 释放信号量
    
    def _run_task(self, task_id, task):
        """运行任务的线程函数"""
        try:
            task.start()
        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            self.task_semaphore.release()  # 释放信号量
    
    def _cleanup_finished_tasks(self):
        """清理已完成的任务"""
        finished_tasks = []
        
        for task_id, task_info in self.running_tasks.items():
            if not task_info['thread'].is_alive():
                finished_tasks.append(task_id)
        
        for task_id in finished_tasks:
            logger.info(f"任务 {task_id} 已完成")
            self.running_tasks.pop(task_id, None)
    
    def _update_stats(self):
        """更新状态统计信息"""
        while not self.stop_event.is_set():
            try:
                stats = {
                    'timestamp': datetime.now().isoformat(),
                    'running_tasks': len(self.running_tasks),
                    'max_concurrent_tasks': Config.MAX_CONCURRENT_TASKS,
                    'available_slots': self.task_semaphore._value,
                    'tasks': []
                }
                
                # 添加正在运行的任务信息
                for task_id, task_info in self.running_tasks.items():
                    task = task_info['task']
                    start_time = task_info['start_time']
                    duration = (datetime.now() - start_time).total_seconds()
                    
                    stats['tasks'].append({
                        'task_id': task_id,
                        'url': task.task_data.get('url', ''),
                        'start_time': start_time.isoformat(),
                        'duration': duration
                    })
                
                # 写入状态日志
                with open(STATS_LOG_PATH, 'w') as f:
                    json.dump(stats, f, indent=2)
                    
                time.sleep(Config.STATS_UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"更新状态统计信息失败: {str(e)}")
                time.sleep(Config.STATS_UPDATE_INTERVAL)
    
    def _handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info(f"收到信号 {signum}，准备关闭")
        self.stop_event.set()
    
    def _shutdown(self):
        """关闭所有任务并清理资源"""
        logger.info("正在关闭爬虫管理器...")
        
        # 杀死所有Chrome进程
        self._kill_all_chrome_processes()
        
        # 等待所有任务线程结束
        for task_id, task_info in self.running_tasks.items():
            thread = task_info['thread']
            logger.info(f"等待任务 {task_id} 结束...")
            thread.join(timeout=5)
        
        logger.info("爬虫管理器已关闭")
    
    def _kill_all_chrome_processes(self):
        """杀死所有Chrome进程"""
        try:
            logger.info("关闭所有Chrome进程")
            os.system("pkill -f chrome")
            os.system("pkill -f chromium")
            os.system("pkill -f chromedriver")
        except Exception as e:
            logger.error(f"杀死Chrome进程失败: {str(e)}")


def main():
    """主函数"""
    try:
        # 确保日志目录存在
        os.makedirs('/logs', exist_ok=True)
        
        logger.info("启动无头Chrome爬虫服务")
        
        # 创建并启动爬虫管理器
        manager = CrawlerManager()
        manager.start()
        
    except Exception as e:
        logger.error(f"主程序异常: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
