from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.market_data.trust import SEBI_FEED, SOURCE_POLICIES, parse_sebi_feed, validate_daily_bar
from scripts.collect_data_evidence import collect

NOW = datetime(2026, 11, 18, 16, tzinfo=timezone.utc)


def feed(*items):
    return ('<rss><channel>' + ''.join(items) + '</channel></rss>').encode()


def item(title='Headline', url='https://www.sebi.gov.in/legal/circulars/example.html', pub='Wed, 18 Nov 2026 20:00:00 +0530'):
    return f'<item><title>{title}</title><link>{url}</link><pubDate>{pub}</pubDate></item>'


def bar(**overrides):
    return {'date': '2026-11-18', 'symbol': 'TEST', 'exchange': 'NSE', 'currency': 'INR',
            'adjustment': 'raw', 'open': 100, 'high': 110, 'low': 95, 'close': 105,
            'volume': 1234, **overrides}


def check(**overrides):
    return validate_daily_bar(bar(**overrides), expected_session=date(2026, 11, 18), source='yfinance')


def test_valid_headline_provenance_and_dedup():
    result = parse_sebi_feed(feed(item(), item()), fetched_at=NOW)
    assert result['source_url'] == SEBI_FEED
    assert len(result['records']) == 1
    record = result['records'][0]
    assert record['published_at'] == '2026-11-18T14:30:00+00:00'
    assert record['public_display'] == 'review_required'
    assert 'description' not in record
    assert result['payload_sha256']


@pytest.mark.parametrize('url', ['http://www.sebi.gov.in/x', 'https://evil.test/',
    'https://www.sebi.gov.in.evil.test/x', 'https://x@evil.test/x', 'javascript:alert(1)', ''])
def test_reject_untrusted_item_urls(url):
    result = parse_sebi_feed(feed(item(url=url)), fetched_at=NOW)
    assert not result['records']
    assert result['rejected']


@pytest.mark.parametrize('pub', ['', 'yesterday', 'Thu, 19 Nov 2026 20:00:00 +0530'])
def test_reject_unknown_or_future_item_date(pub):
    assert not parse_sebi_feed(feed(item(pub=pub)), fetched_at=NOW)['records']


def test_empty_is_not_no_market_events():
    r = parse_sebi_feed(feed(), fetched_at=NOW)
    assert r['collection_status'] == 'empty_or_all_rejected'
    assert 'not a complete' in r['coverage_warning']


@pytest.mark.parametrize('raw', [b'<!DOCTYPE rss><rss/>', b'<!ENTITY x "y"><rss/>', b'x' * 2_000_001, b'<html/>'])
def test_reject_unsafe_or_unexpected_feed(raw):
    with pytest.raises(ValueError):
        parse_sebi_feed(raw, fetched_at=NOW)


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        parse_sebi_feed(feed(), fetched_at=datetime(2026, 11, 18))


def test_quality_is_not_permission():
    r = check()
    assert r['quality'] == 'valid'
    assert r['public_display'] == 'not_cleared'


@pytest.mark.parametrize('overrides', [dict(close=float('nan')), dict(open=float('inf')),
    dict(high=90), dict(low=106), dict(open=0), dict(volume=-1), dict(volume=1.5),
    dict(close=True), dict(close='105'), dict(symbol=''), dict(exchange=''),
    dict(currency=''), dict(adjustment='unknown'), dict(date='bad'), dict(date='2026-11-19')])
def test_bad_bars_fail_closed(overrides):
    r = check(**overrides)
    assert r['quality'] == 'rejected'
    assert not r['usable_for_current_signals']


def test_stale_bar_not_current_signal():
    r = check(date='2026-11-17')
    assert r['quality'] == 'stale'
    assert not r['usable_for_current_signals']


def test_zero_volume_is_warning_not_invented_volume():
    assert check(volume=0)['warnings'] == ['zero_volume_check_instrument_type']


def test_unknown_source_never_cleared():
    r = validate_daily_bar(bar(), expected_session=date(2026, 11, 18), source='other')
    assert r['public_display'] == 'not_cleared'
    assert 'unknown_source' in r['errors']


def test_bse_nse_not_collectable_by_default():
    assert SOURCE_POLICIES['bse']['collection'] == 'written_consent_required'
    assert SOURCE_POLICIES['nse']['collection'] == 'agreement_required'


def test_offline_collector_no_network(tmp_path):
    out = tmp_path / 'evidence.json'
    with patch('scripts.collect_data_evidence.build_opener') as network:
        collect(out, raw=feed(item()), now=NOW)
    network.assert_not_called()
    assert out.read_text().endswith('\n')


def test_malformed_feed_preserves_last_good_output(tmp_path):
    out = tmp_path / 'evidence.json'
    collect(out, raw=feed(item()), now=NOW)
    before = out.read_bytes()
    with pytest.raises(Exception):
        collect(out, raw=b'<rss><broken>', now=NOW)
    assert out.read_bytes() == before


def test_failed_network_attempt_cools_down(tmp_path):
    out = tmp_path / 'evidence.json'
    with patch('scripts.collect_data_evidence.build_opener') as network:
        network.return_value.open.side_effect = OSError('offline')
        with pytest.raises(OSError):
            collect(out, now=NOW)
        with pytest.raises(ValueError, match='cooldown'):
            collect(out, now=NOW)
    assert network.call_count == 1
    assert not out.exists()


def test_redirect_not_followed():
    from scripts.collect_data_evidence import NoRedirect
    with pytest.raises(ValueError, match='redirect'):
        NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test/')


def test_compact_date_is_not_a_canonical_session():
    result = validate_daily_bar(bar(date='20261118'), expected_session=date(2026, 11, 18), source='yfinance')
    assert 'invalid_session_date' in result['errors']


def test_twelvedata_display_is_not_blanket_redistribution_claim():
    assert SOURCE_POLICIES['twelvedata']['public_display'] == 'plan_and_exchange_dependent'
