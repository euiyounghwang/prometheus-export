# ELK Upgrade with Search Guard
<i>ELK Upgrade with Search Guard

General

The first time installation procedure on a production cluster is to:

1) Disable shard allocation
- Cluster Reboot

```bash
GET _cat/indices
GET _cluster/stats?human&pretty

# Set shard allocation to stop
PUT _cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.enable": "none"
  }
}

POST _flush/synced

```
2) Stop all nodes

3) Install the Search Guard plugin on all nodes
- Search Guard License : https://search-guard.com/licensing/
- Search Guard : https://docs.search-guard.com/latest/search-guard-versions

```bash
- Elasticsearch Plugin for Search Guard

$ ./bin/elasticsearch-plugin install -b file:////apps/elasticsearch/node1/elasticsearch-8.12.2/search-guard-flx-elasticsearch-plugin-2.0.0-es-8.12.2.zip

[devuser@localhost elasticsearch-8.12.2]$ ./bin/elasticsearch-plugin install -b file:////apps/elasticsearch/node1/elasticsearch-8.12.2/search-guard-flx-elasticsearch-plugin-2.0.0-es-8.12.2.zip
-> Installing file:////apps/elasticsearch/node1/elasticsearch-8.12.2/search-guard-flx-elasticsearch-plugin-2.0.0-es-8.12.2.zip
-> Downloading file:////apps/elasticsearch/node1/elasticsearch-8.12.2/search-guard-flx-elasticsearch-plugin-2.0.0-es-8.12.2.zip
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@     WARNING: plugin requires additional permissions     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
* java.lang.RuntimePermission accessClassInPackage.com.sun.jndi.*
* java.lang.RuntimePermission accessClassInPackage.sun.misc
* java.lang.RuntimePermission accessClassInPackage.sun.nio.ch
* java.lang.RuntimePermission accessClassInPackage.sun.security.x509
* java.lang.RuntimePermission accessDeclaredMembers
* java.lang.RuntimePermission getClassLoader
* java.lang.RuntimePermission loadLibrary.*
* java.lang.RuntimePermission setContextClassLoader
* java.lang.reflect.ReflectPermission suppressAccessChecks
* java.net.NetPermission getProxySelector
* java.net.SocketPermission * connect,accept,resolve
* java.security.SecurityPermission insertProvider
* java.security.SecurityPermission org.apache.xml.security.register
* java.security.SecurityPermission putProviderProperty.BC
* java.util.PropertyPermission * read,write
* java.util.PropertyPermission org.apache.xml.security.ignoreLineBreaks write
* javax.security.auth.AuthPermission doAs
* javax.security.auth.AuthPermission modifyPrivateCredentials
* javax.security.auth.kerberos.ServicePermission * accept
See https://docs.oracle.com/javase/8/docs/technotes/guides/security/permissions.html
for descriptions of what these permissions allow and the associated risks.
-> Installed search-guard-flx
-> Please restart Elasticsearch to activate any plugins installed
[devuser@localhost elasticsearch-8.12.2]$


- Change chmod to run *.sh
[devuser@localhost tools]$ pwd
/apps/elasticsearch/node1/elasticsearch-8.12.2/plugins/search-guard-flx/tools
[devuser@localhost tools]$ ls
install_demo_configuration.sh
[devuser@localhost tools]$ chmod 755 *.sh

devuser@localhost tools]$ ./install_demo_configuration.sh
Search Guard Demo Installer
 ** Warning: Do not use on production or public reachable systems **
Initialize Search Guard? [y/N] y
Cluster mode requires maybe additional setup of:
  - Virtual memory (vm.max_map_count)
    See https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html

Enable cluster mode? [y/N] n
Basedir: /apps/elasticsearch/node1/elasticsearch-8.12.2
Elasticsearch install type: .tar.gz on NAME="Red Hat Enterprise Linux Server"
Elasticsearch config dir: /apps/elasticsearch/node1/elasticsearch-8.12.2/config
Elasticsearch config file: /apps/elasticsearch/node1/elasticsearch-8.12.2/config/elasticsearch.yml
Elasticsearch bin dir: /apps/elasticsearch/node1/elasticsearch-8.12.2/bin
Elasticsearch plugins dir: /apps/elasticsearch/node1/elasticsearch-8.12.2/plugins
Elasticsearch lib dir: /apps/elasticsearch/node1/elasticsearch-8.12.2/lib
/apps/elasticsearch/node1/elasticsearch-8.12.2/config/elasticsearch.yml seems to be already configured for Search Guard. Quit.
[devuser@localhost tools]$

```

4) Change "elasticsearch.yml" for Search Guard Configuration
```bash

- Created certification automatically
-rw-rw-r--  1 localhost localhost  1704 Jun 21 15:52 esnode-key.pem
-rw-rw-r--  1 localhost localhost  1720 Jun 21 15:52 esnode.pem
..
-rw-rw-r--  1 localhost localhost  1704 Jun 21 15:52 kirk-key.pem
-rw-rw-r--  1 localhost localhost  1610 Jun 21 15:52 kirk.pem
..
-rw-rw-r--  1 localhost localhost  1444 Jun 21 15:52 root-ca.pem


- elasticsearch.yml

# --------------------------------- Discovery ----------------------------------
#
# Pass an initial list of hosts to perform discovery when this node is started:
# The default list of hosts is ["127.0.0.1", "[::1]"]
#
discovery.seed_hosts: ["192.168.79.107", "192.168.79.108"]
#
# Bootstrap the cluster using an initial set of master-eligible nodes:
#
cluster.initial_master_nodes: ["192.168.79.107"]
#
# For more information, consult the discovery and cluster formation module docum
entation.


######## Start Search Guard Demo Configuration ########
# WARNING: revise all the lines below before you go into production
searchguard.ssl.transport.pemcert_filepath: esnode.pem
searchguard.ssl.transport.pemkey_filepath: esnode-key.pem
searchguard.ssl.transport.pemtrustedcas_filepath: root-ca.pem
searchguard.ssl.transport.enforce_hostname_verification: false
searchguard.ssl.http.enabled: false
searchguard.ssl.http.pemcert_filepath: esnode.pem
searchguard.ssl.http.pemkey_filepath: esnode-key.pem
searchguard.ssl.http.pemtrustedcas_filepath: root-ca.pem
searchguard.allow_unsafe_democertificates: true
searchguard.allow_default_init_sgindex: true
searchguard.authcz.admin_dn:
  - CN=kirk,OU=client,O=client,L=test, C=de

searchguard.audit.type: internal_elasticsearch
searchguard.enable_snapshot_restore_privilege: true
searchguard.check_snapshot_restore_write_privileges: true
searchguard.restapi.roles_enabled: ["SGS_ALL_ACCESS"]
cluster.routing.allocation.disk.threshold_enabled: false
node.max_local_storage_nodes: 3

xpack.security.enabled: false
searchguard.enterprise_modules_enabled: false
indices.breaker.total.use_real_memory: false

######## End Search Guard Demo Configuration ########
```

5) Restart Elasticsearch and check that the nodes come up
- Test connection : https://localhost:9200
```bash
[localhost@localhost sgconfig]$ pwd
/apps/elasticsearch/node1/elasticsearch-8.12.2/plugins/search-guard-flx/sgconfig
[localhost@localhost sgconfig]$ ls
elasticsearch.yml.example  sg_action_groups.yml  sg_authc.yml  sg_authz.yml  sg_frontend_authc.yml  sg_frontend_multi_tenancy.yml  sg_internal_users.yml  sg_roles_mapping.yml  sg_roles.yml  sg_tenants.yml
```
- Account Maintain : Add user to "/plugins/search-guard-flx/sgconfig/sg_internal_user.xml" (Use API : https://docs.search-guard.com/7.x-51/rest-api-internalusers, Base64 : https://www.encodebase64.net/, PlainText : <user>:<password>)
```bash
elastic:
  hash: "$2y$12$ScV8euAglZETM/H1xTuQkOP36raAW7ylOw/pVpF10QKja3RSW2aYu=-="
  reserved: false
  backend_roles:
  - "admin"
  description: "common admin"


# User Test
http://localhost:9200/_searchguard/api/internalusers/admin  (Header : 'Authorization' : 'Basic YWRtaW46YWRtaW4=')


-bash-4.2$  curl -XGET -u test:test https://localhost:9260
{
  "name" : "test-node-1",
  "cluster_name" : "test-upgrade",
  "cluster_uuid" : "8Jew6_HCSVa1A7KHL2GOlQ",
  "version" : {
    "number" : "8.12.2",
    "build_flavor" : "default",
    "build_type" : "tar",
    "build_hash" : "48a287ab9497e852de30327444b0809e55d46466",
    "build_date" : "2024-02-19T10:04:32.774273190Z",
    "build_snapshot" : false,
    "lucene_version" : "9.9.2",
    "minimum_wire_compatibility_version" : "7.17.0",
    "minimum_index_compatibility_version" : "7.0.0"
  },
  "tagline" : "You Know, for Search"
}
-bash-4.2$


# Get all users from search guard
-bash-4.2$  curl -XGET -u test:test https://localhost:9260/_searchguard/api/internalusers/ | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   582  100   582    0     0   3287      0 --:--:-- --:--:-- --:--:--  3306
{
  "logstash": {
    "backend_roles": [
      "logstash"
    ],
    "description": "Demo logstash user"
  },
  "snapshotrestore": {
    "backend_roles": [
      "snapshotrestore"
    ],
    "description": "Demo snapshotrestore user"
  },
  "admin": {
    "backend_roles": [
      "admin"
    ],
    "description": "Demo admin user"
  },
  "kibanaserver": {
    "description": "Demo kibanaserver user"
  },
  "kibanaro": {
    "backend_roles": [
      "kibanauser",
      "readall"
    ],
    "attributes": {
      "attribute1": "value1",
      "attribute2": "value2",
      "attribute3": "value3"
    },
    "description": "Demo kibanaro user"
  },
  "biadmin": {
    "backend_roles": [
      "admin"
    ]
  },
  "readall": {
    "backend_roles": [
      "readall"
    ],
    "description": "Demo readall user"
  }
}
-bash-4.2$


curl -X 'PATCH' \
  'https://localhost:9260/_searchguard/api/internalusers' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Basic test=' \
  -d '[ 
  { 
    "op": "add", "path": "/test", "value": { "password": "test", "backend_roles": ["admin"] } 
  }
]' | jq

```


6) Re-enable shard allocation by using sgadmin
```bash
PUT _cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.enable": "all"
  }
}
```

7) Configure authentication/authorization, users, roles and permissions by uploading the Search Guard configuration with sgadmin
```bash

- Change the files in ../sgconfig and execute: 
"/home/biadmin/ELK_UPGRADE/search-guard-hash/tools/sgadmin.sh" -cd "/ES/search_guard/elasticsearch-7.9.0/plugins/search-guard-7/sgconfig" -icl -key "/ES/search_guard/elasticsearch-7.9.0/config/kirk-key.pem" -cert "/ES/search_guard/elasticsearch-7.9.0/config/kirk.pem" -cacert "/ES/search_guard/elasticsearch-7.9.0/config/root-ca.pem" -nhnv
```

8) Install Kibana
```bash
##Kibaba (kibana plugin install 없이 http 기동하게 되면 messaage box for login)
# https://docs.search-guard.com/latest/search-guard-versions

Plugin installation was unsuccessful due to error "No kibana plugins found in archive"
[devuser@gsa02 kibana-7.9.0-linux-x86_64]$ ./bin/kibana-plugin install file:////apps/kibana/kibana-8.12.2/search-guard-flx-kibana-plugin-2.0.0-es-8.12.2.zip
Kibana is currently running with legacy OpenSSL providers enabled! For details and instructions on how to disable see https://www.elastic.co/guide/en/kibana/8.12/production.html#openssl-legacy-provider
Attempting to transfer from file:////apps/kibana/kibana-8.12.2/search-guard-flx-kibana-plugin-2.0.0-es-8.12.2.zip
Transferring 9423509 bytes....................
Transfer complete
Retrieving metadata from plugin archive
Extracting plugin archive
Extraction complete
Plugin installation complete
[devuser@gsa02 kibana-7.9.0-linux-x86_64]$ 


# is proxied through the Kibana server.
elasticsearch.username: "elastic"
elasticsearch.password: "gsaadmin"


elasticsearch.ssl.verificationMode: none
elasticsearch.requestHeadersWhitelist: ["Authorization", "sgtenant"]

# - LOGO (/apps/kibana/kibana-8.12.2/plugins/searchguard/public/assets)


/home/ES/kibana-7.9.0-linux-x86_64/plugins/searchguard/public/apps/loginlogin.html
```


9) Logstash Configuration
- Logstash Reference :https://princehood69.rssing.com/chan-69503895/article83.html
```bash
input {
  stdin {}
}
output {
  elasticsearch {
    hosts => "localhost:9200"
    user => logstash
    password => logstash
    ssl => true
    ssl_certificate_verification => false
    truststore => "<logstash path>/config/truststore.jks"
    truststore_password => changeit
    index => "test"
    document_type => "test_doc"
  }
  stdout{
    codec => rubydebug
  }
}
```
