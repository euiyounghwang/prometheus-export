# python-prometheus-export
<i>python-prometheus-export

Prometheus provides client libraries based on Python, Go, Ruby and others that we can use to generate metrics with the necessary labels. 
- Such an exporter can be included directly in the code of your application
- it can be run as a separate service that will poll one of your services and receive data from it, which will then be converted into the Prometheus format and sent to the Prometheus server. 

When Prometheus scrapes your instance's HTTP endpoint, the client library sends the current state of all tracked metrics to the server.

The prometheus_client package supports exposing metrics from software written in Python, so that they can be scraped by a Prometheus service.
Metrics can be exposed through a standalone web server, or through Twisted, WSGI and the node exporter textfile collector.


### Using Poetry: Create the virtual environment in the same directory as the project and install the dependencies:
```bash
poetry config virtualenvs.in-project true
poetry init
poetry add prometheus-client
```
or you can run this shell script `./create_virtual_env.sh` to make an environment. then go to virtual enviroment using `source .venv/bin/activate`



### Installation
```
pip install prometheus-client
```
