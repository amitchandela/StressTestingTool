import re
import glob
import os
import shutil
#from datetime import datetime
from dotenv import load_dotenv
from datetime import datetime as dt  # Use alias to avoid conflict
from logger import Task_Logger
# Set gevent support for debugging
os.environ['GEVENT_SUPPORT'] = 'True'
import time
import uuid
from locust import HttpUser, task, between
import random
import json
import datetime
import csv
import os
import shutil
import pdb
import threading
import signal
import logging
import requests
# Load environment variables
load_dotenv()
class ClarkConcurrencyTest(HttpUser):
    wait_time = between(0, 0.1)
    global_request_count = 0
    response_times = {}  # Track response times by user count
    request_counts = {}  # Track request counts by user count
    active_requests = 0  # Track active requests
    complexity_response_times = {}  # Track by complexity
    complexity_counts = {}  # Track counts by complexity
    shutdown_event = threading.Event()
    max_requests = int(os.getenv('MAX_ALLOWED_REQUESTS'))
    my_session_cookie_val=os.getenv('MY_SESSION_COOKIE')
    
    stop_new_requests = False
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # GEVENT_SUPPORT=True  locust -f concurrent/concurrency_test.py --host=http://10.41.10.56:5006 --users 20 --spawn-rate 20  --headless --loglevel DEBUG
        self.tenant_id = kwargs.get("tenant_id", None)
        self.category_id = kwargs.get("category_id", None)
        self.user_request_count = 0
        #self.csv_file = "/home/amitc/stress/stress_test_request_details.csv"
        #self.summary_csv_file = "/home/amitc/stress/stress_test_summary.csv"
        #self.complexity_csv_file = "/home/amitc/stress/complexity_summary.csv"
        self.csv_file = os.getenv('CSV_FILE')
        print(f"CSV PATH:: {self.csv_file}")
        self.summary_csv_file = os.getenv('SUMMARY_CSV_FILE')
        print(f"SUMMARY PATH:: {self.summary_csv_file}")
        self.complexity_csv_file = os.getenv('COMPLEXITY_CSV_FILE')
        print(f"COMPLEXITY PATH:: {self.complexity_csv_file}")
        total_users = self.environment.runner.user_count if self.environment.runner else 0
        spawn_rate=self.get_spawn_rate()
        max_usrs = self.max_requests
        # Create separate clients for different tasks
        self.chat_client = requests.Session()
        self.deep_chat_client = requests.Session()    
        # Set base URLs
        self.chat_host = os.getenv('CHAT_HOST', 'http://localhost:5006')
        self.deep_chat_host = os.getenv('DEEP_CHAT_HOST', 'http://localhost:5007')

        
        self.backup_existing_logs("chat",total_users,spawn_rate,max_usrs)
        self.backup_existing_logs("deep_chat",total_users,spawn_rate,max_usrs)
        
        
        self.task_logger = Task_Logger(os.getenv('LOG_DIR'))  
    
        self.init_csv()
    #host = os.getenv("LOAD_BALANCER_URL", "LB-URL-NOT-SET")

    def backup_csv_files(self):
        backup_dir = f"{os.getenv('LOG_DIR')}/backup"
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        
        csv_files = [
            (self.csv_file, "stress_test_request_details"),
            (self.summary_csv_file, "stress_test_summary"), 
            (self.complexity_csv_file, "complexity_summary")
        ]
        
        for csv_file, base_name in csv_files:
            if os.path.exists(csv_file):
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = f"{backup_dir}/{base_name}_{timestamp}.csv"
                shutil.move(csv_file, backup_file)
                print(f"Moved existing {base_name}.csv to {backup_file}")


    def init_csv(self):
        # Backup existing CSV files before creating new ones
        
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                #writer.writerow(['Total Users','spawn_rate','Global_Request_No', 'User_Request_No', 'Thread_ID', 'Query', 'Complexity','Start_Time', 'End_Time', 'Response_Time', 'Concurrent_Users', 'Avg_Response_Time','Status_Code'])
                writer.writerow(['Total Users','spawn_rate','Global_Request_No', 'Thread_ID', 'Query', 'Complexity','Start_Time', 'End_Time', 'Response_Time', 'Concurrent_Users', 'Avg_Response_Time','Status_Code','Final_Response'])

        if not os.path.exists(self.summary_csv_file):
            with open(self.summary_csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Number_of_Users', 'Spawn_Rate', 'Average_Response_Time'])
        
        if not os.path.exists(self.complexity_csv_file):
            with open(self.complexity_csv_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Complexity', 'Total_Requests', 'Average_Response_Time', 'Min_Response_Time', 'Max_Response_Time'])

    def update_complexity_summary(self, complexity, response_time):
        if complexity not in ClarkConcurrencyTest.complexity_response_times:
            ClarkConcurrencyTest.complexity_response_times[complexity] = []
            ClarkConcurrencyTest.complexity_counts[complexity] = 0
        
        ClarkConcurrencyTest.complexity_response_times[complexity].append(response_time)
        ClarkConcurrencyTest.complexity_counts[complexity] += 1
        
        # Update complexity summary CSV
        with open(self.complexity_csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Complexity', 'Total_Requests', 'Average_Response_Time', 'Min_Response_Time', 'Max_Response_Time'])
            
            for comp in ClarkConcurrencyTest.complexity_response_times:
                times = ClarkConcurrencyTest.complexity_response_times[comp]
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                count = ClarkConcurrencyTest.complexity_counts[comp]
                
                writer.writerow([comp, count, f"{avg_time:.2f}", f"{min_time:.2f}", f"{max_time:.2f}"])

    def update_summary_csv(self, total_users, spawn_rate, avg_response_time):
        # Read existing data to avoid duplicates
        existing_data = {}
        if os.path.exists(self.summary_csv_file):
            with open(self.summary_csv_file, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    existing_data[int(float(row['Number_of_Users']))] = row

        # Update or add new entry
        existing_data[total_users] = {
            'Number_of_Users': total_users,
            'Spawn_Rate': spawn_rate,
            'Average_Response_Time': f"{avg_response_time:.2f}"
        }

        # Write updated data
        with open(self.summary_csv_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Number_of_Users', 'Spawn_Rate', 'Average_Response_Time'])
            for user_count in sorted(existing_data.keys()):
                data = existing_data[user_count]
                writer.writerow([data['Number_of_Users'], data['Spawn_Rate'], data['Average_Response_Time']])
    def on_start(self):
        #self.tenant_id = ["SDGC", "Cytiva", "TnL"]
        #self.category_id = "58d432dde793f32048be7f2e07959507"
        print(f"Inside On Start...")
    
    def on_stop(self):
        """Called when the user is stopped"""
        print(f"User stopping, waiting for active requests to complete...")
        # Wait for this user's active requests to complete
        while ClarkConcurrencyTest.active_requests > 0:
            print(f"Waiting for {ClarkConcurrencyTest.active_requests} active requests to complete...")
            time.sleep(1)
        print("All requests completed for this user")
    
    @classmethod
    def wait_for_completion(cls):
        """Wait for all active requests to complete"""
        while cls.active_requests > 0:
            print(f"Waiting for {cls.active_requests} active requests to complete...")
            time.sleep(1)
        print("All requests completed")
    # Add signal handler to wait for completion on shutdown
    def signal_handler(signum, frame):
        print("Shutdown signal received, waiting for active requests to complete...")
        ClarkConcurrencyTest.wait_for_completion()
        exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    '''
    @task(5)
    def list_files(self):
        print(f"Inside list_files task for tenant: {self.tenant_id} and category: {self.category_id}")
        payload = {
            "tenants": self.tenant_id,
            "category_id": self.category_id
        }
        res=self.client.post("/listfiles", json=payload)
        print(f"Response: {res.text}")
    '''
    def get_spawn_rate(self):
        spawn_rate = 0
        if self.environment.runner:
            print(f"{self.environment.runner}")
            # Method 1: Check if spawn_rate exists in runner state
            if hasattr(self.environment.runner, 'spawn_rate'):
                print(f"spawn_rate attribute found")
                spawn_rate = self.environment.runner.spawn_rate
            # Method 2: Check runner state
            elif hasattr(self.environment.runner, 'state') and hasattr(self.environment.runner.state, 'spawn_rate'):
                print(f"state attribute found")
                spawn_rate = self.environment.runner.state.spawn_rate
            # Method 3: Check if it's in the runner's options
            elif hasattr(self.environment.runner, 'options') and hasattr(self.environment.runner.options, 'spawn_rate'):
                print(f"options attribute found")
                spawn_rate = self.environment.runner.options.spawn_rate
            # Method 4: Access from environment parsed options
            elif hasattr(self.environment, 'parsed_options') and hasattr(self.environment.parsed_options, 'spawn_rate'):
                print(f"parsed_options attribute found")
                spawn_rate = self.environment.parsed_options.spawn_rate

        print(f"returning spawn_rate :: {spawn_rate}")
        return spawn_rate
    
    def select_query_by_weight(self):
        simple_queries = [q for q in self.queries if q["complexity"] == "Simple"]
        moderate_queries = [q for q in self.queries if q["complexity"] == "Moderate"]
        
        # 70% moderate, 30% simple
        if random.random() > 0.5:
            if moderate_queries and len(moderate_queries)>0:
                print(f"Moderate query selected")
                return random.choice(moderate_queries)
            elif simple_queries and len(simple_queries)>0:
                return random.choice(simple_queries)
        else:
            if simple_queries and len(simple_queries)>0:
                print(f"Simple queries  selected")
                return random.choice(simple_queries)
            elif moderate_queries and len(moderate_queries)>0:
                return random.choice(moderate_queries)
    
    def backup_existing_logs(self,task_name,total_users,spawn_rate,max_req_allowed):

        log_dir = os.getenv('LOG_DIR')
        backup_dir = os.getenv('BACKUP_DIR')

        #chat_total_users_1_spawn_rate_5.0_max_requests_15
        #log_file = f"{log_dir}/{task_name}_total_users_{total_users}_spawn_rate_{spawn_rate}_max_requests_{max_req_allowed}.log"
        print(f"log_dir:: {log_dir}")
        print(f"backup_dir:: {backup_dir}")
        #print(f"log_file:: {log_file}")
        #self.backup_csv_files()
        # Find all .log files in LOG_DIR
        log_files = glob.glob(f"{log_dir}/*.log")
        if log_files:
            #backup_folder = f"{backup_dir}/{timestamp}_total_users_{total_users}_spawn_{spawn_rate}_maxusers_{max_usrs}"
            # Pattern to match the filename format
            pattern = r".*_total_users_(\d+)_spawn_rate_([\d.]+)_max_requests_(\d+)\.log"
            for log_file in log_files:
                last_log_file_complete_path=os.path.abspath(log_file)
                print(f"Complete Last Log file path is :: {last_log_file_complete_path}")
                last_log_filename = os.path.basename(log_file)
                print(f"last_log_filename:: {last_log_filename}")
                match = re.search(pattern, last_log_filename)
                last_log_total_users=-1
                last_log_spawn_rate=-1
                last_log_max_requests=-1
                if match:
                    last_log_total_users = int(match.group(1))
                    last_log_spawn_rate = float(match.group(2))
                    last_log_max_requests = int(match.group(3))
                    print(f"last total_users_{last_log_total_users}, Last spawn:: {last_log_spawn_rate}, Last maxusers:: {last_log_max_requests}")
                print(f"Checking if last_log_filename:: {last_log_filename} exists or not...")
                if os.path.exists(f"{log_dir}/{last_log_filename}"):
                    print(f"last_log_filename:: {log_dir}/{last_log_filename} exists")
                    os.makedirs(backup_dir, exist_ok=True)
                    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
                    backup_dir=f"{backup_dir}/{timestamp}_total_users_{last_log_total_users}_spawn_{last_log_spawn_rate}_maxusers_{last_log_max_requests}"
                    print(f"backup_dir:: {backup_dir}")
                    
                    backup_file = f"{backup_dir}/{task_name}_{timestamp}_total_users_{last_log_total_users}_spawn_{last_log_spawn_rate}_maxusers_{last_log_max_requests}.log"
                    
                    print(f"backup_file:: {backup_file}")
                    print(f"Copying {last_log_filename} to {backup_file}")
                    os.makedirs(backup_dir, exist_ok=True)
                    shutil.move(last_log_file_complete_path , backup_file)
                    print(f"File moved :: {last_log_file_complete_path}  to {backup_file}")
                    
                    #Now move the excel files
                    complexity_file = f"{os.getenv('STRESS_DIR')}/complexity_summary.csv"
                    print(f"complexity_file:: {complexity_file}")
                    summary_file = f"{os.getenv('STRESS_DIR')}/stress_test_summary.csv"
                    print(f"summary_file:: {summary_file}")
                    stress_test_request_details=f"{os.getenv('STRESS_DIR')}/stress_test_request_details.csv"
                    print(f"stress_test_request_details:: {stress_test_request_details}")

                    if os.path.exists(complexity_file):
                        print(f"Copying {complexity_file} to {backup_dir}/complexity_summary.csv")
                        os.makedirs(backup_dir, exist_ok=True)
                        shutil.move(complexity_file, f"{backup_dir}/complexity_summary.csv")
                        print(f"Moved {complexity_file} to {backup_dir}/complexity_summary.csv")
                    if os.path.exists(summary_file):
                        print(f"Copying {summary_file} to {backup_dir}/stress_test_summary.csv")
                        os.makedirs(backup_dir, exist_ok=True)
                        shutil.move(summary_file, f"{backup_dir}/stress_test_summary.csv")
                        print(f"Moved {summary_file} to {backup_dir}/stress_test_summary.csv")

                    #shutil.move(summary_file, f"{backup_dir}/stress_test_summary.csv")
                    if os.path.exists(stress_test_request_details):
                        print(f"Copying {stress_test_request_details} to {backup_dir}/stress_test_request_details.csv")
                        os.makedirs(backup_dir, exist_ok=True)
                        shutil.move(stress_test_request_details, f"{backup_dir}/stress_test_request_details.csv")
                        print(f"Moved {stress_test_request_details} to {backup_dir}/stress_test_request_details.csv")
                    #shutil.move(stress_test_request_details, f"{backup_dir}/stress_test_request_details.csv")
                    #
                else:
                    print(f"last_log_filename:: {log_dir}/{last_log_filename} does not exists")

    def display_counters(self, logger_obj, task_name):
        logger_obj.info(f"Global requests: {ClarkConcurrencyTest.global_request_count}, Max: {ClarkConcurrencyTest.max_requests}, Active: {ClarkConcurrencyTest.active_requests}")
        print(f"&&&&&&&&&&&&&&&&&&&&&&&& --- {task_name} Task ---Start  &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        logger_obj.info(f"&&&&&&&&&&&&&&&&&&&&&&&& --- {task_name} Task ---Start  &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        
        print(f"{task_name} method/{task_name} invoked. Here are the details of the counters::")
        logger_obj.info(f"{task_name} method/{task_name} invoked. Here are the details of the counters::")
        
        print(f"Value of ClarkConcurrencyTest.global_request_count :: {ClarkConcurrencyTest.global_request_count}")
        logger_obj.info(f"Value of ClarkConcurrencyTest.global_request_count :: {ClarkConcurrencyTest.global_request_count}")
        
        print(f"Value of ClarkConcurrencyTest.max_requests :: {ClarkConcurrencyTest.max_requests}")
        logger_obj.info(f"Value of ClarkConcurrencyTest.max_requests :: {ClarkConcurrencyTest.max_requests}")
        
        print(f"ClarkConcurrencyTest.active_requests :: {ClarkConcurrencyTest.active_requests}") 
        logger_obj.info(f"ClarkConcurrencyTest.active_requests :: {ClarkConcurrencyTest.active_requests}") 
        
        print(f"&&&&&&&&&&&&&&&&&&&&&&&&& --- {task_name} Task ---Counter details  &&&&&&&&&&&&&&&&&&&&&&&&&")
        logger_obj.info(f"&&&&&&&&&&&&&&&&&&&&&&&&& --- {task_name} Task ---Counter details  &&&&&&&&&&&&&&&&&&&&&&&&&")
            
    @classmethod
    def check_completion_and_exit(cls, environment, logger):
        if cls.global_request_count >= cls.max_requests and cls.active_requests == 0:
            print(f"Completed {cls.global_request_count}/{cls.max_requests} requests. Stopping test.")
            logger.info(f"Completed {cls.global_request_count}/{cls.max_requests} requests. Stopping test.")
            environment.runner.quit()  


    #@task(13)# probability will be (1.3/2)=0.65%
    @task(0)
    def chat(self):
        total_users = self.environment.runner.user_count if self.environment.runner else 0
        spawn_rate=self.get_spawn_rate()
            
        chat_logger = self.task_logger.get_logger("chat", total_users, spawn_rate, self.max_requests)
        task_name="chat"
    
        self.display_counters(chat_logger, task_name)
        """
        print(f"&&&&&&&&&&&&&&&&&&&&&&&& --- CHAT Task ---Start  &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        chat_logger.info("&&&&&&&&&&&&&&&&&&&&&&&& --- CHAT Task ---Start  &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        
        print(f"chat method/task invoked. Here are the details of the counters::")
        chat_logger.info(f"chat method/task invoked. Here are the details of the counters::")
        
        print(f"Value of ClarkConcurrencyTest.global_request_count :: {ClarkConcurrencyTest.global_request_count}")
        chat_logger.info(f"Value of ClarkConcurrencyTest.global_request_count :: {ClarkConcurrencyTest.global_request_count}")
        
        print(f"Value of ClarkConcurrencyTest.max_requests :: {ClarkConcurrencyTest.max_requests}")
        chat_logger.info(f"Value of ClarkConcurrencyTest.max_requests :: {ClarkConcurrencyTest.max_requests}")
        
        print(f"ClarkConcurrencyTest.active_requests :: {ClarkConcurrencyTest.active_requests}") 
        chat_logger.info(f"ClarkConcurrencyTest.active_requests :: {ClarkConcurrencyTest.active_requests}") 
        
        print(f"&&&&&&&&&&&&&&&&&&&&&&&&& --- CHAT Task ---Counter details  &&&&&&&&&&&&&&&&&&&&&&&&&")
        chat_logger.info(f"&&&&&&&&&&&&&&&&&&&&&&&&& --- CHAT Task ---Counter details  &&&&&&&&&&&&&&&&&&&&&&&&&")
        """

        # Check if we should stop creating new requests
        if ClarkConcurrencyTest.global_request_count >= ClarkConcurrencyTest.max_requests:
            ClarkConcurrencyTest.stop_new_requests = True
            print(f"Reached max requests ({ClarkConcurrencyTest.max_requests}), stopping new requests")
            print(f"Reached max requests ({ClarkConcurrencyTest.max_requests}), stopping new requests")
            #print(f"Sleeping for 30 seconds...")
            #time.sleep(30)
            
            return
        else:
            print(f"ClarkConcurrencyTest.global_request_count is not greater than ClarkConcurrencyTest.max_requests")
            chat_logger.info(f"{ClarkConcurrencyTest.global_request_count} < {ClarkConcurrencyTest.max_requests}")
            self.user_request_count += 1
            ClarkConcurrencyTest.active_requests += 1
            ClarkConcurrencyTest.global_request_count += 1
            ClarkConcurrencyTest.stop_new_requests = False

        
        if ClarkConcurrencyTest.stop_new_requests:
            print("Not creating new requests, waiting for existing ones to complete")
            chat_logger.info("Not creating new requests, waiting for existing ones to complete")
            return
        #pdb.set_trace()
        
        print(f"Step#1:: Now creating request #::  {ClarkConcurrencyTest.global_request_count}")
        chat_logger.info(f"Step#1:: Now creating request #::  {ClarkConcurrencyTest.global_request_count}")
        
        
        try:
            #"""
            self.queries = [
                {"query":"How to setup AWS CLI","complexity":"Moderate"},
                {"query":"What are the best practices for cloud security","complexity":"Moderate"},
                {"query":"Explain machine learning algorithms","complexity":"Moderate"},
                {"query":"How to optimize database performance","complexity":"Moderate"},
                {"query":"What is containerization and Docker","complexity":"Moderate"},
                {"query":"Guide to microservices architecture","complexity":"Moderate"},
                {"query":"How to implement CI/CD pipeline","complexity":"Moderate"},
                {"query":"What are the benefits of serverless computing","complexity":"Moderate"},
                {"query":"Explain REST API design principles","complexity":"Moderate"},
                {"query":"How to monitor application performance","complexity":"Moderate"},
                {"query":"Hi","complexity":"Simple"},
                {"query":"What is the time","complexity":"Simple"},
                {"query":"How are you","complexity":"Simple"},
                {"query":"How's the weather in Delhi","complexity":"Simple"}
                
            ]
            #"""
            """
            self.queries = [
                {"query":"Compare and analyze differences between Sailpoint ISC and ENTRA ID","complexity":"Moderate"},
                #{"query":"How's the weather in Delhi","complexity":"Simple"}
                
            ]
            """
            query_item = self.select_query_by_weight()
            selected_query=query_item["query"]
            query_complexity=query_item["complexity"]
            print(f"Step#2:: selected query : {selected_query} with {query_complexity} complexity.")
            chat_logger.info(f"Step#2:: selected query : {selected_query} with {query_complexity} complexity.")
            request_start_time = datetime.datetime.now()
            request_start_time_str=request_start_time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Step#3:: ############# Global Request No: {ClarkConcurrencyTest.global_request_count} #########--START--######### Request Start  Time:: {request_start_time} #########")
            chat_logger.info(f"Step#3:: ############# Global Request No: {ClarkConcurrencyTest.global_request_count} #########--START--######### Request Start  Time:: {request_start_time} #########")
            #print(f"User Request count {self.user_request_count}")
            print(f"Inside /chat task for tenant: ")
            chat_logger.info(f"Inside /chat task for tenant: ")
            
            #my_session_cookie="eyJraWQiOiJtaTFKVWlVNml0RW1hbnNVV0Q2bG1ZUHhQb2hWRmtNNGU5enFvaFwvNHRJMD0iLCJhbGciOiJSUzI1NiJ9.eyJhdF9oYXNoIjoiSVM5dDNTLWJ6cjJrbzI5a2xmdHlhdyIsInN1YiI6IjYxODM1ZDFhLWUwYzEtNzAyYy02NDM3LWRjNDhkY2QyM2E5NiIsImNvZ25pdG86Z3JvdXBzIjpbImFwLXNvdXRoLTFfNVdESGgxdVpIX1NERy1TU08iXSwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGgtMS5hbWF6b25hd3MuY29tXC9hcC1zb3V0aC0xXzVXREhoMXVaSCIsImNvZ25pdG86dXNlcm5hbWUiOiJzZGctc3NvX21ydmZ2aWdjMG8yOHZqbDZiYjFpYmhzd2RwZHpoM3luYzV4bDBxcTRyOWEiLCJub25jZSI6ImhXMkN1bDJSYVlKWnNOaDNsMndYIiwib3JpZ2luX2p0aSI6ImJiMTYyZDYxLWFiODItNGU3YS1hMzkxLTJiNmMzZDFlMzljMyIsImF1ZCI6ImRxNzhudTlqa2o2aGdqNm04YWloM2lrZHAiLCJpZGVudGl0aWVzIjpbeyJkYXRlQ3JlYXRlZCI6IjE3NDc1Nzc2MjEyOTEiLCJ1c2VySWQiOiJtcnZmVmlnQzBPMjh2akw2YkIxaUJoU3dkcGR6aDNZTmM1eGwwcVE0cjlBIiwicHJvdmlkZXJOYW1lIjoiU0RHLVNTTyIsInByb3ZpZGVyVHlwZSI6Ik9JREMiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJ0cnVlIn1dLCJ0b2tlbl91c2UiOiJpZCIsImF1dGhfdGltZSI6MTc2NTE3NTk1NiwiZXhwIjoxNzY1MjYyMzU2LCJpYXQiOjE3NjUxNzU5NTYsImp0aSI6Ijc1YmE5OWZhLWUzOWUtNDY0ZS1hYmExLTEyZjIyNGExODVlYyIsImVtYWlsIjoiYW1pdC5jaGFuZGVsYUBzZGdjLmNvbSJ9.U8d1AXTkX71q0vpwUpvIxS64DhqSILMlhcx2mr0yJHcNVLanCGUX2Dyuk9K-R_XWWLl0rAUHRXlkxxjlpBNM0GIiJBTVGeEzTv30VK_Y1Ce_0Q5JoXJ-y2Z6OoXYjQKOT9pOEo7qCgD8URcH6J7lqrIETOw0bbjp4xaObg-WE8LwdjjvMloA51Pshfzzt8L_zAhA3gdD_9lHlE41gGHQt-RvxDoM2FZNGjg58tDkYqHUT4MlEWz44fsPy43bMRuPZHaOL1hLW0xi2CJmV5QGrmYwh8OL6Ji0xns78gtxmgNVoWsF78VyfUmzC6m9CAps6zbS0e0KHtVHwnC9mWD8NQ"
            unique_thread_id = str(uuid.uuid4())
            payload = {
                    "query": selected_query,
                    "workflow_id": "SDG AI Companion",
                    "search_filter": [
                        "engagement"
                    ],
                    "configurables": {
                        "configurable": {
                        "thread_id": unique_thread_id,
                        "q_id": "d7769ff2-1a2a-41dd-b153-45e1f27043ae",
                        "file_path": "null",
                        "collection_name": "null",
                        "instance_id": "f2255271cf22fe1fb66738001a9732a8",
                        "answer_mode": "normal"
                        }
                    }
                }
            #cookies = {"my_session_cookie": my_session_cookie}
            cookies = {"my_session_cookie": self.my_session_cookie_val}
            
            #self.client.post("/chat", json=payload, cookies=cookies)
            print(f"Step#4:: payload query:: {payload['query']}")
            chat_logger.info(f"Step#4:: payload query:: {payload['query']}")
            print(f"Step#5:: payload thread_id:: {payload['configurables']}")
            chat_logger.info(f"Step#5:: payload thread_id:: {payload['configurables']}")
            #start_time = time.time()
           
            total_users = self.environment.runner.user_count if self.environment.runner else 0
            spawn_rate=self.get_spawn_rate()
            #spawn_rate = self.environment.runner.spawn_rate if self.environment.runner else 0
            #spawn_rate = getattr(self.environment.runner, 'spawn_rate', 0) if self.environment.runner else 0
            concurrent_users = ClarkConcurrencyTest.active_requests  # Use active requests count
            #total_users=10
            #spawn_rate=3
            #concurrent_users=3
            print(f"Step#6:: Total Users: {total_users}, Spawn Rate: {spawn_rate}, Concurrent active Requests: {concurrent_users}")
            chat_logger.info(f"Step#6:: Total Users: {total_users}, Spawn Rate: {spawn_rate}, Concurrent active Requests: {concurrent_users}")
             # Use chat_client with chat_host
            url_endpoint = f"{self.chat_host}/chat"
            chat_logger.info(f"Step#6.1:: URL endpoint for chat:: {url_endpoint}")
            with self.client.post(url_endpoint, json=payload, cookies=cookies, stream=True, catch_response=True) as response:
                resp=""
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        print(f"chunk returned for the user request no:: {self.user_request_count}")
                        chat_logger.info(f"chunk returned for the user request no:: {self.user_request_count}")
                        print(chunk.decode('utf-8'))
                        chat_logger.info(chunk.decode('utf-8'))
                        resp += chunk.decode('utf-8')
            
        
            #end_time = time.time()
            request_end_time =datetime.datetime.now()
            request_end_time_str = request_end_time.strftime("%Y-%m-%d %H:%M:%S")
            response_time=(request_end_time - request_start_time).total_seconds()
            print(f"Step#7:: Final response received : ::{resp}")
            chat_logger.info(f"Step#7:: Final response received : ::{resp}")
            print(f"Global Request No: {ClarkConcurrencyTest.global_request_count},  Request Start  Time:: {request_start_time} ")
            chat_logger.info(f"Global Request No: {ClarkConcurrencyTest.global_request_count}, Request Start  Time:: {request_start_time} ")
            print(f"Global Request No: {ClarkConcurrencyTest.global_request_count},  Request End Time:: {request_end_time} ")
            chat_logger.info(f"Global Request No: {ClarkConcurrencyTest.global_request_count},  Request End Time:: {request_end_time} ")

            print(f"Total response time: {response_time} seconds")
            chat_logger.info(f"Total response time: {response_time} seconds")

            #ClarkConcurrencyTest.active_requests -= 1
            if total_users not in ClarkConcurrencyTest.response_times:
                ClarkConcurrencyTest.response_times[total_users] = []
                ClarkConcurrencyTest.request_counts[total_users] = 0
            ClarkConcurrencyTest.response_times[total_users].append(response_time)
            ClarkConcurrencyTest.request_counts[total_users] += 1

            # Calculate average response time for current user count
            avg_response_time = sum(ClarkConcurrencyTest.response_times[total_users]) / len(ClarkConcurrencyTest.response_times[total_users])
            # Update summary CSV
            self.update_summary_csv(total_users, spawn_rate, avg_response_time) 
            self.update_complexity_summary(query_complexity, response_time)
            # Write to CSV
            try:
                with open(self.csv_file, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([
                        total_users,
                        spawn_rate,
                        ClarkConcurrencyTest.global_request_count,
                        #self.user_request_count,
                        unique_thread_id,
                        payload['query'],
                        query_complexity,
                        request_start_time_str,
                        request_end_time_str,
                        response_time,
                        concurrent_users,
                        avg_response_time,
                        response.status_code,
                        resp.replace('\n', ' ').replace('\r', '')  # Clean response for CSV
                    ])
                    file.flush()
                    print(f"Successfully wrote to CSV: {self.csv_file}")
                    chat_logger.info(f"Successfully wrote to CSV: {self.csv_file}")
            except Exception as e:
                print(f"Error writing to CSV: {e}")
                chat_logger.error(f"Error writing to CSV: {e}")
        except Exception as e:
            print(f"Error in /chat task: {e}")
            chat_logger.error(f"Error in /chat task: {e}")
        finally:
            ClarkConcurrencyTest.active_requests -= 1
            print(f"Request completed. Active requests: {ClarkConcurrencyTest.active_requests}")
            chat_logger.info(f"Request completed. Active requests: {ClarkConcurrencyTest.active_requests}")
            
            # If this was the last active request and we've stopped creating new ones
            if ClarkConcurrencyTest.active_requests == 0 and ClarkConcurrencyTest.stop_new_requests:
                print("All requests completed. Stopping test.")
                chat_logger.info("All requests completed. Stopping test.")
                self.environment.runner.quit()
        print(f"############# Global  Request No: {ClarkConcurrencyTest.global_request_count}, User Request No: {self.user_request_count} #########--FINISH--#########")
        chat_logger.info(f"############# Global  Request No: {ClarkConcurrencyTest.global_request_count}, User Request No: {self.user_request_count} #########--FINISH--#########")
    
    @task(2) # probability will be (0.7/2)=0.35%
    def deep_chat(self):
        total_users = self.environment.runner.user_count if self.environment.runner else 0
        spawn_rate=self.get_spawn_rate()
        deep_chat_logger = self.task_logger.get_logger("deep_chat",total_users, spawn_rate, self.max_requests)
        task_name="deep_chat"
        self.display_counters(deep_chat_logger, task_name)
        """
        print(f"&&&&&&&&&&&&&&&&&&&&&&&& --- DEEP_CHAT Task ---Start  &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        print(f"DEEP_CHAT method/task invoked. Here are the details of the counters::")
        
        print(f"Value of ClarkConcurrencyTest.global_request_count :: {ClarkConcurrencyTest.global_request_count}")
        print(f"Value of ClarkConcurrencyTest.max_requests :: {ClarkConcurrencyTest.max_requests}")
        print(f"ClarkConcurrencyTest.active_requests :: {ClarkConcurrencyTest.active_requests}") 
        print(f"&&&&&&&&&&&&&&&&&&&&&&&&& --- DEEP_CHAT Task ---Counter details  &&&&&&&&&&&&&&&&&&&&&&&&&")
        """

        # Check if we should stop creating new requests
        if ClarkConcurrencyTest.global_request_count >= ClarkConcurrencyTest.max_requests:
            ClarkConcurrencyTest.stop_new_requests = True
            print(f"Reached max requests ({ClarkConcurrencyTest.max_requests}), stopping new requests")
            deep_chat_logger.info(f"Reached max requests ({ClarkConcurrencyTest.max_requests}), stopping new requests")
            #print(f"Sleeping for 30 seconds...")
            #time.sleep(30)
            
            return
        else:
            print(f"ClarkConcurrencyTest.global_request_count is not greater than ClarkConcurrencyTest.max_requests")
            deep_chat_logger.info(f"ClarkConcurrencyTest.global_request_count is not greater than ClarkConcurrencyTest.max_requests")
            print(f"{ClarkConcurrencyTest.global_request_count} < {ClarkConcurrencyTest.max_requests}")
            deep_chat_logger.info(f"{ClarkConcurrencyTest.global_request_count} < {ClarkConcurrencyTest.max_requests}")
            self.user_request_count += 1
            ClarkConcurrencyTest.active_requests += 1
            ClarkConcurrencyTest.global_request_count += 1
            ClarkConcurrencyTest.stop_new_requests = False

        
        if ClarkConcurrencyTest.stop_new_requests:
            print("Not creating new requests, waiting for existing ones to complete")
            deep_chat_logger.info("Not creating new requests, waiting for existing ones to complete")
            return
        #pdb.set_trace()
        
        print(f"Step#1:: Now creating request #::  {ClarkConcurrencyTest.global_request_count}")
        deep_chat_logger.info(f"Step#1:: Now creating request #::  {ClarkConcurrencyTest.global_request_count}")
        
        
        try:
            #"""
            self.queries = [
                {"query":"Show me the details of AQI in Delhi India as on today, The goal is to analyze the current AQI and the target audience is the ministers of Delhi government. Do not ask any further questions and just generate the report.","complexity":"Moderate"},
                {"query":"What are the best practices for cloud security, The goal is to know what are the industry best practices and the target audience is technical workforce such as software developers and DevOps team. Do not ask any further questions and just generate the report. Assume that all the section provided by you are correct. Please go ahead and generate and download the report.","complexity":"Moderate"},
                {"query":"Compare and analyze differences between Sailpoint ISC and ENTRA ID. The goal is to know what are the major differences between these and the target audience is technical workforce such as software developers and DevOps team. Do not ask any further questions and just generate the report. Assume that all the section provided by you are correct. Please go ahead and generate and download the report","complexity":"Moderate"},
                
            ]
            #"""
            """
            self.queries = [
                {"query":"Compare and analyze differences between Sailpoint ISC and ENTRA ID","complexity":"Moderate"},
                #{"query":"How's the weather in Delhi","complexity":"Simple"}
                
            ]
            """
            query_item = self.select_query_by_weight()
            selected_query=query_item["query"]
            query_complexity=query_item["complexity"]
            print(f"Step#2:: selected query : {selected_query} with {query_complexity} complexity.")
            deep_chat_logger.info(f"Step#2:: selected query : {selected_query} with {query_complexity} complexity.")
            request_start_time = datetime.datetime.now()
            request_start_time_str=request_start_time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Step#3:: ############# Global Request No: {ClarkConcurrencyTest.global_request_count} #########--START--######### Request Start  Time:: {request_start_time} #########")
            deep_chat_logger.info(f"Step#3:: ############# Global Request No: {ClarkConcurrencyTest.global_request_count} #########--START--######### Request Start  Time:: {request_start_time} #########")
            #print(f"User Request count {self.user_request_count}")
            print(f"Inside /chat task for tenant: ")
            deep_chat_logger.info(f"Inside /chat task for tenant: ")
            
            my_session_cookie="eyJraWQiOiJtaTFKVWlVNml0RW1hbnNVV0Q2bG1ZUHhQb2hWRmtNNGU5enFvaFwvNHRJMD0iLCJhbGciOiJSUzI1NiJ9.eyJhdF9oYXNoIjoiSVM5dDNTLWJ6cjJrbzI5a2xmdHlhdyIsInN1YiI6IjYxODM1ZDFhLWUwYzEtNzAyYy02NDM3LWRjNDhkY2QyM2E5NiIsImNvZ25pdG86Z3JvdXBzIjpbImFwLXNvdXRoLTFfNVdESGgxdVpIX1NERy1TU08iXSwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGgtMS5hbWF6b25hd3MuY29tXC9hcC1zb3V0aC0xXzVXREhoMXVaSCIsImNvZ25pdG86dXNlcm5hbWUiOiJzZGctc3NvX21ydmZ2aWdjMG8yOHZqbDZiYjFpYmhzd2RwZHpoM3luYzV4bDBxcTRyOWEiLCJub25jZSI6ImhXMkN1bDJSYVlKWnNOaDNsMndYIiwib3JpZ2luX2p0aSI6ImJiMTYyZDYxLWFiODItNGU3YS1hMzkxLTJiNmMzZDFlMzljMyIsImF1ZCI6ImRxNzhudTlqa2o2aGdqNm04YWloM2lrZHAiLCJpZGVudGl0aWVzIjpbeyJkYXRlQ3JlYXRlZCI6IjE3NDc1Nzc2MjEyOTEiLCJ1c2VySWQiOiJtcnZmVmlnQzBPMjh2akw2YkIxaUJoU3dkcGR6aDNZTmM1eGwwcVE0cjlBIiwicHJvdmlkZXJOYW1lIjoiU0RHLVNTTyIsInByb3ZpZGVyVHlwZSI6Ik9JREMiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJ0cnVlIn1dLCJ0b2tlbl91c2UiOiJpZCIsImF1dGhfdGltZSI6MTc2NTE3NTk1NiwiZXhwIjoxNzY1MjYyMzU2LCJpYXQiOjE3NjUxNzU5NTYsImp0aSI6Ijc1YmE5OWZhLWUzOWUtNDY0ZS1hYmExLTEyZjIyNGExODVlYyIsImVtYWlsIjoiYW1pdC5jaGFuZGVsYUBzZGdjLmNvbSJ9.U8d1AXTkX71q0vpwUpvIxS64DhqSILMlhcx2mr0yJHcNVLanCGUX2Dyuk9K-R_XWWLl0rAUHRXlkxxjlpBNM0GIiJBTVGeEzTv30VK_Y1Ce_0Q5JoXJ-y2Z6OoXYjQKOT9pOEo7qCgD8URcH6J7lqrIETOw0bbjp4xaObg-WE8LwdjjvMloA51Pshfzzt8L_zAhA3gdD_9lHlE41gGHQt-RvxDoM2FZNGjg58tDkYqHUT4MlEWz44fsPy43bMRuPZHaOL1hLW0xi2CJmV5QGrmYwh8OL6Ji0xns78gtxmgNVoWsF78VyfUmzC6m9CAps6zbS0e0KHtVHwnC9mWD8NQ"
            unique_thread_id = str(uuid.uuid4())
            payload = {
                    "query": selected_query,
                    "workflow_id": "SDG AI Companion",
                    "search_filter": [
                        "engagement"
                    ],
                    "configurables": {
                        "configurable": {
                        "thread_id": unique_thread_id,
                        "q_id": "d7769ff2-1a2a-41dd-b153-45e1f27043ae",
                        "file_path": "null",
                        "collection_name": "null",
                        "instance_id": "f2255271cf22fe1fb66738001a9732a8",
                        "answer_mode": "normal"
                        }
                    }
                }
            #cookies = {"my_session_cookie": my_session_cookie}
            cookies = {"my_session_cookie": self.my_session_cookie_val}
            #self.client.post("/chat", json=payload, cookies=cookies)
            print(f"Step#4:: payload query:: {payload['query']}")
            deep_chat_logger.info(f"Step#4:: payload query:: {payload['query']}")

            
            print(f"Step#5:: payload thread_id:: {payload['configurables']}")
            deep_chat_logger.info(f"Step#5:: payload thread_id:: {payload['configurables']}")
            #start_time = time.time()
           
            total_users = self.environment.runner.user_count if self.environment.runner else 0
            spawn_rate=self.get_spawn_rate()
            #spawn_rate = self.environment.runner.spawn_rate if self.environment.runner else 0
            #spawn_rate = getattr(self.environment.runner, 'spawn_rate', 0) if self.environment.runner else 0
            concurrent_users = ClarkConcurrencyTest.active_requests  # Use active requests count
            #total_users=10
            #spawn_rate=3
            #concurrent_users=3
            print(f"Step#6:: Total Users: {total_users}, Spawn Rate: {spawn_rate}, Concurrent active Requests: {concurrent_users}")
            deep_chat_logger.info(f"Step#6:: Total Users: {total_users}, Spawn Rate: {spawn_rate}, Concurrent active Requests: {concurrent_users}")
            url_endpoint = f"{self.deep_chat_host}/chat"
            with self.client.post(url_endpoint, json=payload, cookies=cookies, stream=True, catch_response=True) as response:
                resp=""
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        print(f"chunk returned for the user request no:: {self.user_request_count}")
                        deep_chat_logger.info(f"chunk returned for the user request no:: {self.user_request_count}")
                        print(chunk.decode('utf-8'))
                        deep_chat_logger.info(chunk.decode('utf-8'))
                        resp += chunk.decode('utf-8')
            
        
            #end_time = time.time()
            request_end_time =datetime.datetime.now()
            request_end_time_str = request_end_time.strftime("%Y-%m-%d %H:%M:%S")
            response_time=(request_end_time - request_start_time).total_seconds()
            print(f"Step#7:: Final response received : ::{resp}")
            deep_chat_logger.info(f"Step#7:: Final response received : ::{resp}")
            print(f"Global Request No: {ClarkConcurrencyTest.global_request_count},  Request Start  Time:: {request_start_time} ")
            deep_chat_logger.info(f"Global Request No: {ClarkConcurrencyTest.global_request_count}, Request Start  Time:: {request_start_time} ")
            print(f"Global Request No: {ClarkConcurrencyTest.global_request_count},  Request End Time:: {request_end_time} ")
            deep_chat_logger.info(f"Global Request No: {ClarkConcurrencyTest.global_request_count}, Request End Time:: {request_end_time} ")
            print(f"Total response time: {response_time} seconds")
            deep_chat_logger.info(f"Total response time: {response_time} seconds")

            #ClarkConcurrencyTest.active_requests -= 1
            if total_users not in ClarkConcurrencyTest.response_times:
                ClarkConcurrencyTest.response_times[total_users] = []
                ClarkConcurrencyTest.request_counts[total_users] = 0
            ClarkConcurrencyTest.response_times[total_users].append(response_time)
            ClarkConcurrencyTest.request_counts[total_users] += 1

            # Calculate average response time for current user count
            avg_response_time = sum(ClarkConcurrencyTest.response_times[total_users]) / len(ClarkConcurrencyTest.response_times[total_users])
            # Update summary CSV
            self.update_summary_csv(total_users, spawn_rate, avg_response_time) 
            self.update_complexity_summary(query_complexity, response_time)
            # Write to CSV
            try:
                with open(self.csv_file, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([
                        total_users,
                        spawn_rate,
                        ClarkConcurrencyTest.global_request_count,
                        #self.user_request_count,
                        unique_thread_id,
                        payload['query'],
                        query_complexity,
                        request_start_time_str,
                        request_end_time_str,
                        response_time,
                        concurrent_users,
                        avg_response_time,
                        response.status_code,
                        resp.replace('\n', ' ').replace('\r', '')  # Clean response for CSV
                    ])
                    file.flush()
                    print(f"Successfully wrote to CSV: {self.csv_file}")
                    deep_chat_logger.info(f"Successfully wrote to CSV: {self.csv_file}")
            except Exception as e:
                print(f"Error writing to CSV: {e}")
                deep_chat_logger.error(f"Error writing to CSV: {e}")
        except Exception as e:
            print(f"Error in /chat task: {e}")
            deep_chat_logger.error(f"Error in /chat task: {e}")
        finally:
            ClarkConcurrencyTest.active_requests -= 1
            print(f"Request completed. Active requests: {ClarkConcurrencyTest.active_requests}")
            deep_chat_logger.info(f"Request completed. Active requests: {ClarkConcurrencyTest.active_requests}")
            
            # If this was the last active request and we've stopped creating new ones
            if ClarkConcurrencyTest.active_requests == 0 and ClarkConcurrencyTest.stop_new_requests:
                print("All requests completed. Stopping test.")
                deep_chat_logger.info("All requests completed. Stopping test.")
                
                self.environment.runner.quit()
        print(f"############# Global  Request No: {ClarkConcurrencyTest.global_request_count}, User Request No: {self.user_request_count} #########--FINISH--#########")
        deep_chat_logger.info(f"############# Global  Request No: {ClarkConcurrencyTest.global_request_count}, User Request No: {self.user_request_count} #########--FINISH--#########")
  


if __name__ == "__main__":
    import sys
    sys.argv = ['locust', '-f', 'concurrent/concurrency_test.py', '--host', 'http://localhost:5026']
    import locust.main
    locust.main.main()