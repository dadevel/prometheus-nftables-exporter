# Prometheus Nftables Exporter

A Prometheus Exporter that exposes metrics from [nftables](https://nftables.org/projects/nftables/index.html).

## Setup

Just start the docker container.
The container needs the `net_admin` capability and must be part of the host network namespace in order to collect data from nftables.

~~~ bash
docker run -d -p 9639 --cap-drop all --cap-add net_admin --network host dadevel/prometheus-nftables-exporter
~~~

And test it.

~~~ bash
curl http://localhost:9630/metrics
~~~

## Configure

| Environment variable              | Description                                                    |
|-----------------------------------|----------------------------------------------------------------|
| `NFTABLES_EXPORTER_ADDRESS`       | listen address, listening on all network interfaces by default |
| `NFTABLES_EXPORTER_PORT`          | listen port, defaults to `9639`                                |
| `NFTABLES_EXPORTER_UPDATE_PERIOD` | update interval in seconds, defaults to `60`                   |

## Example

Firewall ruleset:

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

~~~ bash
DOCKER_BUILDKIT=1 docker build -t dadevel/prometheus-nftables-exporter .
~~~

