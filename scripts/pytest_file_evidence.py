"""Private pytest evidence keyed by collected item paths, never module names."""
import json
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption('--ludo-file-evidence', required=True)


def pytest_configure(config):
    config._ludo_file_counts = {}


def pytest_collection_modifyitems(session, config, items):
    for item in items:
        path = str(item.path.resolve())
        counts = config._ludo_file_counts.setdefault(path, {'collected': 0, 'executed': 0})
        counts['collected'] += 1


def pytest_runtest_makereport(item, call):
    if call.when == 'call':
        item.config._ludo_file_counts[str(item.path.resolve())]['executed'] += 1


def pytest_sessionfinish(session, exitstatus):
    destination = Path(session.config.getoption('--ludo-file-evidence'))
    destination.write_text(json.dumps(session.config._ludo_file_counts), encoding='utf-8')
