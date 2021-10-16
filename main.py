#!/usr/bin/env python3
from collections import defaultdict
from pathlib import Path

import hashlib
import json
import logging
import os
import prometheus_client
import subprocess
import tarfile
import time
import urllib.request, urllib.error

log = logging.getLogger('nftables-exporter')

try:
    logging.basicConfig(level=os.environ.get('NFTABLES_EXPORTER_LOG_LEVEL', 'INFO').upper())
    ADDRESS = os.environ.get('NFTABLES_EXPORTER_ADDRESS', '')
    PORT = int(os.environ.get('NFTABLES_EXPORTER_PORT', 9630))
    UPDATE_PERIOD = int(os.environ.get('NFTABLES_EXPORTER_UPDATE_PERIOD', 60))
    NAMESPACE = os.environ.get('NFTABLES_EXPORTER_NAMESPACE', 'nftables')
    MAXMIND_LICENSE_KEY = os.environ.get('MAXMIND_LICENSE_KEY')
    MAXMIND_DATABASE_EDITION = os.environ.get('MAXMIND_DATABASE_EDITION', 'GeoLite2-Country')
    MAXMIND_CACHE_DIRECTORY = Path(os.environ.get('MAXMIND_CACHE_DIRECTORY', './data/')).expanduser()
except Exception as e:
    raise RuntimeError('one or more environment variables are invalid') from e

if MAXMIND_LICENSE_KEY and MAXMIND_DATABASE_EDITION:
    import maxminddb


def main():
    """The main entry point."""
    metrics = get_prometheus_metrics()
    prometheus_client.start_http_server(addr=ADDRESS, port=PORT)
    log.info(f'listing on {ADDRESS}:{PORT}')
    if MAXMIND_LICENSE_KEY and MAXMIND_DATABASE_EDITION:
        log.info('geoip lookup enabled')
        database_path = prepare_maxmind_database(MAXMIND_LICENSE_KEY, MAXMIND_DATABASE_EDITION, MAXMIND_CACHE_DIRECTORY)
        with maxminddb.open_database(database_path.as_posix()) as database:
            collect_metrics(*metrics, geoip_db=database)
    else:
        log.info('geoip lookup disabled')
        collect_metrics(*metrics)


def get_prometheus_metrics():
    """Returns all prometheus metric objects."""
    return (
        DictGauge(
            'chains',
            'Number of chains in nftables ruleset',
            namespace=NAMESPACE,
        ),
        DictGauge(
            'rules',
            'Number of rules in nftables ruleset',
            namespace=NAMESPACE,
        ),
        DictCounter(
            'counter_bytes',
            'Byte value of named nftables counters',
            labelnames=('family', 'table', 'name'),
            namespace=NAMESPACE,
            unit='bytes'
        ),
        DictCounter(
            'counter_packets',
            'Packet value of named nftables counters',
            labelnames=('family', 'table', 'name'),
            namespace=NAMESPACE,
            unit='packets'
        ),
        DictGauge(
            'map_elements',
            'Element count of named nftables maps',
            labelnames=('family', 'table', 'name', 'type', 'country'),
            namespace=NAMESPACE,
        ),
        DictGauge(
            'meter_elements',
            'Element count of named nftables meters',
            labelnames=('family', 'table', 'name', 'type', 'country'),
            namespace=NAMESPACE,
        ),
        DictGauge(
            'set_elements',
            'Element count of named nftables sets',
            labelnames=('family', 'table', 'name', 'type', 'country'),
            namespace=NAMESPACE,
        ),
    )


def collect_metrics(chains, rules, counter_bytes, counter_packets, map_elements, meter_elements, set_elements, geoip_db=None):
    """Loops forever and periodically fetches data from nftables to update prometheus metrics."""
    log.info('startup complete')
    while True:
        log.debug('collecting metrics')
        rules.set(len(fetch_nftables('ruleset', 'rule')))
        chains.set(len(fetch_nftables('ruleset', 'chain')))
        for item in fetch_nftables('counters', 'counter'):
            counter_bytes.labels(item).set(item.get('bytes', 0))
            counter_packets.labels(item).set(item.get('packets', 0))
        map_elements.reset()
        for item in fetch_nftables('maps', 'map'):
            for labels, value in annotate_elements_with_country(item, geoip_db):
                map_elements.labels(labels).set(value)
        meter_elements.reset()
        for item in fetch_nftables('meters', 'meter'):
            for labels, value in annotate_elements_with_country(item, geoip_db):
                meter_elements.labels(labels).set(value)
        set_elements.reset()
        for item in fetch_nftables('sets', 'set'):
            for labels, value in annotate_elements_with_country(item, geoip_db):
                set_elements.labels(labels).set(value)
        time.sleep(UPDATE_PERIOD)


def fetch_nftables(query_name, type_name):
    """Uses nft command line tool to fetch objects from nftables."""
    log.debug(f'fetching nftables {query_name}')
    process = subprocess.run(
        ('nft', '--json', 'list', query_name),
        capture_output=True,
        check=True,
        text=True,
    )
    data = json.loads(process.stdout)
    version = data['nftables'][0]['metainfo']['json_schema_version']
    if version != 1:
        raise RuntimeError(f'nftables json schema v{version} is not supported')
    return [
        item[type_name]
        for item in data['nftables'][1:]
        if type_name in item
    ]


def annotate_elements_with_country(item, geoip_db):
    """Takes a nftables map, meter or set object and adds country code information to each ip address element."""
    elements = item.get('elem', ())
    if geoip_db and item.get('type') in ('ipv4_addr', 'ipv6_addr'):
        result = defaultdict(int)
        for element in elements:
            if isinstance(element, str):
                country = lookup_ip_country(element, geoip_db)
            elif isinstance(element, dict):
                country = lookup_ip_country(element['elem']['val'], geoip_db)
            else:
                raise TypeError(f'got element of unexpected type {element.__class__.__name__}')
            result[country] += 1
        for country, value in result.items():
            yield dict(item, country=country), value
    else:
        yield dict(item, country=''), len(elements)


def lookup_ip_country(address, database):
    """Returns the country code for a given ip address."""
    info = database.get(address)
    try:
        return info['country']['iso_code']
    except Exception:
        return ''


def retry(n=2, exceptions=Exception):
    """A function decorator that executes the wrapped function up to n + 1 times if it throws an exception."""
    def decorator(callback):
        def wrapper(*args, **kwargs):
            for _ in range(n):
                try:
                    return callback(*args, **kwargs)
                except exceptions as e:
                    logging.warning(f'retrying function {callback.__name__} because it raised {e.__class__.__name__}: {e}')
                    pass
            return callback(*args, **kwargs)

        return wrapper

    return decorator


def prepare_maxmind_database(license_key, database_edition, storage_dir):
    """Downloads, extracts and caches a maxmind geoip database for offline use."""
    checksum = download_maxmind_database_checksum(license_key, database_edition)
    archive_path = download_maxmind_database_archive(license_key, database_edition, storage_dir, checksum)
    database_path = extract_maxmind_database_archive(database_edition, storage_dir, archive_path)
    return database_path


@retry(exceptions=urllib.error.URLError)
def download_maxmind_database_checksum(license_key, database_edition):
    """Fetches the sha256 checksum for a maxmind database."""
    checksum_url = f'https://download.maxmind.com/app/geoip_download?edition_id={database_edition}&license_key={license_key}&suffix=tar.gz.sha256'
    with urllib.request.urlopen(checksum_url) as response:
        words = response.readline().split(maxsplit=1)
        checksum = words[0].decode()
    log.debug(f'database checksum {checksum}')
    return checksum


@retry(exceptions=(urllib.error.URLError, RuntimeError))
def download_maxmind_database_archive(license_key, database_edition, storage_dir, checksum):
    """Downloads a maxmind database archive and validates its checksum."""
    archive_path = storage_dir/f'{database_edition}.tar.gz'
    if not archive_path.exists() or not verify_file_checksum(archive_path, checksum):
        log.info('downloading maxmind geoip database')
        database_url = f'https://download.maxmind.com/app/geoip_download?edition_id={database_edition}&license_key={license_key}&suffix=tar.gz'
        urllib.request.urlretrieve(database_url, filename=archive_path)
    if not verify_file_checksum(archive_path, checksum):
        raise RuntimeError('maxmind database checksum verification failed')
    return archive_path


def extract_maxmind_database_archive(database_edition, storage_dir, archive_path):
    """Unpacks a maxmind database archive."""
    storage_dir.mkdir(exist_ok=True)
    with tarfile.open(archive_path, 'r') as archive:
        archive.extractall(storage_dir)
    database_path = last(storage_dir.glob(f'{database_edition}_*/{database_edition}.mmdb'))
    log.info(f'maxmind database stored at {database_path}')
    return database_path


def verify_file_checksum(path, expected_checksum):
    """Verifies the sha256 checksum of a file."""
    actual_checksum = calculate_file_checksum(path)
    return actual_checksum == expected_checksum


def calculate_file_checksum(path):
    """Calculates the sha256 checksum of a file."""
    # thanks to https://stackoverflow.com/a/3431838
    checksum = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def last(iterable):
    """Returns the last element of an iterable."""
    it = iter(iterable)
    try:
        while True:
            result = next(it)
    except StopIteration:
        return result


def _filter_labels(data, labelnames):
    return {
        key: value
        for key, value in data.items()
        if key in labelnames
    }


def _reset_labels(self):
    for metric in self.collect():
        for sample in metric.samples:
            self.labels(sample.labels).set(0)


class DictGauge(prometheus_client.Gauge):
    """Subclass of prometheus_client.Gauge with automatic label filtering."""
    def labels(self, data):
        return super().labels(**_filter_labels(data, self._labelnames))

    def reset(self):
        _reset_labels(self)


class DictCounter(prometheus_client.Counter):
    def labels(self, data):
        filtered_data = {
            key: value
            for key, value in data.items()
            if key in self._labelnames
        }
        return super().labels(**filtered_data)

    def set(self, data):
        self._value.set(data)

    def reset(self):
        _reset_labels(self)


if __name__ == '__main__':
    main()
