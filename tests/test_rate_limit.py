from unittest.mock import MagicMock

from src.llm.rate_limit import RateLimiter


class TestRateLimiterDisabled:
    def test_disabled_returns_immediately(self):
        limiter = RateLimiter(0)
        limiter.wait()
        limiter.wait()


class TestRateLimiterTokens:
    def test_allows_initial_tokens(self):
        limiter = RateLimiter(3)
        limiter.wait()
        limiter.wait()
        limiter.wait()

    def test_blocks_when_tokens_exhausted(self, mocker):
        now = {"value": 1000.0}
        mocker.patch(
            "src.llm.rate_limit.time.monotonic",
            side_effect=lambda: now["value"],
        )
        limiter = RateLimiter(3)
        limiter.wait()
        limiter.wait()
        limiter.wait()

        sleep_mock = MagicMock()

        def _fake_sleep(delay):
            now["value"] += delay
            sleep_mock(delay)

        mocker.patch("src.llm.rate_limit.time.sleep", side_effect=_fake_sleep)
        limiter.wait()
        sleep_mock.assert_called()

    def test_refill_accumulates_tokens(self, mocker):
        now = {"value": 1000.0}
        mocker.patch(
            "src.llm.rate_limit.time.monotonic",
            side_effect=lambda: now["value"],
        )
        limiter = RateLimiter(3)
        limiter.wait()
        limiter.wait()
        limiter.wait()
        assert limiter._tokens == 0.0

        now["value"] += 60.0
        limiter._refill()
        assert limiter._tokens == 3.0
