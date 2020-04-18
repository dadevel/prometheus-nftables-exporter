#!/usr/bin/env python3
import json
import os
import prometheus_client
import subprocess
import sys
import time


class DictGauge(prometheus_client.Gauge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def labels(self, data):
        filtered_data = {
            key: value
            for key, value in data.items()
            if key in self._labelnames
        }
        return super().labels(**filtered_data)


def main(args):
    try:
        address = str(os.environ.get('ADDRESS', ''))
        port = int(os.environ.get('PORT', '9876'))
        update_period = int(os.environ.get('UPDATE_PERIOD', '60'))
    except ValueError:
        raise RuntimeError("At least one of the environment variables ADDRESS, PORT or UPDATE_PERIOD are set to an invalid value.")

    namespace = 'nftables'
    labels = {'family', 'table', 'name', 'type'}

    counter_bytes_gauge = DictGauge(
        'counter_bytes',
        'Byte value of named nftables counters',
        labelnames=labels,
        namespace=namespace,
        unit='bytes'
    )
    counter_packets_gauge = DictGauge(
        'counter_packets',
        'Packet value of named nftables counters',
        labelnames=labels,
        namespace=namespace,
        unit='packets'
    )
    map_elements_gauge = DictGauge(
        'map_elements',
        'Element count of named nftables maps',
        labelnames=labels,
        namespace=namespace,
    )
    meter_elements_gauge = DictGauge(
        'meter_elements',
        'Element count of named nftables meters',
        labelnames=labels,
        namespace=namespace,
    )
    set_elements_gauge = DictGauge(
        'set_elements',
        'Element count of named nftables sets',
        labelnames=labels,
        namespace=namespace,
    )

    prometheus_client.start_http_server(addr=address, port=port)

    while True:
        for item in fetch_nftables('counters', 'counter'):
            counter_bytes_gauge.labels(item).set(item.get('bytes', 0))
            counter_packets_gauge.labels(item).set(item.get('packets', 0))
        for item in fetch_nftables('maps', 'map'):
            map_elements_gauge.labels(item).set(len(item.get('elem', ())))
        for item in fetch_nftables('meters', 'meter'):
            meter_elements_gauge.labels(item).set(len(item.get('elem', ())))
        for item in fetch_nftables('sets', 'set'):
            set_elements_gauge.labels(item).set(len(item.get('elem', ())))
        time.sleep(update_period)


def fetch_nftables(query_name: str, type_name: str) -> list:
    process = subprocess.run(
        ['nft', '--json', 'list', query_name],
        capture_output=True,
        check=True,
        text=True,
    )
    data = json.loads(process.stdout)
    version = data['nftables'][0]['metainfo']['json_schema_version']
    if version != 1:
        raise RuntimeError(f'json schema v{version} is not supported')
    return [
        item[type_name]
        for item in data['nftables'][1:]
        if type_name in item
    ]


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

