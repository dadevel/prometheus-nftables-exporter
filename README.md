# Prometheus Nftables Exporter

A Prometheus Exporter that exposes metrics from [nftables](https://nftables.org/projects/nftables/index.html).

![Example Grafana Dashboard Screenshot](./images/grafana.png)

## Setup

Just start the docker container.
It requires the `net_admin` capability and must be part of the host network namespace in order to collect data from nftables.

~~~ bash
docker run -d -p 9639 --cap-drop all --cap-add net_admin --network host ghcr.io/dadevel/nftables-exporter
~~~

And test it.

~~~ bash
curl http://localhost:9630/metrics
~~~

nftables-exporter can annotate ip addresses in nftables maps, meters and sets with a country code.
You can use this for example with the [Grafana Worldmap Panel](https://github.com/grafana/worldmap-panel).
Unfortunately you have provide a (free) MaxMind license key.
See [here](https://dev.maxmind.com/geoip/geoip2/geolite2/) for more information.

~~~ bash
docker run -d -p 9639 --cap-drop all --cap-add net_admin --network host -e MAXMIND_LICENSE_KEY=INSERT_YOUR_KEY_HERE ghcr.io/dadevel/nftables-exporter
~~~

## Configure

| Environment variable              | Description                                                             |
|-----------------------------------|-------------------------------------------------------------------------|
| `NFTABLES_EXPORTER_ADDRESS`       | listen address, listening on all network interfaces by default          |
| `NFTABLES_EXPORTER_PORT`          | listen port, defaults to `9639`                                         |
| `NFTABLES_EXPORTER_UPDATE_PERIOD` | update interval in seconds, defaults to `60`                            |
| `NFTABLES_EXPORTER_LOG_LEVEL`     | one of the log levels from pythons `logging` module, defaults to `info` |
| `MAXMIND_LICENSE_KEY`             | license key for maxmind geoip database, optional                        |
| `MAXMIND_DATABASE_EDITION`        | maxmind database edition, defaults to `GeoLite2-Country`                |
| `MAXMIND_CACHE_DIRECTORY`         | directory to store maxmind database in, defaults to `./data`            |

## Example

Firewall ruleset:

~~~ nft
table inet filter {
  counter http-allowed {
  }

  counter http-denied {
  }

  chain input {
    type filter hook input priority 0
    policy drop
    tcp dport { 80, 443 } meter http-limit { ip saddr limit rate over 16 mbytes/second } counter name http-denied drop
    tcp dport { 80, 443 } meter http6-limit { ip6 saddr limit rate over 16 mbytes/second } counter name http-denied drop
    tcp dport { 80, 443 } counter name http-allowed accept
  }
}
~~~

Resulting metrics:

~~~ prom
nftables_counter_bytes{family="inet", name="http-allowed", table="filter"} 90576
nftables_counter_packets{family="inet", name="http-allowed", table="filter"} 783
nftables_counter_bytes{family="inet", name="http-denied", table="filter"} 936
nftables_counter_packets{family="inet", name="http-denied", table="filter"} 13
nftables_meter_elements{family="ip", name="http-limit", table="filter", type="ipv4_addr", country="US"} 7
nftables_meter_elements{family="ip", name="http-limit", table="filter", type="ipv4_addr", country="DE"} 3
nftables_meter_elements{family="ip", name="http-limit", table="filter", type="ipv4_addr", country=""} 2
nftables_meter_elements{family="ip6", name="http6-limit", table="filter", type="ipv6_addr", country="US"} 2
~~~

## Build

Install the dependencies and run the python script.

~~~ bash
pip3 install -r ./requirements.txt
python3 ./main.py
~~~

The `Dockerfile` is available under [github.com/dadevel/dockerfiles](https://github.com/dadevel/dockerfiles/tree/main/nftables-exporter).
