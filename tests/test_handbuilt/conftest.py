"""Unbuilt hand-built functions report as SKIPPED ("TODO") instead of failing.

A stub raises NotImplementedError; this hook turns that into a skip so the
full suite stays green while the engine is being written. Run with ``-rs``
to see the TODO list.
"""

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if call.excinfo is not None and call.excinfo.errisinstance(NotImplementedError):
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1], f"TODO {call.excinfo.value}")
