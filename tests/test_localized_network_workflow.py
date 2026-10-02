"""Contract tests for the manual Task 27 hosted workflow and protocol."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/localized-network.yml"
METHODOLOGY = ROOT / "docs/methodology/localized_network_operating_envelope_v1.md"
DECISIONS = ROOT / "docs/development/decisions.md"
MANIFEST = ROOT / "simulations/configs/localized_network_v1.json"


def test_workflow_is_manual_fixed_matrix_and_retains_failed_shards() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert re.search(r"(?m)^on:\s*\n\s+workflow_dispatch:\s*$", text)
    for forbidden in ("schedule:", "push:", "pull_request:"):
        assert forbidden not in text
    assert re.search(r"(?m)^\s+p:\s*\[20,\s*40,\s*60\]\s*$", text)
    assert "timeout-minutes: 70" in text
    assert "actions/upload-artifact@" in text
    assert "actions/download-artifact@" in text
    assert "if: always()" in text
    assert "continue-on-error: true" in text
    assert "tools.run_localized_network" in text
    assert "tools.summarize_localized_network" in text
    assert "--p-shard" in text
    assert "--shard" in text
    assert "retention-days:" in text
    aggregate = text.split("  aggregate:\n", maxsplit=1)[1]
    download_step = aggregate.split("uses: actions/download-artifact@", maxsplit=1)[1].split(
        "\n      - name:", maxsplit=1
    )[0]
    assert "if-no-files-found:" not in download_step


def test_workflow_matches_frozen_manifest_and_incomplete_artifact_behavior() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["p_values"] == [20, 40, 60]
    assert manifest["actions_timeout_minutes"] == 70
    assert manifest["operational_runtime_ceiling_seconds"] == 3600

    shard_job = text.split("  shards:\n", maxsplit=1)[1].split("\n  aggregate:", maxsplit=1)[0]
    aggregate_job = text.split("  aggregate:\n", maxsplit=1)[1]
    assert "${{ matrix.p }}" in shard_job
    assert "if: always()" in shard_job
    assert "if: always()" in aggregate_job
    assert "${{ needs.shards.result }}" in aggregate_job or "needs: [shards]" in text
    assert "summary.json" in aggregate_job
    assert "acceptance_status" in aggregate_job


def test_v1_protocol_and_prerun_decision_are_prespecified_and_scoped() -> None:
    protocol = METHODOLOGY.read_text(encoding="utf-8")
    decisions = DECISIONS.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for value in ("50", "100", "150", "20", "40", "60", "20261002", "1,000", "25", "100"):
        assert value in protocol
    for phrase in (
        "baseline cap 2",
        "diagnostic cap 4",
        "right-censored",
        "per-prespecified-edge",
        "not a network-wide",
        "p > N",
        "universal",
        "Wilson",
        "incomplete",
        "workflow_dispatch",
    ):
        assert phrase.casefold() in protocol.casefold()
    assert manifest["expected_rows"] == 1620
    assert manifest["expected_pairing_keys"] == 810

    assert "Task 27 pre-run decision" in decisions
    assert "f163ce9e528de59312abe785a5dda984ba8ee4f3c1c124c853bc78a76001bf48" in decisions
    assert "2f0b49a" in decisions and "74823b6" in decisions and "bef4f67" in decisions
    for file_name in (
        "localized_network_v1.json",
        "run_localized_network.py",
        "summarize_localized_network.py",
        "localized-network.yml",
        "localized_network_operating_envelope_v1.md",
    ):
        assert file_name in decisions
