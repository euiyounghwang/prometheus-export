# prometheus-export
<i>python-prometheus-export

Prometheus provides client libraries based on Python, Go, Ruby and others that we can use to generate metrics with the necessary labels. 
- Such an exporter can be included directly in the code of your application
- it can be run as a separate service that will poll one of your services and receive data from it, which will then be converted into the Prometheus format and sent to the Prometheus server. 

When Prometheus scrapes your instance's HTTP endpoint, the client library sends the current state of all tracked metrics to the server.

The prometheus_client package supports exposing metrics from software written in Python, so that they can be scraped by a Prometheus service.
Metrics can be exposed through a standalone web server, or through Twisted, WSGI and the node exporter textfile collector.


#### Python V3.9 Install
```bash
sudo yum install gcc openssl-devel bzip2-devel libffi-devel zlib-devel git 
wget https://www.python.org/ftp/python/3.9.0/Python-3.9.0.tgz 
tar –zxvf Python-3.9.0.tgz or tar -xvf Python-3.9.0.tgz 
cd Python-3.9.0 
./configure --libdir=/usr/lib64 
sudo make 
Sudo make altinstall 

# python3 -m venv .venv --without-pip
sudo yum install python3-pip

sudo ln -s /usr/lib64/python3.9/lib-dynload/ /usr/local/lib/python3.9/lib-dynload

python3 -m venv .venv
source .venv/bin/activate

# pip install -r ./requirement.txt
pip install prometheus-client
pip install requests

# when error occur like this
# ImportError: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'OpenSSL 1.0.2k-fips  26 Jan 2017'. See: https://github.com/urllib3/urllib3/issues/2168
pip install urllib3==1.26.18
pip install pytz
```


### Using Poetry: Create the virtual environment in the same directory as the project and install the dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install poetry

# --
poetry config virtualenvs.in-project true
poetry init
poetry add prometheus-client
poetry add psutil
poetry add pytz
poetry add JPype1
poetry add psycopg2-binary
poetry add jaydebeapi
```
or you can run this shell script `./create_virtual_env.sh` to make an environment. then go to virtual enviroment using `source .venv/bin/activate`



### Installation
```bash
pip install prometheus-client
```

### Custom Promethues Exporter
- Expose my metrics for dev kafka cluster to http://localhost:9115
```bash
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 302.0
python_gc_objects_collected_total{generation="1"} 342.0
python_gc_objects_collected_total{generation="2"} 0.0
# HELP python_gc_objects_uncollectable_total Uncollectable objects found during GC
# TYPE python_gc_objects_uncollectable_total counter
python_gc_objects_uncollectable_total{generation="0"} 0.0
python_gc_objects_uncollectable_total{generation="1"} 0.0
python_gc_objects_uncollectable_total{generation="2"} 0.0
# HELP python_gc_collections_total Number of times this generation was collected
# TYPE python_gc_collections_total counter
python_gc_collections_total{generation="0"} 53.0
python_gc_collections_total{generation="1"} 4.0
python_gc_collections_total{generation="2"} 0.0
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="11",patchlevel="7",version="3.11.7"} 1.0
# HELP hitl_psql_health_status PSQL connection health
# TYPE hitl_psql_health_status gauge
hitl_psql_health_status{hitl_psql_health_status="healthy"} 1.0
hitl_psql_health_status{hitl_psql_health_status="unhealthy"} 0.0
# HELP hitl_psql_health_request_time PSQL connection response time (seconds)
# TYPE hitl_psql_health_request_time histogram
hitl_psql_health_request_time_bucket{le="0.005"} 0.0
hitl_psql_health_request_time_bucket{le="0.01"} 0.0
hitl_psql_health_request_time_bucket{le="0.025"} 0.0
hitl_psql_health_request_time_bucket{le="0.05"} 2.0
hitl_psql_health_request_time_bucket{le="0.075"} 3.0
hitl_psql_health_request_time_bucket{le="0.1"} 4.0
hitl_psql_health_request_time_bucket{le="0.25"} 4.0
hitl_psql_health_request_time_bucket{le="0.5"} 4.0
hitl_psql_health_request_time_bucket{le="0.75"} 4.0
hitl_psql_health_request_time_bucket{le="1.0"} 4.0
hitl_psql_health_request_time_bucket{le="2.5"} 4.0
hitl_psql_health_request_time_bucket{le="5.0"} 4.0
hitl_psql_health_request_time_bucket{le="7.5"} 4.0
hitl_psql_health_request_time_bucket{le="10.0"} 4.0
hitl_psql_health_request_time_bucket{le="+Inf"} 4.0
hitl_psql_health_request_time_count 4.0
hitl_psql_health_request_time_sum 0.2218436000039219
# HELP hitl_psql_health_request_time_created PSQL connection response time (seconds)
# TYPE hitl_psql_health_request_time_created gauge
hitl_psql_health_request_time_created 1.7159152249493546e+09
# HELP es_health_metric Metrics scraped from localhost
# TYPE es_health_metric gauge
es_health_metric{server_job="localhost"} 4.0
# HELP kafka_health_metric Metrics scraped from localhost
# TYPE kafka_health_metric gauge
kafka_health_metric{server_job="localhost"} 3.0
# HELP kibana_health_metric Metrics scraped from localhost
# TYPE kibana_health_metric gauge
kibana_health_metric{server_job="localhost"} 1.0
# HELP logstash_health_metric Metrics scraped from localhost
# TYPE logstash_health_metric gauge
logstash_health_metric{server_job="localhost"} 1.0
```


### Run Custom Promethues Exporter
- Run this command : $ `python ./standalone-es-service-export.py` or `./standalone-export-run.sh`
```bash

#-- HTTP Server/Client Based
# HTTP Server
$  ./es-service-all-server-export-run.sh status/start/stop or ./server-export-run.sh
Server started.

# Client export
$  ./es-service-all-client-export-run.sh status/start/stop or ./client-export-run.sh

# Client only
./standalone-es-service-export.sh status/start/stop

...
[2024-05-20 20:44:06] [INFO] [prometheus_client_export] [work] http://localhost:9999/health?kafka_url=localhost:9092,localhost:9092,localhost:9092&es_url=localhost:9200,localhost:9200,localhost:9200,localhost:9200&kibana_url=localhost:5601&logstash_url=process
[2024-05-20 20:44:06] [INFO] [prometheus_client_export] [get_metrics_all_envs] 200
[2024-05-20 20:44:06] [INFO] [prometheus_client_export] [get_metrics_all_envs] <Response [200]>
[2024-05-20 20:44:06] [INFO] [prometheus_client_export] [get_metrics_all_envs] {'kafka_url': {'localhost:9092': 'OK', 'GREEN_CNT': 3, 'localhost:9092': 'OK', 'localhost:9092': 'OK'}, 'es_url': {'localhost:9200': 'OK', 'GREEN_CNT': 4, 'localhost:9200': 'OK', 'localhost:9200': 'OK', 'localhost:9200': 'OK'}, 'kibana_url': {'localhost:5601': 'OK', 'GREEN_CNT': 1}, 'logstash_url': 1}
...
```