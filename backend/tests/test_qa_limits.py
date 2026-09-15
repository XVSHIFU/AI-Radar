import pytest

from radar.qa_limits import AskAdmission, AskLimitReached


def test_slots_release_on_failure_and_reject_concurrent_work():
    limiter = AskAdmission(max_active=1)
    with pytest.raises(ValueError), limiter.slot("first"):
        with pytest.raises(AskLimitReached), limiter.slot("second"):
            pytest.fail("concurrent request admitted")
        raise ValueError("simulated provider failure")
    with limiter.slot("second"):
        pass


def test_client_and_global_windows_expire_without_retaining_clients():
    now = [0.0]
    limiter = AskAdmission(clock=lambda: now[0], per_client=1, total_per_minute=2)
    with limiter.slot("a"):
        pass
    with pytest.raises(AskLimitReached), limiter.slot("a"):
        pytest.fail("same client exceeded limit")
    with limiter.slot("b"):
        pass
    with pytest.raises(AskLimitReached), limiter.slot("c"):
        pytest.fail("global window exceeded")
    now[0] = 60.0
    with limiter.slot("c"):
        pass
    assert set(limiter._clients) == {"c"}


def test_client_table_is_bounded_without_eviction_bypass():
    limiter = AskAdmission(max_clients=1)
    with limiter.slot("a"):
        pass
    with pytest.raises(AskLimitReached), limiter.slot("b"):
        pytest.fail("unbounded client admitted")
    assert set(limiter._clients) == {"a"}
