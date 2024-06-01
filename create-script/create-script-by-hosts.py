
import json
import logging


logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)


def making_script(db_url, kafka_url, kafka_connect_url, zookeeper_url, es_url, kibana_url):
    ''' create python script command per every environment'''
    script_arguments = 'python ./standalone-es-service-export.py --interface http --db_http_host tsgvm00875:8002 --url jdbc:oracle:thin:bi"$"reporting/{} --db_run false --kafka_url {} --kafka_connect_url {} --zookeeper_url  {} --es_url {} --kibana_url {} --interval 30 --sql "SELECT processname, status, MAX (CAST (addts AS DATE)) as addts, COUNT (*), get_db_name as dbid FROM es_pipeline_processed a WHERE addts >= TRUNC (SYSTIMESTAMP) AND status IN (\'E\', \'C\') GROUP BY processname, status ORDER BY 3 DESC"' \
    .format(db_url, kafka_url, kafka_connect_url, zookeeper_url, es_url, kibana_url)

    return script_arguments


def transform_json_to_each_arguments(host_dict):
    # db_url, kafka_url, kafka_connect_url, zookeeper_url, es_url, kibana_url = '', '', '', '', '', ''
    hosts_dicts = {}
    for key, value in host_dict.items():
        hosts_dict ={}
        for element in value:
            for k, v in element.items():
               
                if 'kibana' in str(k).lower():
                    kibana_url = "{}:5601".format(str(v))
                    hosts_dict.update({'kibana' :  kibana_url})
               
                if 'nodes' in str(k).lower():
                    # print(k)
                    es_url = "{}:9200".format(str(v))
                    if 'es_url' not in hosts_dict.keys():
                        hosts_dict.update({'es_url' :  [es_url]})
                    else:
                        hosts_dict['es_url'].append(es_url)
                    # print("#2", hosts_dict)
               
                if 'transfer' in str(k).lower():
                    # print(k)
                    kafka_url = "{}:9092".format(str(v))
                    if 'kafka_url' not in hosts_dict.keys():
                        hosts_dict.update({'kafka_url' :  [kafka_url]})
                    else:
                        hosts_dict['kafka_url'].append(kafka_url)
                    # print("#2", hosts_dict)

                    kafka_connect_url = "{}:8083".format(str(v))
                    if 'kafka_connect_url' not in hosts_dict.keys():
                        hosts_dict.update({'kafka_connect_url' :  [kafka_connect_url]})
                    else:
                        hosts_dict['kafka_connect_url'].append(kafka_connect_url)


                    zookeeper_url = "{}:2181".format(str(v))
                    if 'zookeeper_url' not in hosts_dict.keys():
                        hosts_dict.update({'zookeeper_url' :  [zookeeper_url]})
                    else:
                        hosts_dict['zookeeper_url'].append(zookeeper_url)

        
        if key not in hosts_dict.keys():
            hosts_dicts.update({key : hosts_dict})
        else:
            hosts_dicts[key] = hosts_dict
    
    logging.info(json.dumps(hosts_dicts, indent=2))


    def export_file(hosts_dicts):
        ''' export to file '''
        with open("./script_envs", "w") as f:
            ''' call to making_script'''
            for k, v in hosts_dicts.items():
                kibana_url = v.get("kibana")
                print('\n')
                print(f"# {k} ENV")
                script_env = making_script(db_url=None, kafka_url=','.join(v.get("kafka_url")).lower(), kafka_connect_url=','.join(v.get("kafka_connect_url")).lower(), zookeeper_url=','.join(v.get("zookeeper_url")).lower(), es_url=','.join(v.get("es_url")).lower(), kibana_url=v.get("kibana").lower())
                print(script_env)
                f.write('\n')
                f.write(f"# {k} ENV" + '\n')
                f.write(script_env + '\n')

    ''' export file'''
    ''' output 
    # dev ENV
    python ./standalone-es-service-export.py --interface http --db_http_host tsgvm00875:8002 --url jdbc:oracle:thin:bi"$"reporting/None --db_run false --kafka_url data1:9092,data2:9092,data3:9092 --kafka_connect_url data1:8083,data2:8083,data3:8083 --zookeeper_url  data1:2181,data2:2181,data3:2181 --es_url es1:9200,es2:9200,es3:9200,es4:9200 --kibana_url kibana:5601 --interval 30 --sql "SELECT processname, status, MAX (CAST (addts AS DATE)) as addts, COUNT (*), get_db_name as dbid FROM es_pipeline_processed a WHERE addts >= TRUNC (SYSTIMESTAMP) AND status IN ('E', 'C') GROUP BY processname, status ORDER BY 3 DESC"

    # localhost ENV
    python ./standalone-es-service-export.py --interface http --db_http_host tsgvm00875:8002 --url jdbc:oracle:thin:bi"$"reporting/None --db_run false --kafka_url data11:9092,data21:9092,data31:9092 --kafka_connect_url data11:8083,data21:8083,data31:8083 --zookeeper_url  data11:2181,data21:2181,data31:2181 --es_url es11:9200,es21:9200,es31:9200,es41:9200,es51:9200 --kibana_url kibana1:5601 --interval 30 --sql "SELECT processname, status, MAX (CAST (addts AS DATE)) as addts, COUNT (*), get_db_name as dbid FROM es_pipeline_processed a WHERE addts >= TRUNC (SYSTIMESTAMP) AND status IN ('E', 'C') GROUP BY processname, status ORDER BY 3 DESC"
    '''
    export_file(hosts_dicts)
                



# read host file to make an dict in memory
def read_hosts(server_file):
    ''' transform to json format for the host'''
    ''' 
     {
        "dev": [
            {
            "Elastic - LogStash": "Elastic - LogStash",
            "logstash": "logstash"
            },
            {
            "Elastic - Kibana": "Elastic - Kibana",
            "kibana": "kibana"
            },
            {
            "Elastic - Data Nodes*": "Elastic - Data Nodes*",
            "es1": "es1"
            },
            {
            "Elastic - Data Nodes": "Elastic - Data Nodes",
            "es2": "es2"
            },
            {
            "Elastic - Data Nodes": "Elastic - Data Nodes",
            "es3": "es3"
            },
            {
            "Elastic - Data Nodes": "Elastic - Data Nodes",
            "es4": "es4"
            },
            {
            "Data Transfer (Kafka, Spark, ZK)  (Kafka, Spark, ZK)  VMs *": "Data Transfer (Kafka, Spark, ZK)  (Kafka, Spark, ZK)  VMs *",
            "data1": "data1"
            },
            {
            "Data Transfer (Kafka, Spark, ZK)  VMs": "Data Transfer (Kafka, Spark, ZK)  VMs",
            "data2": "data2"
            },
            {
            "Data Transfer (Kafka, Spark, ZK)  VMs": "Data Transfer (Kafka, Spark, ZK)  VMs",
            "data3": "data3"
            }
        ],
        ..
    }

    '''
    hosts_dicts = {}
    with open(server_file) as data_file:
        name_of_environment = ''
        for line in data_file:
            if '#' in line:
                continue
            line = line.strip().split("|")
            # print(f"{line}")

            name_of_environment = line[0]

            sub_hosts_dicts = {line[i-1] : line[i] for i in range(2, len(line))}

            if name_of_environment not in hosts_dicts.keys():
                hosts_dicts.update({name_of_environment : [sub_hosts_dicts]})
            else:
                hosts_dicts[name_of_environment].append(sub_hosts_dicts)
    
        # logging.info(json.dumps(hosts_dicts, indent=2))            
            
    return hosts_dicts


if __name__ == '__main__':

    ''' read hosts file and transform to json format'''
    hosts_dicts = read_hosts("./hosts")
    ''' generate arguments for shell script arguments for ./standalone-export-run.sh'''

    ''' results
    # dev ENV
    python ./standalone-es-service-export.py --interface http --db_http_host tsgvm00875:8002 --url jdbc:oracle:thin:bi"$"reporting/None --db_run false --kafka_url data1:9092,data2:9092,data3:9092 --kafka_connect_url data1:8083,data2:8083,data3:8083 --zookeeper_url  data1:2181,data2:2181,data3:2181 --es_url es1:9200,es2:9200,es3:9200,es4:9200 --kibana_url kibana:5601 --interval 30 --sql "SELECT * FROM TEST"

    # localhost ENV
    python ./standalone-es-service-export.py --interface http --db_http_host tsgvm00875:8002 --url jdbc:oracle:thin:bi"$"reporting/None --db_run false --kafka_url data11:9092,data21:9092,data31:9092 --kafka_connect_url data11:8083,data21:8083,data31:8083 --zookeeper_url  data11:2181,data21:2181,data31:2181 --es_url es11:9200,es21:9200,es31:9200,es41:9200,es51:9200 --kibana_url kibana1:5601 --interval 30 --sql "SELECT * FROM TEST"

    '''
    transform_json_to_each_arguments(hosts_dicts)