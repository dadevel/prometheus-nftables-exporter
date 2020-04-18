# Prometheus Nftables Exporter [![CI](https://github.com/dadevel/prometheus-nftables-exporter/workflows/CI/badge.svg?branch=master)](https://github.com/dadevel/prometheus-nftables-exporter/actions)

A Prometheus Exporter that exposes metrics from [Nftables](https://nftables.org/projects/nftables/index.html).

## Setup

Just start the docker container.
The container needs the `CAP_NET_ADMIN` capability and must be part of the host network namespace in order to get data from Nftables.

~~~ sh
docker run -d --cap-add net_admin --network host dadevel/prometheus-nftables-exporter
~~~

And test it.

~~~ sh
curl http://localhost:9876/metrics
~~~

## Metrics

Example Nftables ruleset:

~~~ nft
table ip filter {
  counter http-allowed {
  }

  counter http-denied {
  }

  chain input {
    type filter hook input priority 0
    policy drop
    tcp dport { 80, 443 } meter http-limit { ip saddr limit rate over 16 mbytes/second } counter name http-denied drop
    tcp dport { 80, 443 } counter name http-allowed accept
  }
}
~~~

Resulting metrics:

~~~ prom
nftables_counter_bytes{family="ip", name="http-allowed", table="filter"} 90576
nftables_counter_packets{family="ip", name="http-allowed", table="filter"} 783
nftables_counter_bytes{family="ip", name="http-denied", table="filter"} 936
nftables_counter_packets{family="ip", name="http-denied", table="filter"} 13
nftables_meter_elements{family="ip", name="http-limit", table="filter", type="ipv4_addr"} 3
~~~

## Build

~~~ sh
docker build -t dadevel/prometheus-nftables-exporter .
~~~

