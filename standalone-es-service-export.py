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
zookeeper_nodes_gauge_g = Gauge("zookeeper_health_metric", 'Metrics scraped from localhost', ["server_job"])
kibana_instance_gauge_g = Gauge("kibana_health_metric", 'Metrics scraped from localhost', ["server_job"])
logstash_instance_gauge_g = Gauge("logstash_health_metric", 'Metrics scraped from localhost', ["server_job"])
spark_jobs_gauge_g = Gauge("spark_jobs_running_metrics", 'Metrics scraped from localhost', ["server_job", "id", "cores", "memoryperslave", "submitdate", "duration", "activeapps"])
db_jobs_gauge_g = Gauge("db_jobs_running_metrics", 'Metrics scraped from localhost', ["server_job", "processname", "cnt", "status", "addts", "dbid"])
db_jobs_performance_gauge_g = Gauge("db_jobs_performance_running_metrics", 'Metrics scraped from localhost', ["server_job"])

''' export failure instance list metric'''
es_service_jobs_failure_gauge_g = Gauge("es_service_jobs_failure_running_metrics", 'Metrics scraped from localhost', ["server_job", "reason"])



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
    
    ''' save failure nodes into dict'''
    saved_failure_dict = {}

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
                    ''' save failure node with a reason into saved_failure_dict'''
                    saved_failure_dict.update({each_urls[0] : each_host + " Port closed"})
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
                loop = 1
                for listener in active_listner_connect:
                    try:
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
            if not node:
                return None
            logging.info(f"get_spark_jobs - {node}")
            master_node = node.split(",")[0].split(":")[0]
            logging.info(f"get_spark_jobs #1- {master_node}")

            # -- make a call to master node to get the information of activeapps
            resp = requests.get(url="http://{}:8080/json".format(master_node), timeout=5)
            
            if not (resp.status_code == 200):
                ''' save failure node with a reason into saved_failure_dict'''
                saved_failure_dict.update({node : "http://{}:8080/json API do not reachable".format(master_node)})
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
                # -- make a call to node
                resp = requests.get(url="http://{}/_cluster/health".format(each_es_host), timeout=5)
                
                if not (resp.status_code == 200):
                    ''' save failure node with a reason into saved_failure_dict'''
                    # saved_failure_dict.update({each_es_host.split(":")[0] : each_es_host + " Port closed"})
                    continue
                
                logging.info(f"activeES - {resp}, {resp.json()}")
                return resp.json()
                
            return None

        except Exception as e:
            logging.error(e)


    def get_all_envs_status(all_env_status, value, type=None):
        ''' return all_envs_status status'''
        logging.info('get_all_envs_status - {} -> merged list : {}'.format(value, all_env_status))
        try:
            if type == 'kafka':
                if value == 3:
                    all_env_status.append(1)
                elif value > 0 and value <3:
                    all_env_status.append(0)
                else:
                    all_env_status.append(-1)
            else:
                if value == 1:
                    ''' green'''
                    all_env_status.append(1)
                elif value == 0:
                    ''' yellow'''
                    all_env_status.append(0)
                else:
                    ''' red'''
                    all_env_status.append(-1)
            
            return all_env_status

        except Exception as e:
            logging.error(e)

    try: 
        ''' all_envs_status : 0 -> red, 1 -> yellow, 2 --> green '''
        all_env_status_memory_list = []          

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

        ''' check the status of nodes on all kibana/kafka/connect except es nodes by using socket '''
        ''' The es cluster is excluded because it has already been checked in get_elasticsearch_health function'''
        monitoring_metrics_cp = copy.deepcopy(monitoring_metrics)
        # del monitoring_metrics_cp["es_url"]
        logging.info("monitoring_metrics_cp - {}".format(json.dumps(monitoring_metrics_cp, indent=2)))

        ''' socket.connect_ex( <address> ) similar to the connect() method but returns an error indicator of raising an exception for errors '''
        ''' The error indicator is 0 if the operation succeeded, otherwise the value of the errno variable. '''
        ''' Kafka/Kafka connect/Spark/Kibana'''
        response_dict = get_service_port_alive(monitoring_metrics_cp)

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
            # spark_jobs_gauge_g
            for each_job in response_spark_jobs:
                duration = str(round(float(each_job["duration"])/(60.0*60.0*1000.0),2)) + " h" if 'duration' in each_job else -1
                # logging.info(duration)
                for k, v in each_job.items():
                    if k  == 'state':
                        if v.upper() == 'RUNNING':
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), 
                                                      id=each_job.get('id',''),
                                                      cores=each_job.get('cores',''), 
                                                      memoryperslave=each_job.get('memoryperslave',''), 
                                                      submitdate= each_job.get('submitdate',''),
                                                      duration=duration, 
                                                      activeapps=each_job.get('name','')
                                                      ).set(1)
                        else:
                            spark_jobs_gauge_g.labels(server_job=socket.gethostname(), 
                                                      id=each_job.get('id',''),
                                                      cores=each_job.get('cores',''), 
                                                      memoryperslave=each_job.get('memoryperslave',''), 
                                                      submitdate= each_job.get('submitdate',''),
                                                      duration=duration, 
                                                      activeapps=each_job.get('name','')
                                                      ).set(0)
                    
        else:
            ''' all envs update for current server active'''
            ''' all_env_status_memory_list -1? 0? 1? at least one?'''
            ''' master node spark job is not running'''
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, type='spark')

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
        if response_listeners: 
            for host in response_listeners.keys():
                for element in response_listeners[host]:
                    if 'error_code' in element:
                        continue
                    else:
                        if len(element['tasks']) > 0:
                            if element['tasks'][0]['state'].upper() == 'RUNNING':
                                kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element.get('name',''), running=element['tasks'][0]['state']).set(1)
                            else:
                                kafka_connect_listeners_gauge_g.labels(server_job=socket.gethostname(), host=host, name=element.get('name',''), running=element['tasks'][0]['state']).set(0)

        else:
            ''' all envs update for current server active'''
            ''' all_env_status_memory_list -1? 0? 1? at least one?'''
            ''' master node spark job is not running'''
            all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, -1, type='kafka_listner')

        ''' pgrep -f logstash to get process id'''
        ''' set 1 if process id has value otherwise set 0'''
        # -- local instance based
        logstash_instance_gauge_g.labels(socket.gethostname()).set(int(get_Process_Id()))

        ''' all envs update for current server active'''
        ''' all_env_status_memory_list -1? 0? 1? at least one?'''
        logging.info(f"all_envs_status #ES : {all_env_status_memory_list}")

        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kafka_url"]["GREEN_CNT"]), type='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kafka_connect_url"]["GREEN_CNT"]), type='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["zookeeper_url"]["GREEN_CNT"]), type='kafka')
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(response_dict["kibana_url"]["GREEN_CNT"]))
        all_env_status_memory_list = get_all_envs_status(all_env_status_memory_list, int(get_Process_Id()))

        logging.info(f"all_envs_status #All : {all_env_status_memory_list}")

        ''' set value for node instance '''
        if list(set(all_env_status_memory_list)) == [1]:
            ''' green '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(1)
        
        elif list(set(all_env_status_memory_list)) == [-1]:
            ''' red '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(3)

        else:
            ''' yellow '''
            all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='cluster').set(2)

        ''' all envs update for current data pipeline active --> process in db_jobs_work function'''

        ''' expose failure node with a reason'''
        logging.info(f"es_service_jobs_failure_gauge_g - {saved_failure_dict}")
        es_service_jobs_failure_gauge_g._metrics.clear()
        for k, v in saved_failure_dict.items():
            es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason=v).set(0)
            

    except Exception as e:
        logging.error(e)




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
                                ''' expose failure node with a reason'''
                                es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason="'ES_PIPELINE_UPLOAD_TEST_WM' ADDTS time is 30 minutes later than current time").set(0)
                            else:
                                ''' green'''
                                all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(1)

            ''' if ES_PIPELINE_UPLOAD_TEST_WM process doesn't exist in es_pipeline_processed table'''
            if not is_exist_process_name_for_es:
                ''' red'''
                logging.info(f"No 'ES_PIPELINE_UPLOAD_TEST_WM' Process")
                all_envs_status_gauge_g.labels(server_job=socket.gethostname(), type='data_pipeline').set(2)
                ''' expose failure node with a reason'''
                es_service_jobs_failure_gauge_g.labels(server_job=socket.gethostname(), reason="No 'ES_PIPELINE_UPLOAD_TEST_WM' Process").set(0)
            
        except Exception as e:
            logging.error(e)
        
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
        logging.info(f"Standalone Prometheus Exporter Server started..")

        while True:
            StartTime = datetime.datetime.now()

            ''' Collection metrics from ES/Kafka/Spark/Kibana/Logstash'''
            get_metrics_all_envs(monitoring_metrics)
            
            ''' export application processing time '''
            EndTime = datetime.datetime.now()
            Delay_Time = str((EndTime - StartTime).seconds) + '.' + str((EndTime - StartTime).microseconds).zfill(6)[:2]
            logging.info("# Export Application Running Time - {}".format(str(Delay_Time)))
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
            th1 = Thread(target=work, args=(int(port), int(interval), monitoring_metrics))
            th1.daemon = True
            th1.start()
            T.append(th1)
        
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
    
    
     
 