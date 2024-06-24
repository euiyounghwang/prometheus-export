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
import datetime, time
import json
import argparse
from threading import Thread
import logging
import socket
from config.log_config import create_log
import subprocess
import json
import copy
import jaydebeapi
import jpype
import re
from collections import defaultdict


# logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

# Initialize & Inject with only one instance
logging = create_log()


hitl_server_health_status = Enum("hitl_server_health_status", "PSQL connection health", states=["healthy", "unhealthy"])
# kafka_broker_health_status = Enum("kafka_broker_health_status", "Kafka connection health", states=["green","yellow","red"])
hitl_server_health_request_time = Histogram('hitl_server_health_request_time', 'Server connection response time (seconds)')

kafka_brokers_gauge = Gauge("kafka_brokers", "the number of kafka brokers")

''' export application performance metric'''
es_service_jobs_performance_gauge_g = Gauge("es_service_jobs_performance_running_metrics", 'Metrics scraped from localhost', ["server_job"])

''' gauge with dict type'''
''' type : cluster/data_pipeline'''
all_envs_status_gauge_g = Gauge("all_envs_status_metric", 'Metrics scraped from localhost', ["server_job", "type"])
es_nodes_gauge_g = Gauge("es_node_metric", 'Metrics scraped from localhost', ["server_job"])
es_nodes_health_gauge_g = Gauge("es_health_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_nodes_gauge_g = Gauge("kafka_health_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_connect_nodes_gauge_g = Gauge("kafka_connect_nodes_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_connect_listeners_gauge_g = Gauge("kafka_connect_listeners_metric", 'Metrics scraped from localhost', ["server_job", "host", "name", "running"])
kafka_connect_health_gauge_g = Gauge("kafka_connect_health_metric", 'Metrics scraped from localhost', ["server_job"])
kafka_isr_list_gauge_g = Gauge("kafka_isr_list_metric", 'Metrics scraped from localhost', ["server_job", "topic", "partition", "leader", "replicas", "isr"])
zookeeper_nodes_gauge_g = Gauge("zookeeper_health_metric", 'Metrics scraped from localhost', ["server_job"])
spark_nodes_gauge_g = Gauge("spark_health_metric", 'Metrics scraped from localhost', ["server_job"])
kibana_instance_gauge_g = Gauge("kibana_health_metric", 'Metrics scraped from localhost', ["server_job"])
logstash_instance_gauge_g = Gauge("logstash_health_metric", 'Metrics scraped from localhost', ["server_job"])
spark_jobs_gauge_g = Gauge("spark_jobs_running_metrics", 'Metrics scraped from localhost', ["server_job", "id", "cores", "memoryperslave", "submitdate", "duration", "activeapps"])
db_jobs_gauge_g = Gauge("db_jobs_running_metrics", 'Metrics scraped from localhost', ["server_job", "processname", "cnt", "status", "addts", "dbid"])
db_jobs_performance_gauge_g = Gauge("db_jobs_performance_running_metrics", 'Metrics scraped from localhost', ["server_job"])

''' export failure instance list metric'''
es_service_jobs_failure_gauge_g = Gauge("es_service_jobs_failure_running_metrics", 'Metrics scraped from localhost', ["server_job", "host", "reason"])



class oracle_database:

    def __init__(self, db_url) -> None:
        self.db_url = db_url
        self.set_db_connection()
        

    def set_init_JVM(self):
        '''
        Init JPYPE StartJVM
        '''

        if jpype.isJVMStarted():
            return
        
        jar = r'./ojdbc8.jar'
        args = '-Djava.class.path=%s' % jar

        # print('Python Version : ', sys.version)
        # print('JAVA_HOME : ', os.environ["JAVA_HOME"])
        # print('JDBC_Driver Path : ', JDBC_Driver)
        # print('Jpype Default JVM Path : ', jpype.getDefaultJVMPath())

        # jpype.startJVM("-Djava.class.path={}".format(JDBC_Driver))
        jpype.startJVM(jpype.getDefaultJVMPath(), args, '-Xrs')


    def set_init_JVM_shutdown(self):
        jpype.shutdownJVM() 
   

    def set_db_connection(self):
        ''' DB Connect '''
        print('connect-str : ', self.db_url)
        
        StartTime = datetime.datetime.now()

        # -- Init JVM
        self.set_init_JVM()
        # --
        
        # - DB Connection
        self.db_conn = jaydebeapi.connect("oracle.jdbc.driver.OracleDriver", self.db_url)
        # --
        EndTime = datetime.datetime.now()
        Delay_Time = str((EndTime - StartTime).seconds) + '.' + str((EndTime - StartTime).microseconds).zfill(6)[:2]
        print("# DB Connection Running Time - {}".format(str(Delay_Time)))

    
    def set_db_disconnection(self):
        ''' DB Disconnect '''
        self.db_conn.close()
        print("Disconnected to Oracle database successfully!") 

    
    def get_db_connection(self):
        return self.db_conn
    

    def excute_oracle_query(self, sql):
        '''
        DB Oracle : Excute Query
        '''
        print('excute_oracle_query -> ', sql)
        # Creating a cursor object
        cursor = self.get_db_connection().cursor()

        # Executing a query
        cursor.execute(sql)
        
        # Fetching the results
        results = cursor.fetchall()
        cols = list(zip(*cursor.description))[0]
        # print(type(results), cols)

        json_rows_list = []
        for row in results:
            # print(type(row), row)
            json_rows_dict = {}
            for i, row in enumerate(list(row)):
                json_rows_dict.update({cols[i] : row})
            json_rows_list.append(json_rows_dict)

        cursor.close()

        # logging.info(json_rows_list)
        
        return json_rows_list
    


class ProcessHandler():
    ''' Get the process by the processname'''

    def __init__(self) -> None:
        pass

    ''' get ProcessID'''
    def isProcessRunning(self, name):
        ''' Get PID with process name'''
        try:
            call = subprocess.check_output("pgrep -f '{}'".format(name), shell=True)
            logging.info("Process IDs - {}".format(call.decode("utf-8")))
            return True
        except subprocess.CalledProcessError:
            return False
        
    
    ''' get command result'''
    def get_run_cmd_Running(self, cmd):
        ''' Get PID with process name'''
        try:
            logging.info("get_run_cmd_Running - {}".format(cmd))
            call = subprocess.check_output("{}".format(cmd), shell=True)
            output = call.decode("utf-8")
            # logging.info("CMD - {}".format(output))
            # logging.info(output.split("\n"))
            
            output = [element for element in output.split("\n") if len(element) > 0]

            return output
        except subprocess.CalledProcessError:
            return None   


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




''' save failure nodes into dict'''
saved_failure_dict = {}

def get_metrics_all_envs(monitoring_metrics):
    ''' get metrics from custom export for the health of kafka cluster'''
    
    global saved_failure_dict

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
            for idx, each_host in enumerate(url_lists):
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
                    ''' save failure node with a reason into saved_failure_dict'''
                    saved_failure_dict.update({each_urls[0] : "[Node #{}-{}] ".format(idx+1, k) + each_host + " Port closed"})
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
                try:
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
                except Exception as e:
                    pass

            logging.info(f"active_listener_list - {json.dumps(active_listner_connect, indent=2)}")

            ''' add tracking logs and save failure node with a reason into saved_failure_dict'''
            if not active_listner_connect:
                saved_failure_dict.update({",".join(nodes_list): "http://{}:8083/connectors API do not reachable".format(nodes_list)})
                return None
            
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
                loop = 1
                for listener in active_listner_connect:
                    try:
                        """
                        resp_each_listener = requests.get(url="http://{}:8083/connectors/{}".format(node, listener), timeout=5)
                        # logging.info(f"len(resp_each_listener['tasks']) - {node} -> { len(list(resp_each_listener.json()['tasks']))}")
                        ''' If the “task” details are missing from the listener, then we probably are not processing data.'''
                        if len(list(resp_each_listener.json()["tasks"])) > 0:
                            # logging.info(f"listener_apis_dict make a call - {node} -> {listener}")
                            resp_listener = requests.get(url="http://{}:8083/connectors/{}/status".format(node, listener), timeout=5)
                            # logging.info(f"listeners - {resp_listener}, {resp_listener.json()}")
                            listeners_list.append(resp_listener.json())
                        else:
                            ''' save failure node with a reason into saved_failure_dict'''
                            saved_failure_dict.update({"{}_{}".format(node, str(loop)) : "http://{}:8083/connectors/{} tasks are missing".format(node, listener)})
                        """
                        resp_listener = requests.get(url="http://{}:8083/connectors/{}/status".format(node, listener), timeout=5)
                        listeners_list.append(resp_listener.json())
                        
                        loop +=1
                    except Exception as e:
                        ''' save failure node with a reason into saved_failure_dict'''
                        saved_failure_dict.update({"{}_{}".format(node, str(loop))  : "http://{}:8083/connectors/{}/status API do not reachable".format(node, listener)})
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

            ''' clear spark nodes health'''
            spark_nodes_gauge_g.clear()

            if not node:
                return None
            logging.info(f"get_spark_jobs - {node}")
            master_node = node.split(",")[0].split(":")[0]
            logging.info(f"get_spark_jobs #1- {master_node}")

            # -- make a call to master node to get the information of activeapps
            resp = requests.get(url="http://{}:8080/json".format(master_node), timeout=5)
            logging.info(f"get_spark_jobs - response {resp.status_code}")
            
            if not (resp.status_code == 200):
                return None
            
            ''' expose metrics spark node health is active'''
            spark_nodes_gauge_g.labels(server_job=socket.gethostname()).set(1)

            # logging.info(f"activeapps - {resp}, {resp.json()}")
            resp_working_job = resp.json().get("activeapps", "")
            # response_activeapps = []
            if resp_working_job:
                logging.info(f"activeapps - {resp_working_job}")
                return resp_working_job
            return None

        except Exception as e:
            ''' add tracking logs and save failure node with a reason into saved_failure_dict'''
            saved_failure_dict.update({node : "spark cluster - http://{}:8080/json API do not reachable".format(master_node)})
            spark_nodes_gauge_g.labels(server_job=socket.gethostname()).set(0)
            logging.error(e)


    def get_Process_Id():
        ''' get_Process_Id'''
        process_name = "/logstash-"
        process_handler = ProcessHandler()
        logging.info("Prcess - {}".format(process_handler.isProcessRunning(process_name)))
        if process_handler.isProcessRunning(process_name):
            return 1
        
        ''' save failure node with a reason into saved_failure_dict'''
        saved_failure_dict.update({socket.gethostname() : "Logstash didn't run"})
        return 0
    

    def get_elasticsearch_health(monitoring_metrics):
        ''' get cluster health '''
        ''' return health json if one of nodes in cluster is acitve'''
        try:
            es_url_hosts = monitoring_metrics.get("es_url", "")
            logging.info(f"get_elasticsearch_health hosts - {es_url_hosts}")
            es_url_hosts_list = es_url_hosts.split(",")
            
            for each_es_host in es_url_hosts_list:

                try:
                    # -- make a call to node
                    resp = requests.get(url="http://{}/_cluster/health".format(each_es_host), timeout=5)
                    
                    if not (resp.status_code == 200):
                        ''' save failure node with a reason into saved_failure_dict'''
                        # saved_failure_dict.update({each_es_host.split(":")[0] : each_es_host + " Port closed"})
                        continue
                    
                    logging.info(f"activeES - {resp}, {resp.json()}")
                    ''' log if one of ES nodes goes down'''
                    if int(resp.json().get("unassigned_shards")) > 0:
                        saved_failure_dict.update({socket.gethostname() : "[elasticsearch exception] The number of unassiged shards : {}".format(resp.json().get("unassigned_shards"))})
                    return resp.json()
                
                except Exception as e:
                    pass
                
            return None

        except Exception as e:
            logging.error(e)


    def get_elasticsearch_audit_alert(monitoring_metrics):
        ''' get nodes health/check the some metrics for delivering audit alert via email '''
        ''' https://www.elastic.co/guide/en/elasticsearch/reference/current/cat-nodes.html'''

        def get_float_number(s):
            ''' get float/numbder from string'''
            p = re.compile("\d*\.?\d+")
            return float(''.join(p.findall(s)))

        try:
            es_url_hosts = monitoring_metrics.get("es_url", "")
            logging.info(f"get_elasticsearch_audit_alert hosts - {es_url_hosts}")
            es_url_hosts_list = es_url_hosts.split(",")
            
            for each_es_host in es_url_hosts_list:
                try:
                    # -- make a call to cluster for checking the disk space on all nodes in the cluster
                    resp = requests.get(url="http://{}/_cat/nodes?format=json&h=name,ip,h,diskAvail".format(each_es_host), timeout=5)
                    
                    if not (resp.status_code == 200):
                        ''' save failure node with a reason into saved_failure_dict'''
                        # saved_failure_dict.update({each_es_host.split(":")[0] : each_es_host + " Port closed"})
                        continue
                    
                    logging.info(f"get_elasticsearch_audit_alert - {resp}, {resp.json()}")

                    for element_dict in resp.json():
                        for k, v in element_dict.items():
                            if k == "diskAvail":
                                if get_float_number(v) < int(os.environ["ES_NODES_DISK_AVAILABLE_THRESHOLD"]):
                                    ''' save failure node with a reason into saved_failure_dict'''
                                    saved_failure_dict.update({each_es_host.split(":")[0] : "[{}]".format(element_dict.get("name","")) + " Disk availed : " + element_dict.get("diskAvail","")})
                                    return True
                    return False
                    
                except Exception as e:
                    pass
            
        except Exception as e:
            logging.error(e)


    def get_kafka_ISR_lists():
        ''' get kafka ISR lists'''
        process_handler = ProcessHandler()
        GET_KAFKA_ISR_LIST = os.environ["GET_KAFKA_ISR_LIST"]

        # kafka_topic_isr = '/home/biadmin/monitoring/custom_export/kafka_2.11-0.11.0.0/bin/kafka-topics.sh --describe --zookeeper  {} --topic ELASTIC_PIPELINE_QUEUE'.format(ZOOKEEPER_URLS)
        response = process_handler.get_run_cmd_Running(GET_KAFKA_ISR_LIST)

        # logging.info(f"Kafka ISR : {response}")
        ''' ['Topic:ELASTIC_PIPELINE_QUEUE\tPartitionCount:16\tReplicationFactor:3\tConfigs:', '\ '''

        kafk_offsets_dict = defaultdict()
        for idx in range(1, len(response)):
            each_isr = [element for element in response[idx].split("\t") if len(element) > 0]
            logging.info(each_isr)
            kafk_offsets_dict.update({"{}_{}".format(each_isr[0],str(idx-1)) : each_isr})

        logging.info(f"get_kafka_ISR_lists - {json.dumps(kafk_offsets_dict, indent=2)}")

        return kafk_offsets_dict


    def get_kafka_ISR_metrics():
        ''' get Kafka Offset_ISR by using Kafka Job Interface API or Local Kafka cluster (It required to have a kafak folder to run the command)'''
        try:
            """
            ''' Kafka ISR command result using local kafak cluster installed'''
            saved_kafka_isr_lists_dict = get_kafka_ISR_lists()
            '''
                "Topic: ELASTIC_PIPELINE_QUEUE_12": [
                    "Topic: ELASTIC_PIPELINE_QUEUE",
                    "Partition: 11",
                    "Leader: 2",
                    "Replicas: 2,1,3",
                    "Isr: 1,2"
                ],

            '''
            """
            # -- make a call to node
            ZOOKEEPER_URLS = os.environ["ZOOKEEPER_URLS"]
            KAFKA_JOB_INTERFACE_API = os.environ["KAFKA_JOB_INTERFACE_API"]
            ''' request to Kafak Job interface api'''
            resp = requests.get(url="http://{}/kafka/get_kafka_isr_list?broker_list={}".format(KAFKA_JOB_INTERFACE_API, ZOOKEEPER_URLS), timeout=5)
                    
            if not (resp.status_code == 200):
                return None
                    
            logging.info(f"get_kafka_ISR_metrics from Kafka Job Interface API - {resp}, {resp.json()}")
            saved_kafka_isr_lists_dict = resp.json()["results"]
                
            ''' If saved_kafka_isr_lists_dict is not None '''
            ''' Sometimes we have an NoneType Object from the function called when Kafka cluster went down during the security patching'''
            if saved_kafka_isr_lists_dict:
                kafka_isr_dict = {}
                for k, v in saved_kafka_isr_lists_dict.items():
                    key = k.split(":")[1].lower().strip()
                    kafka_isr_dict.update({key:{element.split(":")[0] : element.split(":")[1].strip() for element in v}})
                    
                    
                    kafka_isr_list_gauge_g._metrics.clear()  
                    logging.info(f"temp_kafka_isr_dict = {kafka_isr_dict}")  
                    for k, v in kafka_isr_dict.items():
                        logging.info(f"# k - {k}, # v - {v}")
                        kafka_isr_list_gauge_g.labels(server_job=socket.gethostname(), topic=v.get("Topic",""), partition=v.get("Partition",""), leader=v.get("Leader",""), replicas=v.get("Replicas",""), isr=v.get("Isr","")).set(1)
            

        except Exception as e:
            logging.error(e)

    def get_all_envs_status(all_env_status, value, types=None):
        ''' return all_envs_status status'''
        logging.info('type : {}, get_all_envs_status"s value - {} -> merged list : {}'.format(types, value, all_env_status))
        try:
            if types == 'kafka':
                if value == 3:
                    ''' green'''
                    all_env_status.append(1)
                elif value > 0 and value <3:
                    ''' yellow'''
                    all_env_status.append(0)
                else:
                    ''' red'''
                    all_env_status.append(-1)
            # elif types == 'logstash' :
            #     if value == 1:
            #        ''' green'''
            #        all_env_status.append(1)
            #     else:
            #        ''' red'''
            #        all_env_status.append(-1)
            else:
                if value == 1:
                   ''' green'''
                   all_env_status.append(1)
                else:
                   ''' red'''
                   all_env_status.append(-1)
            # else:
            #     if value == 1:
            #         ''' green'''
            #         all_env_status.append(1)
            #     elif value == 0:
            #         ''' yellow'''
            #         all_env_status.append(0)
            #     else:
            #         ''' red'''
            #         all_env_status.append(-1)
            
            return all_env_status

        except Exception as e:
            logging.error(e)

    try: 
        ''' all_envs_status : 0 -> red, 1 -> yellow, 2 --> green '''
        all_env_status_memory_list = []

        ''' clear logs'''
        saved_failure_dict.clear()

        #-- es node cluster health
        ''' http://localhost:9200/_cluster/health '''
        
        ''' The cluster health API returns a simple status on the health of the cluster. '''
        ''' get the health of the cluseter and set value based on status/get the number of nodes in the cluster'''
        ''' The operation receives cluster health results from only one active node among several nodes. '''
        resp_es_health = get_elasticsearch_health(monitoring_metrics)
        if resp_es_health:
            ''' get es nodes from _cluster/health api'''
            es_nodes_gauge_g.labels(socket.gethostname()).set(int(resp_es_health['number_of_nodes']))
            if resp_es_health['status'] == 'green':
                all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list,1)
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(2)
            elif resp_es_health['status'] == 'yellow':
                all_env_status_memory_list == get_all_envs_status(all_env_status_memory_list,0)
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(1)
            else:
                all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1)
                es_nodes_health_gauge_g.labels(socket.gethostname()).set(0)
        else:
            es_nodes_health_gauge_g.labels(socket.gethostname()).set(0)
            es_nodes_gauge_g.labels(socket.gethostname()).set(0)
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1)
        #--

        ''' Check the number of metrics for audit alert'''
        is_audit_alert_es = get_elasticsearch_audit_alert(monitoring_metrics)
        if is_audit_alert_es:
            all_env_status_memory_list == get_all_envs_status(all_env_status_memory_list,0)

        ''' check the status of nodes on all kibana/kafka/connect except es nodes by using socket '''
        ''' The es cluster is excluded because it has already been checked in get_elasticsearch_health function'''
        monitoring_metrics_cp = copy.deepcopy(monitoring_metrics)
        # del monitoring_metrics_cp["es_url"]
        logging.info("monitoring_metrics_cp - {}".format(json.dumps(monitoring_metrics_cp, indent=2)))

        ''' socket.connect_ex( <address> ) similar to the connect() method but returns an error indicator of raising an exception for errors '''
        ''' The error indicator is 0 if the operation succeeded, otherwise the value of the errno variable. '''
        ''' Kafka/Kafka connect/Spark/Kibana'''
        response_dict = get_service_port_alive(monitoring_metrics_cp)

        ''' Kafka Health'''
        kafka_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["kafka_url"]["GREEN_CNT"]))
        kafka_connect_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["kafka_connect_url"]["GREEN_CNT"]))
        zookeeper_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["zookeeper_url"]["GREEN_CNT"]))
        
        ''' Update the status of kibana instance by using socket.connect_ex'''
        # es_nodes_gauge_g.labels(socket.gethostname()).set(int(response_dict["es_url"]["GREEN_CNT"]))
        kibana_instance_gauge_g.labels(socket.gethostname()).set(int(response_dict["kibana_url"]["GREEN_CNT"]))

       
        ''' first node of --kafka_url argument is a master node to get the number of jobs using http://localhost:8080/json '''
        ''' To receive spark job lists, JSON results are returned from master node 8080 port. ''' 
        ''' From the results, we get the list of spark jobs in activeapps key and transform them to metrics for exposure. '''
        # -- Get spark jobs
        response_spark_jobs = get_spark_jobs(monitoring_metrics.get("kafka_url", ""))

        spark_jobs_gauge_g._metrics.clear()
        if response_spark_jobs: 
            ''' list of spark jobs shows'''
            # spark_jobs_gauge_g
            for each_job in response_spark_jobs:
                duration = str(round(float(each_job["duration"])/(60.0*60.0*1000.0),2)) + " h" if 'duration' in each_job else -1
                # logging.info(duration)
                for k, v in each_job.items():
                    if k  == 'state':
                        if v.upper() == 'RUNNING':
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), id=each_job.get('id',''), cores=each_job.get('cores',''), memoryperslave=each_job.get('memoryperslave',''), submitdate= each_job.get('submitdate',''), duration=duration, activeapps=each_job.get('name','')).set(1)
                        else:
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), id=each_job.get('id',''), cores=each_job.get('cores',''), memoryperslave=each_job.get('memoryperslave',''), submitdate= each_job.get('submitdate',''), duration=duration, activeapps=each_job.get('name','')).set(0)
                    
        else:
            ''' all envs update for current server active'''
            ''' all_env_status_memory_list -1? 0? 1? at least one?'''
            ''' master node spark job is not running'''
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, types='spark')

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

        ''' First, this operation receives results from one active node to find out the listenen list through 8083 port with connectos endpoint (http://localhost:8083/connectors/) '''
        ''' then, each kafka node receives json results from port 8083 to check the status of kafka listener. '''
        ''' As a result, it is checked whether each listener is running normally. '''
        ''' Prometheus periodically takes exposed metrics and exposes them on the graph. '''
        response_listeners = get_kafka_connector_listeners(monitoring_metrics.get("kafka_url", ""))
        kafka_connect_listeners_gauge_g._metrics.clear()
        is_running_one_of_kafka_listner = False
        any_failure_listener = True
        host_list = []
        ''' kafka Connect health'''
        kafka_state_list = []
        if response_listeners: 
            for host in response_listeners.keys():
                loop = 0
                host_list.append(host)
                for element in response_listeners[host]:
                    if 'error_code' in element:
                        kafka_state_list.append(-1)
                        continue
                    else:
                        if len(element['tasks']) > 0:
                            if element['tasks'][0]['state'].upper() == 'RUNNING':
                                kafka_state_list.append(1)
                                is_running_one_of_kafka_listner = True
                                kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element.get('name',''), running=element['tasks'][0]['state']).set(1)
                            else:
                                kafka_state_list.append(-1)
                                kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element.get('name',''), running=element['tasks'][0]['state']).set(0)
                                ''' add tracking logs'''
                                if 'trace' in  element['tasks'][0]:
                                    saved_failure_dict.update({"{}_{}".format(host, str(loop)) : element.get('name','') + "," + element['tasks'][0]['trace']})
                                else:
                                    saved_failure_dict.update({"{}_{}".format(host, str(loop)) : element.get('name','')})
                                any_failure_listener = False
                                loop += 1

        else:
            ''' all envs update for current server active'''
            ''' all_env_status_memory_list -1? 0? 1? at least one?'''
            ''' master node spark job is not running'''
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, types='kafka_listner')

        logging.info(f"is_running_one_of_kafka_listner - {is_running_one_of_kafka_listner}, host_list : {host_list}")

        ''' get all kafka hosts'''
        kafka_node_hosts = monitoring_metrics.get("kafka_url", "").split(",")
        logging.info(f"kafka_node_hosts - {kafka_node_hosts}")

        if kafka_node_hosts:
            kafka_nodes_list = [node.split(":")[0] for node in kafka_node_hosts]
        else:
            kafka_nodes_list = ""

        logging.info(f"get all kafka hosts - {kafka_nodes_list}")
        ''' add tracking'''
        if not is_running_one_of_kafka_listner:
            ''' all envs update for current server active'''
            ''' all_env_status_memory_list -1? 0? 1? at least one?'''
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, types='kafka_listner')
            saved_failure_dict.update({",".join(kafka_nodes_list) : "all Kafka listeners are not active process running.."})

        ''' add tracking'''
        ''' if one of listener is not running with running status'''
        if not any_failure_listener:
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, types='kafka_listner')


        '''  kafka Connect health Set if listeners are working on all nodes with state of RUNNING'''
        logging.info(f"Kafka_Health : {kafka_state_list}")
        if list(set(kafka_state_list)) == [1]:
            kafka_connect_health_gauge_g.labels(server_job=socket.gethostname()).set(3)
        elif list(set(kafka_state_list)) == [-1] or len(kafka_state_list) < 1:
            kafka_connect_health_gauge_g.labels(server_job=socket.gethostname()).set(0)
        else:
            kafka_connect_health_gauge_g.labels(server_job=socket.gethostname()).set(1)


        ''' get Kafka ISR metrics'''
        # get_kafka_ISR_metrics()

      
        ''' pgrep -f logstash to get process id'''
        ''' set 1 if process id has value otherwise set 0'''
        # -- local instance based
        logstash_instance_gauge_g.labels(socket.gethostname()).set(int(get_Process_Id()))

        ''' all envs update for current server active'''
        ''' all_env_status_memory_list -1? 0? 1? at least one?'''
        logging.info(f"all_envs_status #ES : {all_env_status_memory_list}")

        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kafka_url"]["GREEN_CNT"]), types='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kafka_connect_url"]["GREEN_CNT"]), types='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["zookeeper_url"]["GREEN_CNT"]), types='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kibana_url"]["GREEN_CNT"]), types='kibana')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(get_Process_Id()), types='logstash')

        logging.info(f"all_envs_status #All : {all_env_status_memory_list}")

        ''' ----------------------------------------------------- '''
        ''' Set Server Active Graph'''
        ''' set value for node instance '''
        global saved_status_dict

        if list(set(all_env_status_memory_list)) == [1]:
            ''' green '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(1)
        
        elif list(set(all_env_status_memory_list)) == [-1]:
            ''' red '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(3)
            ''' update gloabl variable for alert email'''
            saved_status_dict.update({'server_active' : 'Red'})

        else:
            ''' yellow '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(2)
            ''' update gloabl variable for alert email'''
            saved_status_dict.update({'server_active' : 'Yellow'})
            
        ''' all envs update for current data pipeline active --> process in db_jobs_work function'''
        ''' ----------------------------------------------------- '''


        ''' expose failure node with a reason'''
        logging.info(f"[metrtics] es_service_jobs_failure_gauge_g - {saved_failure_dict}")
        logging.info(f"[db] es_service_jobs_failure_gauge_g - {saved_failure_db_dict}")
        
        def remove_special_char(input_str):
            ''' remove special char'''
            special_char = '_'
            if special_char not in input_str:
                return input_str
            
            return str(input_str).split(special_char)[0]

        ''' Warning logs clear'''
        es_service_jobs_failure_gauge_g._metrics.clear()

        ''' metric threads'''
        failure_message = []
        for k, v in saved_failure_dict.items():
            es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(),  host=remove_special_char(k), reason=v).set(0)
            failure_message.append(v)
       
        ''' db threads'''
        for k, v in saved_failure_db_dict.items():
            ''' host_ remove'''
            es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), host=remove_special_char(k), reason=v).set(0)
            failure_message.append(v)

        ''' ------------------------------------------------------'''
        ''' send an email these warning message if the status of env has an yellow or red'''
        # email_list = os.environ["EMAIL_LIST"]
        # logging.info(f"mail_list from shell script: {email_list}")
        
        ''' if server status is yellow or red'''
        global saved_thread_alert, saved_thread_alert_message
        if not list(set(all_env_status_memory_list)) == [1] or saved_failure_db_dict:
            ''' if failure mesage has something'''
            if failure_message:
                ''' Call function to send an email'''
                # send_mail(body="',' ".join(failure_message), env=socket.gethostname(), status='Yellow', to=email_list)
                saved_thread_alert = True
                saved_thread_alert_message = failure_message
        else:
            saved_thread_alert = False
        ''' ------------------------------------------------------'''
        
        logging.info(f"saved_thread_alert - {saved_thread_alert}")
        # logging.info(f"saved_thread_alert_message - {saved_thread_alert_message}")
        logging.info(f"saved_status_dict - {saved_status_dict}")

    except Exception as e:
        logging.error(e)


''' global mememoy'''
''' alert message to mail with interval?'''
saved_thread_alert = False
saved_thread_alert_message = []
saved_status_dict = {}


''' dict memory for db failrue'''
saved_failure_db_dict = {}

def db_jobs_work(interval, database_object, sql, db_http_host, db_url):
# def db_jobs_work(interval, db_http_host):
    ''' We can see the metrics with processname and addts fieds if they are working to process normaly'''
    ''' This thread will run if db_run as argument is true and db is online using DB interface RestAPI'''
    
    def get_time_difference(input_str_time):
        ''' get time difference'''
        now_time = datetime.datetime.now()
        print(f"audit_process_name_time - {audit_process_name_time}, : {type(audit_process_name_time)}, now_time - {now_time} : {type(now_time)}")
        date_diff = now_time-audit_process_name_time
        # date_diff = audit_process_name_time-now_time
        print(f"Time Difference - {date_diff}")
        time_hours = date_diff.seconds / 3600
        print(f"Time Difference to hours- {time_hours}")

        return time_hours
    

    ''' db main process with sleep five mintues'''
    global saved_status_dict
    while True:
        try:
            # - main sql
            '''
             [
                {'a': 'v', 'b': 'b1}
            ]
            '''
            StartTime = datetime.datetime.now()
            db_transactin_time = 0.0

            ''' clear saved_failure_db_dict '''
            saved_failure_db_dict.clear()

            if db_http_host:
                '''  retrieve records from DB interface REST API URL using requests library'''
                logging.info("# HTTP Interface")

                ''' call to DB interface RestAPI'''
                request_body = {
                        "db_url" : db_url,
                        "sql" : sql
                }

                logging.info("db_http_host : {}, db_url : {}, sql : {}".format(db_http_host, db_url, sql))
                resp = requests.post(url="http://{}/db/get_db_query".format(db_http_host), json=request_body, timeout=20)
                
                if not (resp.status_code == 200):
                    ''' clear table for db records if host not reachable'''
                    db_jobs_gauge_g._metrics.clear()
                    ''' DB error '''
                    logging.info(f"{resp.json()['message']}")
                    all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(2)
                    ''' expose failure node with a reason'''
                    # es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason="No 'ES_PIPELINE_UPLOAD_TEST_WM' Process").set(0)
                    saved_failure_db_dict.update({'db-jobs' : resp.json()['message']})
                    saved_status_dict.update({'es_pipeline' : 'Red'})
                    return None
                
                logging.info(f"db/process_table - {resp}")
                ''' db job performance through db interface restapi'''
                # db_jobs_performance_gauge_g.labels(server_job=socket.gethostname()).set(int(resp.json["running_time"]))
                result_json_value = resp.json()["results"]
                db_transactin_time = resp.json()["running_time"]
         
            else:
                ''' This logic perform to connect to DB directly and retrieve records from processd table '''
                logging.info("# DB Interface Directly")
                result_json_value = database_object.excute_oracle_query(sql)

            ''' DB processing time '''
            EndTime = datetime.datetime.now()
            Delay_Time = str((EndTime - StartTime).seconds) + '.' + str((EndTime - StartTime).microseconds).zfill(6)[:2]
            logging.info("# DB Query Running Time - {}".format(str(Delay_Time)))

            ''' clear table for db records if host not reachable'''
            db_jobs_gauge_g._metrics.clear()

            ''' calculate delay time for DB'''
            ''' if db_http_post set db_transactin_time from HTTP interface API otherwise set Delay time'''
            db_transactin_perfomrance = db_transactin_time if db_http_host else Delay_Time
            db_jobs_performance_gauge_g.labels(server_job=socket.gethostname()).set(float(db_transactin_perfomrance))

            ''' response same format with list included dicts'''   
            logging.info(result_json_value)
            # db_jobs_gauge_g._metrics.clear()
            is_exist_process_name_for_es = False
            if result_json_value:
                for element_each_json in result_json_value:
                    # logging.info('# rows : {}'.format(element_each_json))
                    db_jobs_gauge_g.labels(server_job=socket.gethostname(), processname=element_each_json['PROCESSNAME'], status=element_each_json['STATUS'], cnt=element_each_json["COUNT(*)"], addts=element_each_json["ADDTS"], dbid=element_each_json['DBID']).set(1)
                    if 'PROCESSNAME' in element_each_json:
                        ''' all envs update for current data pipeline active --> process in db_jobs_work function'''
                        if element_each_json.get('PROCESSNAME','') == 'ES_PIPELINE_UPLOAD_TEST_WM':
                            ''' set this variable if this process is working'''
                            is_exist_process_name_for_es = True
                            audit_process_name_time = datetime.datetime.strptime(element_each_json.get("ADDTS",""), "%Y-%m-%d %H:%M:%S")
                            time_difference_to_hours = get_time_difference(audit_process_name_time)
                            ''' ES PIPELINE AUDIT PROCESS If the processing time is 30 minutes slower than the current time, we believe there may be a problem with the process.'''
                            if time_difference_to_hours > 0.5:
                                ''' red'''
                                logging.info(f"Time Difference with warining from the process - {time_difference_to_hours}")
                                all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(2)
                                ''' update gloabl variable for alert email'''
                                saved_status_dict.update({'es_pipeline' : 'Red'})
                                ''' expose failure node with a reason'''
                                # es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason="'ES_PIPELINE_UPLOAD_TEST_WM' ADDTS time is 30 minutes later than current time").set(0)
                                saved_failure_db_dict.update({element_each_json.get('DBID', 'db_jobs') : "ES_PIPELINE_UPLOAD_TEST_WM' ADDTS time is 30 minutes later than current time"})
                            else:
                                ''' green'''
                                all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(1)

            ''' if ES_PIPELINE_UPLOAD_TEST_WM process doesn't exist in es_pipeline_processed table'''
            if not is_exist_process_name_for_es:
                ''' red'''
                logging.info(f"No 'ES_PIPELINE_UPLOAD_TEST_WM' Process")
                all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(2)
                ''' expose failure node with a reason'''
                # es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason="No 'ES_PIPELINE_UPLOAD_TEST_WM' Process").set(0)
                saved_failure_db_dict.update({'db-jobs' : "No 'ES_PIPELINE_UPLOAD_TEST_WM' Process"})
                saved_status_dict.update({'es_pipeline' : 'Red'})

            logging.info("\n\n")
            
        except Exception as e:
            logging.error(e)
            pass
        
        # time.sleep(interval)
        ''' update after five minutes'''
        time.sleep(interval)


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
        logging.info(f"\n\nStandalone Prometheus Exporter Server started..")

        while True:
            StartTime = datetime.datetime.now()

            ''' Collection metrics from ES/Kafka/Spark/Kibana/Logstash'''
            get_metrics_all_envs(monitoring_metrics)
            
            ''' export application processing time '''
            EndTime = datetime.datetime.now()
            Delay_Time = str((EndTime - StartTime).seconds) + '.' + str((EndTime - StartTime).microseconds).zfill(6)[:2]
            logging.info("# Export Application Running Time - {}\n\n".format(str(Delay_Time)))
            es_service_jobs_performance_gauge_g.labels(server_job=socket.gethostname()).set(float(Delay_Time))
            
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

    except (KeyboardInterrupt, SystemExit):
        logging.info("#Interrupted..")
       


def alert_work(db_http_host):
    ''' thread for alert'''

    def json_read_config(path):
        ''' read config file with option'''
        with open(path, "r") as read_file:
            data = json.load(read_file)
        return data

    try:
        global saved_failure_dict
        while True:
            ''' read config file to enable/disable to send an email'''
            '''
            data = json_read_config("./mail/config.json")
            logging.info(f"config json file : {data}")
            '''

            # logging.info(f"\n\nmail treading working..")

            ''' interface es_config_api http://localhost:8004/config/get_mail_config '''
            es_config_host = str(db_http_host).split(":")[0]
            logging.info(f"es_config_host : {es_config_host}")
            resp = requests.get(url="http://{}:8004/config/get_mail_config".format(es_config_host), timeout=5)
                
            if not (resp.status_code == 200):
                ''' save failure node with a reason into saved_failure_dict'''
                logging.error(f"es_config_interface api do not reachable")
                saved_failure_dict.update({socket.gethostname(): "es_config_interface_api do not reachable"})
                continue
                
            # logging.info(f"get_mail_config - {resp}, {json.dumps(resp.json(), indent=2)}")
            logging.info(f"get_mail_config - {resp}, {resp.json()}")
            data = resp.json()

            ''' ------------------------------------------------------'''
            ''' send an email these warning message if the status of env has an yellow or red'''
            # email_list = os.environ["EMAIL_LIST"]
            # email_list = data.get("mail_list")

            thread_interval = int(data.get("thread_interval"))
            logging.info(f"get_mail_config [thread_interval] - {thread_interval}")
            logging.info(f"get_dashbaord_from_shell- {os.environ['GRAFANA_DASHBOARD_URL']}")

            '''
            {
                "dev": {
                    "mail_list": "test",
                    "is_mailing": true
                },
                "localhost": {
                    "mail_list": "test",
                    "is_mailing": true
                }
            }    
            '''
            get_es_config_interface_api_host_key = socket.gethostname().split(".")[0]

            email_list = data[get_es_config_interface_api_host_key].get("mail_list")
            logging.info(f"mail_list from shell script: {email_list}")
            logging.info(f"is_mailing: {data[get_es_config_interface_api_host_key].get('is_mailing')}, type : {type(data[get_es_config_interface_api_host_key].get('is_mailing'))}")

            logging.info(f"saved_status_dict - {json.dumps(saved_status_dict, indent=2)}")
            
            ''' Call function to send an email'''
            ''' global mememoy'''
            ''' alert message to mail with interval?'''
            if saved_thread_alert:
                # if data.get("is_mailing"):
                if data[get_es_config_interface_api_host_key].get("is_mailing"):
                    logging.info("\n\nSending email..")
                    send_mail(body="\n\t".join(saved_thread_alert_message), host=get_es_config_interface_api_host_key, env=data[get_es_config_interface_api_host_key].get("env"), status_dict=saved_status_dict, to=email_list)
            ''' ------------------------------------------------------'''
            
            logging.info(f"saved_thread_alert - {saved_thread_alert}")
            # logging.info(f"saved_thread_alert_message - {saved_thread_alert_message}")
            
            ''' every one day to send an alert email'''
            # time.sleep(60*60*24)
            ''' every one hour to send an alert email'''
            # time.sleep(60*60)
            # time.sleep(60)
            time.sleep(60*thread_interval)

    except (KeyboardInterrupt, SystemExit):
        logging.info("#Interrupted..")



# Function that send email.
def send_mail(body, host, env, status_dict, to):

    def cleanText(readData):
        text = re.sub('[-=+,#/\?:^$.@*\"※~&%ㆍ!』\\‘|\[\]\(\)\<\>`\'…》]', '', readData)
        return text

    try:
        ''' send mail through mailx based on python environment'''
        grafana_dashboard_url = os.environ["GRAFANA_DASHBOARD_URL"]
        
        ''' remove special characters'''
        '''
        body = body.replace('(', "'('").replace(')', "')'")
        body = body.replace('\n\t', " ").replace('(', "").replace(')', "").replace('\n', " ")
        body = re.sub(r"[^\uAC00-\uD7A30-9a-zA-Z\s]", " ", body)
        body = cleanText(body)
        '''
        body = body.encode('utf-8')
        ''' remove b first character'''
        logging.info(f"send_mail -> Mail Alert message : {body}")
    
        body = "Monitoring [ES Team Dashboard on export application]'\n\t' \
            - Grafana Dashboard URL : {}'\n\t' \
            - Enviroment: {}, Prometheus Export Application Runnig Host : {}, Export Application URL : http://{}:9115'\n\t' \
            - Server Status: {}, ES_PIPELINE Status : {}'\n\t' \
            - Alert Message : {} \
            ".format(grafana_dashboard_url, env, host, host, status_dict.get("server_active","Green"), status_dict.get("es_pipeline","Green"), body)
        
        email_user_list = to.split(",")
        print(f"email_user_list : {email_user_list}")
        """
        for user in email_user_list:
            print(user)
            cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert' " + "-c a@test.mail " + to
            result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            output, errors = result.communicate()
            if output:
                print(f"Send mail to user : {user}, output : {output}")
            if errors:
                print(errors)
        """

        # cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert' " + "-c a@test.mail " + to
        cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert [{env}]' " + to
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output, errors = result.communicate()
        if output:
            print(f"Send mail output : {output}")
        if errors:
            print(errors)
    except Exception as e:
        logging.error(e)




if __name__ == '__main__':
    '''
    ./standalone-export-run.sh -> ./standalone-es-service-export.sh status/stop/start
    # first node of --kafka_url argument is a master node to get the number of jobs using http://localhost:8080/json
    # -- direct access to db
    python ./standalone-es-service-export.py --interface db --url jdbc:oracle:thin:id/passwd@address:port/test_db --db_run false --kafka_url localhost:9092,localhost:9092,localhost:9092 --kafka_connect_url localhost:8083,localhost:8083,localhost:8083 --zookeeper_url  localhost:2181,localhost:2181,localhost:2181 --es_url localhost:9200,localhost:9201,localhost:9201,localhost:9200 --kibana_url localhost:5601 --sql "SELECT processname from test"
    # -- collect records through DB interface Restapi
    python ./standalone-es-service-export.py --interface http --db_http_host localhost:8002 --url jdbc:oracle:thin:id/passwd@address:port/test_db --db_run false --kafka_url localhost:9092,localhost:9092,localhost:9092 --kafka_connect_url localhost:8083,localhost:8083,localhost:8083 --zookeeper_url  localhost:2181,localhost:2181,localhost:2181 --es_url localhost:9200,localhost:9201,localhost:9201,localhost:9200 --kibana_url localhost:5601 --sql "SELECT processname from test"
    '''
    parser = argparse.ArgumentParser(description="Script that might allow us to use it as an application of custom prometheus exporter")
    parser.add_argument('--kafka_url', dest='kafka_url', default="localhost:29092,localhost:39092,localhost:49092", help='Kafka hosts')
    parser.add_argument('--kafka_connect_url', dest='kafka_connect_url', default="localhost:8083,localhost:8084,localhost:8085", help='Kafka connect hosts')
    parser.add_argument('--zookeeper_url', dest='zookeeper_url', default="localhost:22181,localhost:21811,localhost:21812", help='zookeeper hosts')
    parser.add_argument('--es_url', dest='es_url', default="localhost:9200,localhost:9501,localhost:9503", help='es hosts')
    parser.add_argument('--kibana_url', dest='kibana_url', default="localhost:5601,localhost:15601", help='kibana hosts')
    ''' ----------------------------------------------------------------------------------------------------------------'''
    ''' set DB or http interface api'''
    parser.add_argument('--interface', dest='interface', default="db", help='db or http')
    ''' set DB connection dircectly'''
    parser.add_argument('--url', dest='url', default="postgresql://postgres:1234@localhost:5432/postgres", help='db url')
    parser.add_argument('--db_run', dest="db_run", default="False", help='If true, executable will run after compilation.')
    parser.add_argument('--sql', dest='sql', default="select * from test", help='sql')
    ''' request DB interface restpi insteady of connecting db dircectly'''
    parser.add_argument('--db_http_host', dest='db_http_host', default="http://localhost:8002", help='db restapi url')
    ''' ----------------------------------------------------------------------------------------------------------------'''
    parser.add_argument('--port', dest='port', default=9115, help='Expose Port')
    parser.add_argument('--interval', dest='interval', default=30, help='Interval')
    args = parser.parse_args()

    ''' 
    The reason why I created this dashboard was because on security patching day, 
    we had to check the status of ES cluster/kafka/spark job and kibana/logstash manually every time Even if it is automated with Jenkins script.
    
    The service monitoring export we want does not exist in the built-in export application that is already provided. 
    To reduce this struggle, I developed it using the prometheus library to check the status at once on the dashboard.

    Prometheus provides client libraries based on Python, Go, Ruby and others that we can use to generate metrics with the necessary labels.
    When Prometheus scrapes your instance's HTTP endpoint, the client library sends the current state of all tracked metrics to the server. 
    The prometheus_client package supports exposing metrics from software written in Python, so that they can be scraped by a Prometheus service. 
    '''

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

    ''' ----------------------------------------------------------------------------------------------------------------'''
    ''' set DB or http interface api'''
    if args.interface:
        interface = args.interface

    ''' set DB connection dircectly'''
    if args.url:
        db_url = args.url
    
    if args.db_run:
        db_run = args.db_run

    if args.sql:
        sql = args.sql

    ''' request DB interface restpi insteady of connecting db dircectly'''
    if args.db_http_host:
        db_http_host = args.db_http_host
    ''' ----------------------------------------------------------------------------------------------------------------'''

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

    db_run = True if str(db_run).upper() == "TRUE" else False
    print(interface, db_run, type(db_run), sql)

    if interface == 'db' and db_run:
        database_object = oracle_database(db_url)
    else:
        database_object = None
    
    # work(int(port), int(interval), monitoring_metrics)

    try:
        T = []
        '''
        th1 = Thread(target=test)
        th1.daemon = True
        th1.start()
        T.append(th1)
        '''
        
        ''' es/kafka/kibana/logstash prcess check thread'''
        for host in ['localhost']:
            ''' main process to collect metrics'''
            main_th = Thread(target=work, args=(int(port), int(interval), monitoring_metrics))
            main_th.daemon = True
            main_th.start()
            T.append(main_th)

            ''' alert through mailx'''
            mail_th = Thread(target=alert_work, args=(db_http_host,))
            mail_th.daemon = True
            mail_th.start()
            T.append(mail_th)

        
        ''' Set DB connection to validate the status of data pipelines after restart kafka cluster when security patching '''
        ''' We can see the metrics with processname and addts fieds if they are working to process normaly'''
        ''' we create a single test record every five minutes and we upload that test record into a elastic search '''
        ''' and we do that just for auditing purposes to check the overall health of the data pipeline to ensure we're continually processing data '''
        ''' This thread will run every five minutes if db_run as argument is true and db is online'''
        # --
       
        if interface == 'db':
            ''' access to db directly to collect records to check the overall health of the data pipleline'''
            if db_run and database_object.get_db_connection():
                db_thread = Thread(target=db_jobs_work, args=(300, database_object, sql, None, None))
                db_thread.daemon = True
                db_thread.start()
                T.append(db_thread)
        
        elif interface == 'http':
            ''' request DB interface restpi insteady of connecting db dircectly '''
            db_http_thread = Thread(target=db_jobs_work, args=(300, None, sql, db_http_host, db_url))
            db_http_thread.daemon = True
            db_http_thread.start()
            T.append(db_http_thread)

        # wait for all threads to terminate
        for t in T:
            while t.is_alive():
                t.join(0.5)

    except (KeyboardInterrupt, SystemExit):
        logging.info("# Interrupted..")

    finally:
        if interface == 'db' and db_run:
            database_object.set_db_disconnection()
            database_object.set_init_JVM_shutdown()
        
    logging.info("Standalone Prometheus Exporter Server exited..!")
    
    
     
 