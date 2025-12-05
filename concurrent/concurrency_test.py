
import os
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
import pdb
import threading
import signal

class ClarkConcurrencyTest(HttpUser):
    wait_time = between(1, 5)
    global_request_count = 0
    response_times = {}  # Track response times by user count
    request_counts = {}  # Track request counts by user count
    active_requests = 0  # Track active requests
    complexity_response_times = {}  # Track by complexity
    complexity_counts = {}  # Track counts by complexity
    shutdown_event = threading.Event()
    max_requests = 20
    stop_new_requests = False
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant_id = kwargs.get("tenant_id", None)
        self.category_id = kwargs.get("category_id", None)
        self.user_request_count = 0
        self.csv_file = "/home/amitc/stress/stress_test_request_details.csv"
        self.summary_csv_file = "/home/amitc/stress/stress_test_summary.csv"
        self.complexity_csv_file = "/home/amitc/stress/complexity_summary.csv"
        self.init_csv()
    #host = os.getenv("LOAD_BALANCER_URL", "LB-URL-NOT-SET")
    def init_csv(self):
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
                    existing_data[int(row['Number_of_Users'])] = row

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
            return random.choice(moderate_queries)
        else:
            return random.choice(simple_queries)
        
        
    @task(1)
    def chat(self):
        # Check if we should stop creating new requests
        if ClarkConcurrencyTest.global_request_count >= ClarkConcurrencyTest.max_requests:
            ClarkConcurrencyTest.stop_new_requests = True
            print(f"Reached max requests ({ClarkConcurrencyTest.max_requests}), stopping new requests")
            return
        if ClarkConcurrencyTest.stop_new_requests:
            print("Not creating new requests, waiting for existing ones to complete")
            return
        #pdb.set_trace()
        self.user_request_count += 1
        ClarkConcurrencyTest.active_requests += 1
        ClarkConcurrencyTest.global_request_count += 1
        print(f"Creating request {ClarkConcurrencyTest.global_request_count}")
        try:
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
            query_item = self.select_query_by_weight()
            selected_query=query_item["query"]
            query_complexity=query_item["complexity"]
            print(f"selected query : {selected_query} with {query_complexity} complexity.")

            request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"############# Global Request No: {ClarkConcurrencyTest.global_request_count} #########--START--######### Time:: {request_time} #########")
            #print(f"User Request count {self.user_request_count}")
            print(f"Inside /chat task for tenant: ")
            
            """
            eyJraWQiOiJtaTFKVWlVNml0RW1hbnNVV0Q2bG1ZUHhQb2hWRmtNNGU5enFvaFwvNHRJMD0iLCJhbGciOiJSUzI1NiJ9.eyJhdF9oYXNoIjoiTUwyNTRzQjJicGNsNzdfd3ZYcWkzUSIsInN1YiI6IjYxODM1ZDFhLWUwYzEtNzAyYy02NDM3LWRjNDhkY2QyM2E5NiIsImNvZ25pdG86Z3JvdXBzIjpbImFwLXNvdXRoLTFfNVdESGgxdVpIX1NERy1TU08iXSwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGgtMS5hbWF6b25hd3MuY29tXC9hcC1zb3V0aC0xXzVXREhoMXVaSCIsImNvZ25pdG86dXNlcm5hbWUiOiJzZGctc3NvX21ydmZ2aWdjMG8yOHZqbDZiYjFpYmhzd2RwZHpoM3luYzV4bDBxcTRyOWEiLCJub25jZSI6IlVNelB5REh0UndXVWplUVlzd2FQIiwib3JpZ2luX2p0aSI6IjkyOTNiOTQ3LWYwYWQtNGIwZS1hZjE3LWQ3OWJlMDljZmE5YSIsImF1ZCI6ImRxNzhudTlqa2o2aGdqNm04YWloM2lrZHAiLCJpZGVudGl0aWVzIjpbeyJkYXRlQ3JlYXRlZCI6IjE3NDc1Nzc2MjEyOTEiLCJ1c2VySWQiOiJtcnZmVmlnQzBPMjh2akw2YkIxaUJoU3dkcGR6aDNZTmM1eGwwcVE0cjlBIiwicHJvdmlkZXJOYW1lIjoiU0RHLVNTTyIsInByb3ZpZGVyVHlwZSI6Ik9JREMiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJ0cnVlIn1dLCJ0b2tlbl91c2UiOiJpZCIsImF1dGhfdGltZSI6MTc2NDgzMDc1MywiZXhwIjoxNzY0OTE3MTUzLCJpYXQiOjE3NjQ4MzA3NTMsImp0aSI6ImIyZTNhMWM3LTdlYWYtNDUyYS1iY2YzLTlhNzkwOTFmMTgzYSIsImVtYWlsIjoiYW1pdC5jaGFuZGVsYUBzZGdjLmNvbSJ9.USGUDsLFwHZ7_DKkX9WaRaPF5_kCu3CgT51Xk2PE8LfaLF1W3k06Uhk10HtDwmmGp5esWMEIe02evjPCCQO8IlAd00G2gfAhiYqhZDQ8MZ1RkNg8_y3wSzYdM5uA1ZmPB4jcOh3HZcSsIcBR6Y1J0oCuLuOQRSuamVmK87VVfHJro-Fti9pXFYBPCdsQIAhiF_2HwV7djK4MbK242wo49w6nFknWK7GJ-vuXsizM-Zw2o_3qPc7G1rULbehLeXGuZEhMibzpnIOyFxly1koNL9U9ZGPXR3jNStqQC3BNwsb-CIYL09ARPZdrft1g7-2HzDwxIzxr1v5bqMfg2Lf8Yg
            
            "query": "Show me the list of most polluted cities with highest AQI levels in the last 3 months",
            "query": "How to setup AWS CLI"
                    
            
            """
            my_session_cookie="eyJraWQiOiJtaTFKVWlVNml0RW1hbnNVV0Q2bG1ZUHhQb2hWRmtNNGU5enFvaFwvNHRJMD0iLCJhbGciOiJSUzI1NiJ9.eyJhdF9oYXNoIjoiUzkzaE1JWldtNzRxR3lvVl9vRHcyUSIsInN1YiI6IjYxODM1ZDFhLWUwYzEtNzAyYy02NDM3LWRjNDhkY2QyM2E5NiIsImNvZ25pdG86Z3JvdXBzIjpbImFwLXNvdXRoLTFfNVdESGgxdVpIX1NERy1TU08iXSwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuYXAtc291dGgtMS5hbWF6b25hd3MuY29tXC9hcC1zb3V0aC0xXzVXREhoMXVaSCIsImNvZ25pdG86dXNlcm5hbWUiOiJzZGctc3NvX21ydmZ2aWdjMG8yOHZqbDZiYjFpYmhzd2RwZHpoM3luYzV4bDBxcTRyOWEiLCJub25jZSI6Im5CQ3loYTBodG9ORmxQT0hSM3o3Iiwib3JpZ2luX2p0aSI6IjUxMzE2OWU5LTZiODAtNGNkZi05YmM1LWIwNzFlZmM0NzYyYiIsImF1ZCI6ImRxNzhudTlqa2o2aGdqNm04YWloM2lrZHAiLCJpZGVudGl0aWVzIjpbeyJkYXRlQ3JlYXRlZCI6IjE3NDc1Nzc2MjEyOTEiLCJ1c2VySWQiOiJtcnZmVmlnQzBPMjh2akw2YkIxaUJoU3dkcGR6aDNZTmM1eGwwcVE0cjlBIiwicHJvdmlkZXJOYW1lIjoiU0RHLVNTTyIsInByb3ZpZGVyVHlwZSI6Ik9JREMiLCJpc3N1ZXIiOm51bGwsInByaW1hcnkiOiJ0cnVlIn1dLCJ0b2tlbl91c2UiOiJpZCIsImF1dGhfdGltZSI6MTc2NDkyMDk2MiwiZXhwIjoxNzY1MDA3MzYyLCJpYXQiOjE3NjQ5MjA5NjIsImp0aSI6IjA4M2M1MjY5LTRkOGYtNDQxYi1hNDk3LWFkZDYzZTI5NDgzYiIsImVtYWlsIjoiYW1pdC5jaGFuZGVsYUBzZGdjLmNvbSJ9.kicioQPrCrcrI40_Hs7GoHIeY7qw1IKeePIf1jAo0mTzyETkIlEqriEYVt9sB2OLs9NcTM67ieL41syP8EtMxpPtddOZ8ydNF4Vk0iC8SCcT1vyYy-X3eEXX3M8DHrqer0LhWD1PeE9BlBq1L2b9Mh6Ds8aTjXHR6eXlHzmaijMAUDa35v761HcrQfjMJWMIetM_2eMTudEungpiOx5dRW5jkyhXji6JkUUQAeaPAPxWIyiOTiYdQy5VxfqP6Nw-Y1pQcqLyHegEa3e8Q8c3wBeIGALKBJaBl-Rd37cLGT-5TR6e9CPqv3CPZxGPzaqfujolLC2hhN0c3BHYYv0iIw"
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
            cookies = {"my_session_cookie": my_session_cookie}
            #self.client.post("/chat", json=payload, cookies=cookies)
            print(f"payload query:: {payload['query']}")
            print(f"payload thread_id:: {payload['configurables']}")
            start_time = time.time()
            print(f"")
            total_users = self.environment.runner.user_count if self.environment.runner else 0
            spawn_rate=self.get_spawn_rate()
            #spawn_rate = self.environment.runner.spawn_rate if self.environment.runner else 0
            #spawn_rate = getattr(self.environment.runner, 'spawn_rate', 0) if self.environment.runner else 0
            concurrent_users = ClarkConcurrencyTest.active_requests  # Use active requests count
            #total_users=10
            #spawn_rate=3
            #concurrent_users=3
            print(f"Total Users: {total_users}, Spawn Rate: {spawn_rate}, Concurrent Users: {concurrent_users}")
            with self.client.post("/chat", json=payload, cookies=cookies, stream=True, catch_response=True) as response:
                resp=""
                for chunk in response.iter_content(chunk_size=4096):
                    if chunk:
                        print(f"chunk returned for the user request no:: {self.user_request_count}")
                        print(chunk.decode('utf-8'))
                        resp += chunk.decode('utf-8')
            
        
            end_time = time.time()
            response_time=end_time - start_time
            print(f"Final response received : ::{resp}")
            print(f"Total response time: {response_time} seconds")

            ClarkConcurrencyTest.active_requests -= 1
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
                        request_time,
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        f"{response_time:.2f}",
                        concurrent_users,
                        f"{avg_response_time:.2f}",
                        response.status_code,
                        resp.replace('\n', ' ').replace('\r', '')  # Clean response for CSV
                    ])
                    file.flush()
                    print(f"Successfully wrote to CSV: {self.csv_file}")
            except Exception as e:
                print(f"Error writing to CSV: {e}")
        except Exception as e:
            print(f"Error in /chat task: {e}")
        finally:
            ClarkConcurrencyTest.active_requests -= 1
            print(f"Request completed. Active requests: {ClarkConcurrencyTest.active_requests}")
            
            # If this was the last active request and we've stopped creating new ones
            if ClarkConcurrencyTest.active_requests == 0 and ClarkConcurrencyTest.stop_new_requests:
                print("All requests completed. Stopping test.")
                self.environment.runner.quit()
        print(f"############# Global  Request No: {ClarkConcurrencyTest.global_request_count}, User Request No: {self.user_request_count} #########--FINISH--#########")
    

if __name__ == "__main__":
    import sys
    sys.argv = ['locust', '-f', 'concurrent/concurrency_test.py', '--host', 'http://localhost:5026']
    import locust.main
    locust.main.main()