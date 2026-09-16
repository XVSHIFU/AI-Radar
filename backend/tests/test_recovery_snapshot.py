import copy

import pytest

from radar.recovery_bundle import FINGERPRINT_TABLES, InvalidBundle
from radar.recovery_snapshot import MAX_ROW_BYTES, TableDigest, compare_fingerprints


def fingerprint(table, *rows):
    digest = TableDigest(table)
    for row in rows:
        digest.add(row)
    return digest.finish()


def test_fingerprint_preserves_row_boundaries_order_nulls_and_identity():
    digest = fingerprint("public_ask_requests", '{"charged":true}', '{"ip_hash":null}')
    assert digest["rows"] == 2
    assert digest != fingerprint("public_ask_requests", '{"ip_hash":null}', '{"charged":true}')
    assert digest != fingerprint("public_ask_requests", '{"charged":true}{"ip_hash":null}')
    assert digest != fingerprint("public_ask_requests", '{"charged":false}', '{"ip_hash":null}')
    assert fingerprint("events") != fingerprint("evidence")


def test_oversized_rows_and_unknown_tables_fail_without_including_data():
    with pytest.raises(InvalidBundle, match="unknown recovery table"):
        TableDigest("public_ask_requests; DELETE FROM events")
    digest = TableDigest("public_ask_requests")
    with pytest.raises(InvalidBundle, match="invalid recovery row"):
        digest.add(None)
    with pytest.raises(InvalidBundle, match="capture limit"):
        digest.add("a" * (MAX_ROW_BYTES + 1))
    assert digest.finish()["rows"] == 0


@pytest.mark.parametrize("change", ["missing", "count", "digest", "boolean", "extra", "actual"])
def test_restore_gate_rejects_missing_or_altered_ledger(change):
    actual = {name: fingerprint(name, '{"charge":20}') for name in FINGERPRINT_TABLES}
    expected = copy.deepcopy(actual)
    compare_fingerprints(expected, actual)
    if change == "missing":
        del expected["research_model_calls"]
    elif change == "count":
        expected["public_ask_requests"]["rows"] = 0
    elif change == "digest":
        expected["llm_calls"]["sha256"] = "0" * 64
    elif change == "boolean":
        expected["events"]["rows"] = True
    elif change == "extra":
        expected["foreign"] = fingerprint("events")
    else:
        del actual["events"]
    with pytest.raises(InvalidBundle):
        compare_fingerprints(expected, actual)
