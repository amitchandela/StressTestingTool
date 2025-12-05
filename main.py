#from concurrent.concurrency_test import ClarkConcurrencyTest
from locust import Environment, stats

from concurrent.concurrency_test import ClarkConcurrencyTest


def concurrency_test():
    env = Environment(user_classes=[ClarkConcurrencyTest], host="http://localhost:8080", catch_responses=True)
    env.create_local_runner()
    env.runner.start(1, spawn_rate=1)  # 1 user, spawn rate 1/sec
    
   
    

if __name__ =="__main__":
    concurrency_test()