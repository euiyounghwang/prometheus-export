import os
import requests
import time
from prometheus_client import start_http_server, Enum, Histogram, Counter, Summary, Gauge, CollectorRegistry
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from prometheus_client.core import (
    GaugeMetricFamily,
    CounterMetricFamily,
    REGISTRY
)
import datetime
import json
import argparse
from threading import Thread
import logging
import socket
from config.log_config import create_log
import subprocess
import json
import copy

# logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

# Initialize & Inject with only one instance
logging = create_log()


hitl_server_health_status = Enum("hitl_server_health_status", "PSQL connection health", states=["healthy", "unhealthy"])
# kafka_broker_health_status = Enum("kafka_broker_health_status", "Kafka connection health", states=["green","yellow","red"])
hitl_server_health_request_time = Histogram('hitl_server_health_request_time', 'Server connection response time (seconds)')

kafka_brokers_gauge = Gauge("kafka_brokers", "the number of kafka brokers")

''' gauge with dict type'''
es_nodes_gauge_g = Gauge("es_node_metric", 'Metrics scraped from localhost', ["server_job"])
es_nodes_health_gauge_g = Gauge("es_health_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_nodes_gauge_g = Gauge("kafka_health_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_connect_nodes_gauge_g = Gauge("kafka_connect_nodes_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_connect_listeners_gauge_g = Gauge("kafka_connect_listeners_metric", 'Metrics scraped from localhost', ["server_job", "host", "name", "running"])
zookeeper_nodes_gauge_g = Gauge("zookeeper_health_metric", 'Metrics scraped from localhost', ["server_job"])
kibana_instance_gauge_g = Gauge("kibana_health_metric", 'Metrics scraped from localhost', ["server_job"])
logstash_instance_gauge_g = Gauge("logstash_health_metric", 'Metrics scraped from localhost', ["server_job"])
spark_jobs_gauge_g = Gauge("spark_jobs_running_metrics", 'Metrics scraped from localhost', ["server_job", "id", "cores", "memoryperslave", "submitdate", "duration", "activeapps"])


class ProcessHandler():
    ''' Get the process by the processname'''

    def __init__(self) -> None:
        pass

    def isProcessRunning(self, name):
        ''' Get PID with process name'''
        try:
            call = subprocess.check_output("pgrep -f '{}'".format(name), shell=True)
            logging.info("Process IDs - {}".format(call.decode("utf-8")))
            return True
        except subprocess.CalledProcessError:
            return False


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




def get_metrics_all_envs(monitoring_metrics):
    ''' get metrics from custom export for the health of kafka cluster'''
    
    def get_service_port_alive(monitoring_metrics):
        ''' get_service_port_alive'''
        ''' 
        socket.connect_ex( <address> ) similar to the connect() method but returns an error indicator of raising an exception for errors returned by C-level connect() call.
        Other errors like host not found can still raise exception though
        '''
        response_dict = {}
        for k, v in monitoring_metrics.items():
            response_dict.update({k : ""})
            response_sub_dict = {}
            url_lists = v.split(",")
            # logging.info("url_lists : {}".format(url_lists))
            totalcount = 0
            for each_host in url_lists:
                each_urls = each_host.split(":")
                # logging.info("urls with port : {}".format(each_urls))
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex((each_urls[0],int(each_urls[1])))
                if result == 0:
                    # print("Port is open")
                    totalcount +=1
                    response_sub_dict.update({each_urls[0] + ":" + each_urls[1] : "OK"})
                    response_sub_dict.update({"GREEN_CNT" : totalcount})
                else:
                    # print("Port is not open")
                    response_sub_dict.update({each_urls[0] + ":" + each_urls[1] : "FAIL"})
                    response_sub_dict.update({"GREEN_CNT" : totalcount})
                sock.close()
            response_dict.update({k : response_sub_dict})
            
        # logging.info(json.dumps(response_dict, indent=2))
        logging.info(response_dict)
        return response_dict


    def get_kafka_connector_listeners(node_list_str):
        ''' get the state of each node's listener'''
        ''' 1) http://localhost:8083/connectors/  -> ["test_api",..]'''
        ''' 
            2) http://localhost:8083/connectors/test_api/status 
            -> 
            "localhost" : [
                    {
                        "name": "test_api",
                        "connector": {
                            "state": "RUNNING",
                            "worker_id": "127.0.0.1:8083"
                        },
                        "tasks": [
                            {
                            "state": "RUNNING",
                            "id": 0,
                            "worker_id": "127.0.0.1:8083"
                            }
                        ]
                    }
              ]
        '''
        try:
            if not node_list_str:
                return None
            logging.info(f"get_kafka_connector_listeners - {node_list_str}")
            
            master_node = node_list_str.split(",")[0].split(":")[0]
            logging.info(f"get_kafka_connector_listeners #1- {master_node}")

            node_hosts = node_list_str.split(",")
            nodes_list = [node.split(":")[0] for node in node_hosts]
            
            active_listner_list = {}
            active_listner_connect = []
            
            for each_node in nodes_list:
                # -- make a call to master node to get the information of activeapps
                logging.info(each_node)
                resp = requests.get(url="http://{}:8083/connectors".format(each_node), timeout=5)
                    
                # logging.info(f"activeapps - {resp}, {resp.status_code}, {resp.json()}")
                logging.info(f"activeconnectors/listeners - {resp}, {resp.status_code}")
                if not (resp.status_code == 200):
                    continue
                else:
                #    active_listner_connect.update({each_node : resp.json()})
                    active_listner_connect = resp.json()
                    break
            logging.info(f"active_listner_list - {json.dumps(active_listner_connect, indent=2)}")
            
            '''
            # Master node
            # -- make a call to master node to get the information of activeapps
            resp = requests.get(url="http://{}:8083/connectors".format(master_node), timeout=5)
            if not (resp.status_code == 200):
                return None
            else:
                # logging.info("OK~@#")
                active_listner_connect.update({master_node : resp.json()})
            logging.info(f"active_listner_connect #1 - {json.dumps(active_listner_connect.get(master_node), indent=2)}")
            '''

            #-- with listeners_list
            listener_apis_dict = {}
            for node in nodes_list:
                listener_apis_dict.update({node : {}})
                listeners_list = []
                for listener in active_listner_connect:
                    try:
                        # logging.info(f"listener_apis_dict make a call - {node} -> {listener}")
                        resp_listener = requests.get(url="http://{}:8083/connectors/{}/status".format(node, listener), timeout=5)
                        # logging.info(f"listeners - {resp_listener}, {resp_listener.json()}")
                        listeners_list.append(resp_listener.json())
                    except Exception as e:
                        pass
                listener_apis_dict.update({node : listeners_list})

            # logging.info(f"listener_apis_dict - {json.dumps(listener_apis_dict, indent=2)}")
            logging.info(f"listener_apis_dict - {listener_apis_dict}")
            ''' result '''
            '''
            {
                "localhost1": [{
                    "test_jdbc": {
                    "name": "test_jdbc",
                    "connector": {
                        "state": "RUNNING",
                        "worker_id": "localhost:8083"
                    },
                    "tasks": [
                        {
                        "state": "RUNNING",
                        "id": 0,
                        "worker_id": "localhost:8083"
                        }
                    ]
                    }
                },
                "localhost2": {},
                "localhost3": {}
            }]

            '''
            return listener_apis_dict
            
        except Exception as e:
            logging.error(e)


    def get_spark_jobs(node):
        ''' get_spark_jobs '''
        ''' get_spark_jobs - localhost:9092,localhost:9092,localhost:9092 '''
        ''' first node of --kafka_url argument is a master node to get the number of jobs using http://localhost:8080/json '''
        try:
            if not node:
                return None
            logging.info(f"get_spark_jobs - {node}")
            master_node = node.split(",")[0].split(":")[0]
            logging.info(f"get_spark_jobs #1- {master_node}")

            # -- make a call to master node to get the information of activeapps
            resp = requests.get(url="http://{}:8080/json".format(master_node), timeout=5)
            
            if not (resp.status_code == 200):
                return None
            
            # logging.info(f"activeapps - {resp}, {resp.json()}")
            resp_working_job = resp.json().get("activeapps", "")
            # response_activeapps = []
            if resp_working_job:
                logging.info(f"activeapps - {resp_working_job}")
                return resp_working_job
            return None

        except Exception as e:
            logging.error(e)


    def get_Process_Id():
        ''' get_Process_Id'''
        process_name = "/logstash-"
        process_handler = ProcessHandler()
        logging.info("Prcess - {}".format(process_handler.isProcessRunning(process_name)))
        if process_handler.isProcessRunning(process_name):
            return 1
        return 0
    

    def get_elasticsearch_health(monitoring_metrics):
        ''' get cluster health '''
        ''' return health json if one of nodes in cluster is acitve'''
        try:
            es_url_hosts = monitoring_metrics.get("es_url", "")
            logging.info(f"get_elasticsearch_health hosts - {es_url_hosts}")
            es_url_hosts_list = es_url_hosts.split(",")
            
            for each_es_host in es_url_hosts_list:
                # -- make a call to node
                resp = requests.get(url="http://{}/_cluster/health".format(each_es_host), timeout=5)
                
                if not (resp.status_code == 200):
                    continue
                
                logging.info(f"activeES - {resp}, {resp.json()}")
                return resp.json()
                
            return None

        except Exception as e:
            logging.error(e)


    try:           
         #-- es node cluster health
        ''' http://localhost:9200/_cluster/health '''
        
        resp_es_health = get_elasticsearch_health(monitoring_metrics)
        if resp_es_health:
            ''' get es nodes from _cluster/health api'''
            es_nodes_gauge_g.labels(socket.gethostname()).set(int(resp_es_health['number_of_nodes']))
            if resp_es_health['status'] == 'green':
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(2)
            elif resp_es_health['status'] == 'yellow':
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(1)
            else:
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(0)
        else:
            es_nodes_health_gauge_g.labels(socket.gethostname()).set(0)
            es_nodes_gauge_g.labels(socket.gethostname()).set(0)
        #--

        ''' check nodes on all kibana/kafka/connect except es nodes by using socket '''
        monitoring_metrics_cp = copy.deepcopy(monitoring_metrics)
        del monitoring_metrics_cp["es_url"]
        logging.info("monitoring_metrics_cp - {}".format(json.dumps(monitoring_metrics_cp, indent=2)))
        response_dict = get_service_port_alive(monitoring_metrics_cp)

        kafka_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["kafka_url"]["GREEN_CNT"]))
        kafka_connect_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["kafka_connect_url"]["GREEN_CNT"]))
        zookeeper_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["zookeeper_url"]["GREEN_CNT"]))
        
        ''' get es nodes from _cluster/health api'''
        # es_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["es_url"]["GREEN_CNT"]))
        kibana_instance_gauge_g.labels(socket.gethostname()).set(int(response_dict["kibana_url"]["GREEN_CNT"]))

        # -- Get spark jobs
        response_spark_jobs = get_spark_jobs(monitoring_metrics.get("kafka_url", ""))

        spark_jobs_gauge_g._metrics.clear()
        if response_spark_jobs: 
            # spark_jobs_gauge_g
            for each_job in response_spark_jobs:
                duration = str(round(float(each_job["duration"])/(60.0*60.0*1000.0),2)) + " h"
                # logging.info(duration)
                for k, v in each_job.items():
                    if k  == 'state':
                        if v.upper() == 'RUNNING':
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), id=each_job["id"], cores=each_job['cores'], memoryperslave=each_job["memoryperslave"], submitdate=each_job["submitdate"], duration=duration, activeapps=each_job['name']).set(1)
                        else:
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), id=each_job["id"], cores=each_job['cores'], memoryperslave=each_job["memoryperslave"], submitdate=each_job["submitdate"], duration=duration, activeapps=each_job['name']).set(0)
                    
        
        # -- Get connect listeners
        '''
            {
                "localhost1": [
                  {
                    "name": "test_jdbc",
                    "connector": {
                        "state": "RUNNING",
                        "worker_id": "localhost:8083"
                    },
                    "tasks": [
                        {
                        "state": "RUNNING",
                        "id": 0,
                        "worker_id": "localhost:8083"
                        }
                    ]
                  }
                ],
                "localhost2": {},
                "localhost3": {}
            }
        '''
        response_listeners = get_kafka_connector_listeners(monitoring_metrics.get("kafka_url", ""))
        kafka_connect_listeners_gauge_g._metrics.clear()
        if response_listeners: 
            for host in response_listeners.keys():
                for element in response_listeners[host]:
                    if 'error_code' in element:
                        continue
                    else:
                        if element['tasks'][0]['state'].upper() == 'RUNNING':
                            kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element['name'], running=element['tasks'][0]['state']).set(1)
                        else:
                            kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element['name'], running=element['tasks'][0]['state']).set(0)

        # -- local instance based
        logstash_instance_gauge_g.labels(socket.gethostname()).set(int(get_Process_Id()))

    except Exception as e:
        logging.error(e)


def work(port, interval, monitoring_metrics):
    ''' Threading work'''
    '''
    # capture for HTTP URL for the status (example)
    cmd="curl -s lcoalhost/json/ "
    json=`$cmd | jq . > $test.json`
    activeApps=`jq .activeapps[]  $test.json `
    currentApp=`echo $activeApps  | jq 'select(.name=="tstaApp")' >  $test.json`
    currentAppStatus=`jq '.name  + " with Id " + .id + " is  " + .state' $test.json`
    echo $currentAppStatus

    # capture for the process (example)
    pid=`ps ax | grep -i 'logstash' | grep -v grep | awk '{print $1}'`
    if [ -n "$pid" ]
        then
        echo "logstash is Running as PID: $pid"
    else
        echo "logstash is not Running"
    fi
    '''
    try:
        start_http_server(int(port))
        print(f"Standalone Prometheus Exporter Server started..")

        while True:
            get_metrics_all_envs(monitoring_metrics)
            time.sleep(interval)

        '''
        for each_host in ['localhost', 'localhost']:
            while True:
                urls = urls.format(each_host)
                logging.info(urls)
                get_server_health(each_host)
                get_metrics_all_envs(each_host, urls)
                time.sleep(interval)
        '''

    except KeyboardInterrupt:
        logging.info("#Interrupted..")
    
    start_http_server(int(port))
    print(f"Prometheus Exporter Server started..")



if __name__ == '__main__':
    '''
    ./standalone-export-run.sh -> ./standalone-es-service-export.sh status/stop/start
    # first node of --kafka_url argument is a master node to get the number of jobs using http://localhost:8080/json
    python ./standalone-es-service-export
    python ./prometheus_client_export.py --host localhost --url "http://localhost:9999/health?kafka_url=localhost:29092,localhost:39092,localhost:49092&es_url=localhost:9200,localhost:9501,localhost:9503"
    '''
    parser = argparse.ArgumentParser(description="Script that might allow us to use it as an application of custom prometheus exporter")
    parser.add_argument('--kafka_url', dest='kafka_url', default="localhost:29092,localhost:39092,localhost:49092", help='Kafka hosts')
    parser.add_argument('--kafka_connect_url', dest='kafka_connect_url', default="localhost:8083,localhost:8084,localhost:8085", help='Kafka connect hosts')
    parser.add_argument('--zookeeper_url', dest='zookeeper_url', default="localhost:22181,localhost:21811,localhost:21812", help='zookeeper hosts')
    parser.add_argument('--es_url', dest='es_url', default="localhost:9200,localhost:9501,localhost:9503", help='es hosts')
    parser.add_argument('--kibana_url', dest='kibana_url', default="localhost:5601,localhost:15601", help='kibana hosts')
    parser.add_argument('--port', dest='port', default=9115, help='Expose Port')
    parser.add_argument('--interval', dest='interval', default=30, help='Interval')
    args = parser.parse_args()

    if args.kafka_url:
        kafka_url = args.kafka_url

    if args.kafka_connect_url:
        kafka_connect_url = args.kafka_connect_url

    if args.zookeeper_url:
        zookeeper_url = args.zookeeper_url

    if args.es_url:
        es_url = args.es_url

    if args.kibana_url:
        kibana_url = args.kibana_url

    if args.interval:
        interval = args.interval

    if args.port:
        port = args.port


    monitoring_metrics = {
        "kafka_url" : kafka_url,
        "kafka_connect_url" : kafka_connect_url,
        "zookeeper_url" : zookeeper_url,
        "es_url" : es_url,
        "kibana_url" : kibana_url
    }

    logging.info(json.dumps(monitoring_metrics, indent=2))
    logging.info(interval)

    work(int(port), int(interval), monitoring_metrics)
    '''
    T = []
    try:
        for host in ['localhost', 'localhost1']:
            th1 = Thread(target=work, args=(int(port), int(interval), monitoring_metrics))
            th1.daemon = True
            th1.start()
            T.append(th1)
            # th1.join()
        [t.join() for t in T] # wait for all threads to terminate
    except (KeyboardInterrupt, SystemExit):
        logging.info("#Interrupted..")
    '''
    
   