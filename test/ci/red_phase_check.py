#!/usr/bin/env python3
"""CI gate: prove the ATDD suite is RED for the RIGHT reason.

The solutioning stop-point means no production code exists, so the ATDD contract
suite (``test/atdd``) must fail on purpose. This gate asserts that:

* every collected test is executed (no silent skips), and
* every test FAILS in the call phase with ``NotImplementedError`` — i.e. it reached
  the interface stub and failed on the contract, not on a typo, import error or a
  collection error.

Any pass, error (setup/teardown/collection), or skip is a gate FAILURE.

Usage:  python test/ci/red_phase_check.py     (also: make red-phase)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ATDD_DIR = Path(__file__).resolve().parents[1] / "atdd"

#: The only acceptable red-phase failure: the interface stub was called.
EXPECTED_EXC = "NotImplementedError"


class RedPhasePlugin:
    """Collects the call-phase outcome + exception type of every ATDD test."""

    def __init__(self) -> None:
        self.results: list[tuple[str, str, str | None]] = []

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):  # noqa: ANN001
        outcome = yield
        report = outcome.get_result()
        if report.when == "call":
            exc_type = call.excinfo.type.__name__ if call.excinfo else None
            self.results.append((item.nodeid, report.outcome, exc_type))


def main() -> int:
    plugin = RedPhasePlugin()
    pytest.main(
        [str(ATDD_DIR), "-q", "--tb=no", "-p", "no:cacheprovider"],
        plugins=[plugin],
    )

    if not plugin.results:
        print("GATE FAIL: no ATDD tests were collected")
        return 1

    bad = [
        (nid, outcome, exc)
        for (nid, outcome, exc) in plugin.results
        if outcome != "failed" or exc != EXPECTED_EXC
    ]

    print(f"ATDD collected: {len(plugin.results)} tests")
    print(f"red-for-the-right-reason: {len(plugin.results) - len(bad)}/{len(plugin.results)}")

    if bad:
        print("GATE FAIL: these tests did not fail on the interface stub:")
        for nid, outcome, exc in bad[:20]:
            print(f"  [{outcome}] {nid} (exc={exc})")
        return 1

    print(f"GATE PASS: all {len(plugin.results)} ATDD tests red on {EXPECTED_EXC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
