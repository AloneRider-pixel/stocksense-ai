import logging
import pytest
from app import demo
from app.core.config import settings


def test_phase_order_and_failure_logging_preserve_exception_and_session_close(monkeypatch,caplog):
    events=[]
    class Session:
        def close(self):events.append('close')
    monkeypatch.setattr(settings,'environment','development')
    monkeypatch.setattr(settings,'market_data_provider','twelve_data')
    monkeypatch.setattr(demo,'init_db',lambda:events.append('db'))
    monkeypatch.setattr(demo,'get_session',Session)
    monkeypatch.setattr(demo,'_ingest_live_symbols',lambda s:events.append('ingest')or 0)
    fault=RuntimeError('secret-must-not-be-logged')
    def fail(s):events.append('models');raise fault
    monkeypatch.setattr(demo,'_train_live_symbol_models',fail)
    monkeypatch.setattr(demo,'_seed_demo_user',lambda s:pytest.fail('must not change order'))
    with caplog.at_level(logging.INFO):
        with pytest.raises(RuntimeError)as result:demo.seed_demo_environment()
    assert result.value is fault
    assert events==['db','ingest','models','close']
    assert 'phase=live_models symbol=- status=failed' in caplog.text
    assert 'error_type=RuntimeError' in caplog.text and 'duration_ms=' in caplog.text
    assert 'secret-must-not-be-logged'not in caplog.text


def test_phase_uses_monotonic_duration_and_reraises_cancellation(monkeypatch,caplog):
    import asyncio
    times=iter([10,10.25]);monkeypatch.setattr(demo.time,'perf_counter',lambda:next(times))
    with caplog.at_level(logging.INFO):
        with pytest.raises(asyncio.CancelledError):
            with demo._startup_phase('fixture'):raise asyncio.CancelledError()
    assert 'duration_ms=250.0 error_type=CancelledError'in caplog.text
