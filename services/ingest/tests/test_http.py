"""Test del client HTTP educato: cache, rate limit, retry/backoff, robots.txt."""

from __future__ import annotations

import httpx
import pytest

from cordata_ingest.http import FetchError, PoliteClient, RobotsDisallowed


class FakeTime:
    """Orologio finto: `sleep` avanza il tempo senza aspettare davvero."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(handler, tmp_path, fake: FakeTime, **kwargs) -> PoliteClient:
    return PoliteClient(
        cache_dir=tmp_path / "cache",
        ua="Cordata-test/0",
        transport=httpx.MockTransport(handler),
        sleep=fake.sleep,
        clock=fake.clock,
        **kwargs,
    )


def test_user_agent_and_cache_hit(tmp_path):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"n": len(calls)})

    client = make_client(handler, tmp_path, FakeTime(), respect_robots=False)
    first = client.get("https://example.org/api", params={"b": 2, "a": 1})
    second = client.get("https://example.org/api", params={"a": 1, "b": 2})

    assert len(calls) == 1, "la seconda richiesta deve arrivare dalla cache"
    assert calls[0].headers["User-Agent"] == "Cordata-test/0"
    assert str(calls[0].url) == "https://example.org/api?a=1&b=2"
    assert first.json() == second.json() == {"n": 1}
    assert not first.from_cache and second.from_cache


def test_ttl_none_disables_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text="ok")

    client = make_client(handler, tmp_path, FakeTime(), respect_robots=False)
    client.get("https://example.org/x", ttl=None)
    client.get("https://example.org/x", ttl=None)
    assert len(calls) == 2


def test_rate_limit_between_requests_to_same_host(tmp_path):
    fake = FakeTime()
    client = make_client(
        lambda r: httpx.Response(200, text="ok"),
        tmp_path,
        fake,
        respect_robots=False,
        min_interval=2.0,
        host_intervals={"slow.example.org": 5.0},
    )
    client.get("https://example.org/1", ttl=None)
    client.get("https://example.org/2", ttl=None)
    assert fake.sleeps == [2.0]

    client.get("https://other.example.org/1", ttl=None)  # host diverso: nessuna attesa
    assert fake.sleeps == [2.0]

    client.get("https://slow.example.org/1", ttl=None)
    client.get("https://slow.example.org/2", ttl=None)
    assert fake.sleeps == [2.0, 5.0]


def test_retry_on_429_honours_retry_after(tmp_path):
    fake = FakeTime()
    statuses = iter([429, 503, 200])

    def handler(request):
        status = next(statuses)
        headers = {"Retry-After": "7"} if status == 429 else {}
        return httpx.Response(status, headers=headers, text=str(status))

    client = make_client(handler, tmp_path, fake, respect_robots=False, min_interval=0)
    res = client.get("https://example.org/x")

    assert res.status == 200 and client.requests_made == 3
    assert fake.sleeps[0] == pytest.approx(7.0), "Retry-After prevale sul backoff iniziale"
    assert 2.0 <= fake.sleeps[1] <= 2.5, "secondo tentativo: backoff esponenziale con jitter"


def test_gives_up_and_returns_last_response(tmp_path):
    client = make_client(
        lambda r: httpx.Response(429, text="rate limited"),
        tmp_path,
        FakeTime(),
        respect_robots=False,
        max_retries=2,
        min_interval=0,
    )
    res = client.get("https://example.org/x")
    assert res.status == 429 and client.requests_made == 3
    with pytest.raises(FetchError):
        res.raise_for_status()
    assert client.get("https://example.org/x").from_cache is False, "gli errori non vanno in cache"


def test_network_error_raises_fetch_error(tmp_path):
    def handler(request):
        raise httpx.ConnectError("connection reset by peer")

    client = make_client(
        handler, tmp_path, FakeTime(), respect_robots=False, max_retries=1, min_interval=0
    )
    with pytest.raises(FetchError, match="ConnectError"):
        client.get("https://example.org/x")
    assert client.requests_made == 2


def test_conditional_request_when_cache_expired(tmp_path):
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, headers={"ETag": '"v1"'}, text="payload")

    client = make_client(handler, tmp_path, FakeTime(), respect_robots=False)
    client.get("https://example.org/doc", ttl=3600)
    again = client.get("https://example.org/doc", ttl=0)  # cache scaduta → richiesta condizionale

    assert len(seen) == 2 and seen[1].headers["If-None-Match"] == '"v1"'
    assert again.from_cache and again.text() == "payload"


def test_robots_txt_is_respected(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /privato/\n")
        return httpx.Response(200, text="ok")

    client = make_client(handler, tmp_path, FakeTime())
    assert client.get("https://example.org/pubblico/a").ok
    with pytest.raises(RobotsDisallowed):
        client.get("https://example.org/privato/a")


def test_missing_robots_allows_but_broken_robots_blocks(tmp_path):
    def handler(request):
        if request.url.host == "no-robots.example.org" and request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.host == "broken.example.org" and request.url.path == "/robots.txt":
            return httpx.Response(500)
        return httpx.Response(200, text="ok")

    client = make_client(handler, tmp_path, FakeTime(), max_retries=0)
    assert client.get("https://no-robots.example.org/a").ok
    with pytest.raises(RobotsDisallowed):
        client.get("https://broken.example.org/a")


def test_download_streams_and_skips_unchanged(tmp_path):
    def handler(request):
        if request.headers.get("If-None-Match") == '"abc"':
            return httpx.Response(304)
        return httpx.Response(200, headers={"ETag": '"abc"'}, content=b"x" * 1000)

    client = make_client(handler, tmp_path, FakeTime(), respect_robots=False)
    dest = tmp_path / "out" / "file.bin"
    meta = client.download("https://example.org/file.bin", dest)
    assert dest.read_bytes() == b"x" * 1000 and meta["bytes"] == 1000 and not meta["unchanged"]
    assert len(meta["sha256"]) == 64

    again = client.download("https://example.org/file.bin", dest)
    assert again["unchanged"] is True
