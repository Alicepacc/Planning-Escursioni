"""Client HTTP "educato": l'unico punto da cui l'ingestion parla con server altrui.

Applica le regole del §3 della SPEC ("Rispetto dei server altrui"):

- User-Agent identificativo (vedi `config.user_agent`);
- cache su disco con TTL e richieste condizionali (ETag / If-Modified-Since);
- intervallo minimo tra richieste allo stesso host;
- retry con backoff esponenziale su 429/5xx ed errori di rete, onorando `Retry-After`;
- `robots.txt` rispettato (RFC 9309).

Tutti gli adapter delle fonti devono usare `PoliteClient`; niente `httpx.get` sparsi.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from .config import data_dir, user_agent

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
ROBOTS_TTL = 24 * 3600
ROBOTS_AGENT = "Cordata"


class RobotsDisallowed(Exception):
    """L'URL è escluso dal robots.txt dell'host (o il robots.txt non è leggibile)."""


class FetchError(Exception):
    """Richiesta fallita dopo tutti i tentativi (errore di rete o stato HTTP non recuperabile)."""

    def __init__(self, url: str, reason: str, status: int | None = None):
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason
        self.status = status


@dataclass
class Fetched:
    url: str
    status: int
    headers: dict[str, str]
    content: bytes
    fetched_at: float
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.content)

    def header(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    def raise_for_status(self) -> Fetched:
        if not self.ok:
            raise FetchError(self.url, f"HTTP {self.status}", self.status)
        return self


def _full_url(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    query = urlencode(sorted((k, v) for k, v in params.items() if v is not None), doseq=True)
    return f"{url}{'&' if '?' in url else '?'}{query}"


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


class PoliteClient:
    """Client HTTP con cache, rate limit per host, retry/backoff e robots.txt."""

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        ua: str | None = None,
        min_interval: float = 1.0,
        host_intervals: Mapping[str, float] | None = None,
        max_retries: int = 4,
        max_backoff: float = 60.0,
        timeout: float = 30.0,
        respect_robots: bool = True,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else data_dir() / "http-cache"
        self.ua = ua or user_agent()
        self.min_interval = min_interval
        self.host_intervals = dict(host_intervals or {})
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        self.respect_robots = respect_robots
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._http = httpx.Client(
            headers={"User-Agent": self.ua, "Accept-Encoding": "gzip, deflate"},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self.requests_made = 0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ cache

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        host = urlsplit(url).netloc.replace(":", "_") or "nohost"
        key = hashlib.sha256(url.encode()).hexdigest()[:32]
        base = self.cache_dir / host / key
        return base.with_suffix(".body"), base.with_suffix(".meta.json")

    def _cache_read(self, url: str) -> Fetched | None:
        body, meta = self._cache_paths(url)
        if not (body.exists() and meta.exists()):
            return None
        try:
            info = json.loads(meta.read_text(encoding="utf-8"))
            return Fetched(
                url=info["url"],
                status=info["status"],
                headers=info["headers"],
                content=body.read_bytes(),
                fetched_at=info["fetched_at"],
                from_cache=True,
            )
        except (OSError, ValueError, KeyError):
            return None

    def _cache_write(self, url: str, res: Fetched) -> None:
        body, meta = self._cache_paths(url)
        body.parent.mkdir(parents=True, exist_ok=True)
        body.write_bytes(res.content)
        meta.write_text(
            json.dumps(
                {
                    "url": res.url,
                    "status": res.status,
                    "headers": res.headers,
                    "fetched_at": res.fetched_at,
                    "sha256": res.sha256,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    # ------------------------------------------------------------- rate limit

    def _throttle(self, host: str) -> None:
        interval = self.host_intervals.get(host, self.min_interval)
        last = self._last_request.get(host)
        if last is not None:
            wait = interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)

    # ----------------------------------------------------------------- robots

    def allowed_by_robots(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        parser = self._robots[origin]
        if parser is None:  # robots.txt irraggiungibile: RFC 9309 → trattare come divieto totale
            return False
        return parser.can_fetch(ROBOTS_AGENT, url)

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        parser = RobotFileParser()
        try:
            res = self._fetch(f"{origin}/robots.txt", {}, ttl=ROBOTS_TTL)
        except FetchError as exc:
            log.warning("robots.txt non raggiungibile per %s: %s", origin, exc.reason)
            return None
        if res.ok:
            parser.parse(res.text().splitlines())
        elif 400 <= res.status < 500:
            parser.parse([])  # nessun robots.txt: tutto consentito
        else:
            log.warning("robots.txt di %s risponde %s: accesso sospeso", origin, res.status)
            return None
        return parser

    # ------------------------------------------------------------------ fetch

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        ttl: float | None = 24 * 3600,
        respect_robots: bool | None = None,
    ) -> Fetched:
        """GET con cache, rate limit, retry e robots.txt.

        `ttl` è la validità della cache in secondi (None = nessuna cache). Restituisce la risposta
        anche se lo stato finale non è 2xx (usare `raise_for_status()`); solleva `FetchError` solo
        per errori di rete persistenti e `RobotsDisallowed` se il robots.txt vieta l'URL.
        """
        full = _full_url(url, params)
        check_robots = self.respect_robots if respect_robots is None else respect_robots
        if check_robots and not self.allowed_by_robots(full):
            raise RobotsDisallowed(full)
        return self._fetch(full, dict(headers or {}), ttl=ttl)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        return self.get(url, **kwargs).raise_for_status().json()

    def _fetch(self, url: str, headers: dict[str, str], *, ttl: float | None) -> Fetched:
        cached = self._cache_read(url) if ttl is not None else None
        if cached and (time.time() - cached.fetched_at) < ttl:
            return cached
        if cached:  # scaduta: prova una richiesta condizionale
            if etag := cached.header("etag"):
                headers.setdefault("If-None-Match", etag)
            if modified := cached.header("last-modified"):
                headers.setdefault("If-Modified-Since", modified)

        host = urlsplit(url).netloc
        last_error = "nessun tentativo"
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            retry_after: float | None = None
            try:
                self.requests_made += 1
                resp = self._http.get(url, headers=headers)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                resp = None
            finally:
                self._last_request[host] = self._clock()

            if resp is not None:
                if resp.status_code == 304 and cached:
                    cached.fetched_at = time.time()
                    self._cache_write(url, cached)
                    return cached
                res = Fetched(
                    url=str(resp.url),
                    status=resp.status_code,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    content=resp.content,
                    fetched_at=time.time(),
                )
                if resp.status_code not in RETRY_STATUSES:
                    if res.ok and ttl is not None:
                        self._cache_write(url, res)
                    return res
                last_error = f"HTTP {resp.status_code}"
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                if attempt == self.max_retries:
                    return res

            if attempt < self.max_retries:
                backoff = min(self.max_backoff, 2.0**attempt) + random.uniform(0, 0.5)
                delay = min(self.max_backoff, max(backoff, retry_after or 0.0))
                log.info("%s → %s; nuovo tentativo tra %.1fs", url, last_error, delay)
                self._sleep(delay)
        raise FetchError(url, last_error)

    # --------------------------------------------------------------- download

    def download(
        self, url: str, dest: Path, *, respect_robots: bool | None = None
    ) -> dict[str, Any]:
        """Scarica un file grande in streaming, con SHA-256 e richiesta condizionale.

        Accanto a `dest` salva `<dest>.meta.json` (url, etag, last-modified, sha256, fetched_at):
        serve per la riproducibilità e per non riscaricare un file invariato.
        """
        check_robots = self.respect_robots if respect_robots is None else respect_robots
        if check_robots and not self.allowed_by_robots(url):
            raise RobotsDisallowed(url)
        dest = Path(dest)
        meta_path = dest.with_name(dest.name + ".meta.json")
        headers: dict[str, str] = {}
        if dest.exists() and meta_path.exists():
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            if old.get("etag"):
                headers["If-None-Match"] = old["etag"]
            if old.get("last_modified"):
                headers["If-Modified-Since"] = old["last_modified"]

        host = urlsplit(url).netloc
        last_error = "nessun tentativo"
        for attempt in range(self.max_retries + 1):
            self._throttle(host)
            try:
                self.requests_made += 1
                with self._http.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 304:
                        return {**old, "unchanged": True}
                    if resp.status_code in RETRY_STATUSES:
                        last_error = f"HTTP {resp.status_code}"
                    else:
                        if resp.status_code != 200:
                            raise FetchError(url, f"HTTP {resp.status_code}", resp.status_code)
                        digest = hashlib.sha256()
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        tmp = dest.with_name(dest.name + ".part")
                        with tmp.open("wb") as fh:
                            for chunk in resp.iter_bytes(1 << 20):
                                fh.write(chunk)
                                digest.update(chunk)
                        tmp.replace(dest)
                        meta = {
                            "url": url,
                            "etag": resp.headers.get("ETag"),
                            "last_modified": resp.headers.get("Last-Modified"),
                            "sha256": digest.hexdigest(),
                            "bytes": dest.stat().st_size,
                            "fetched_at": time.time(),
                            "unchanged": False,
                        }
                        meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
                        return meta
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            finally:
                self._last_request[host] = self._clock()
            if attempt < self.max_retries:
                self._sleep(min(self.max_backoff, 2.0**attempt) + random.uniform(0, 0.5))
        raise FetchError(url, last_error)
