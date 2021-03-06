from __future__ import print_function
import pytest

import re
import requests

from helpers.cluster import ClickHouseCluster

cluster = ClickHouseCluster(__file__)
node = cluster.add_instance('node', main_configs=['configs/prom_conf.xml'])

@pytest.fixture(scope="module")
def start_cluster():
    try:
        cluster.start()
        yield cluster
    finally:
        cluster.shutdown()


def parse_response_line(line):
    allowed_prefixes = [
        "ClickHouse",
        "# HELP",
        "# TYPE",
    ]
    assert any(line.startswith(prefix) for prefix in allowed_prefixes), msg

    if line.startswith("#"):
        return {}
    match = re.match('^([a-zA-Z_:][a-zA-Z0-9_:]+)(\{.*\})? (\d)', line)
    assert match, line
    name, _, val = match.groups()
    return {name: int(val)}


def get_and_check_metrics():
    response = requests.get("http://{host}:{port}/metrics".format(
        host=node.ip_address, port=8001), allow_redirects=False)

    if response.status_code != 200:
        response.raise_for_status()

    assert response.headers['content-type'].startswith('text/plain')

    results = {}
    for resp_line in response.text.split('\n'):
        resp_line = resp_line.rstrip()
        if not resp_line:
            continue
        res = parse_response_line(resp_line)
        results.update(res)
    return results


def test_prometheus_endpoint(start_cluster):

    metrics_dict = get_and_check_metrics()
    assert metrics_dict['ClickHouseProfileEventsQuery'] >= 0
    prev_query_count = metrics_dict['ClickHouseProfileEventsQuery']

    resp = node.query("SELECT 1")
    resp = node.query("SELECT 2")
    resp = node.query("SELECT 3")

    metrics_dict = get_and_check_metrics()
    assert metrics_dict['ClickHouseProfileEventsQuery'] >= prev_query_count + 3
