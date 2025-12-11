import logging
import os

from dotenv import load_dotenv
load_dotenv()
class Task_Logger:
    def __init__(self, base_path=None):
        print(f"base_path (Parameter):: {base_path}")
        self.base_path = base_path or os.getenv('LOG_DIR', '/home/amitc/stress/logs')
        print(f"self.base_path:: {self.base_path}")
        
        os.makedirs(base_path, exist_ok=True)
        self.loggers = {}
    
    def get_logger(self, task_name, total_users=1, spawn_rate=1, max_requests=1):
        if task_name not in self.loggers:
            logger = logging.getLogger(f"task_{task_name}")
            logger.setLevel(logging.INFO)
            
            handler = logging.FileHandler(f"{self.base_path}/{task_name}_total_users_{total_users}_spawn_rate_{spawn_rate}_max_requests_{max_requests}.log")
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            logger.addHandler(handler)
            self.loggers[task_name] = logger
        
        return self.loggers[task_name]

# Add this to your ClarkConcurrencyTest class __init__ method:

