import os
import requests
import time
from prometheus_client import start_http_server, Enum, Histogram, Counter, Summary, Gauge
import datetime
import json

hitl_psql_health_status = Enum("hitl_psql_health_status", "PSQL connection health", states=["healthy", "unhealthy"])
# kafka_broker_health_status = Enum("kafka_broker_health_status", "Kafka connection health", states=["3","2","1"])
kafka_brokers = Gauge("kafka_brokers", "the number of kafka brokers")
hitl_psql_health_request_time = Histogram('hitl_psql_health_request_time', 'PSQL connection response time (seconds)')


def transform_prometheus_txt_to_Json(response):
    ''' transform_prometheus_txt_to_Json '''
    body_list = [body for body in response.text.split("\n") if not "#" in body and len(body)>0]
    
    prometheus_json = {}
    loop = 0
    for x in body_list:
        json_key_pairs = x.split(" ")
        prometheus_json.update({json_key_pairs[0] : json_key_pairs[1]})
            
    # print(json.dumps(prometheus_json, indent=2))

    return prometheus_json


def get_prometheus_endpoint():
    ''' polling from existing prometheus client'''
    PROMETHEUS = 'http://localhost:9308/'

    end_of_month = datetime.datetime.today().replace(day=1).date()

    last_day = end_of_month - datetime.timedelta(days=1)
    duration = '[' + str(last_day.day) + 'd]'

    response = requests.get(PROMETHEUS + '/metrics',
    #   params={
    #     'query': 'sum by (job)(increase(process_cpu_seconds_total' + duration + '))',
    #     'time': time.mktime(end_of_month.timetuple())}
        )
    
    response = transform_prometheus_txt_to_Json(response)
    # print('kafka_brokers - ', response['kafka_brokers'])

    # kafka_brokers.state(response['kafka_brokers'])
    kafka_brokers.set(int(response['kafka_brokers']))
   

def get_metrics():

    with hitl_psql_health_request_time.time():
        resp = requests.get(url="http://localhost:9308/metrics")
    
    # print(resp.status_code)
            
    if not (resp.status_code == 200):
        hitl_psql_health_status.state("unhealthy")
            
if __name__ == '__main__':
    print(f"Server started..")
    start_http_server(9115)
    while True:
        get_metrics()
        get_prometheus_endpoint()
        time.sleep(1)