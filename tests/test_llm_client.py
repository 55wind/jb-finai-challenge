"""LLM 가용성 캐시 TTL — 서버 up/down 자동 재감지 (프로덕션 견고성)."""
import httpx
import pytest

from app.pipeline import llm_client


@pytest.fixture(autouse=True)
def reset_cache():
    llm_client._available = None
    llm_client._checked_at = 0.0
    yield
    llm_client._available = None
    llm_client._checked_at = 0.0


class _FakeClient:
    """지정한 status_code(또는 예외)를 돌려주는 httpx.AsyncClient 대체."""
    def __init__(self, status=200, raise_exc=False):
        self.status = status
        self.raise_exc = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        if self.raise_exc:
            raise httpx.ConnectError("down")
        return httpx.Response(self.status)


def _patch(monkeypatch, **kw):
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda *a, **k: _FakeClient(**kw))


@pytest.mark.anyio
async def test_cache_hit_skips_probe_within_ttl(monkeypatch):
    _patch(monkeypatch, status=200)
    assert await llm_client.is_available() is True
    # 서버가 죽어도 TTL 내에는 캐시 사용(재프로브 안 함)
    _patch(monkeypatch, raise_exc=True)
    assert await llm_client.is_available() is True


@pytest.mark.anyio
async def test_reprobe_after_ttl_detects_down(monkeypatch):
    _patch(monkeypatch, status=200)
    assert await llm_client.is_available() is True
    # TTL 경과 시뮬레이션 → 죽은 서버를 재감지해 폴백(무한 120s hang 방지)
    llm_client._checked_at -= (llm_client.LLM_PROBE_TTL + 1)
    _patch(monkeypatch, raise_exc=True)
    assert await llm_client.is_available() is False


@pytest.mark.anyio
async def test_reprobe_after_ttl_detects_up(monkeypatch):
    _patch(monkeypatch, raise_exc=True)
    assert await llm_client.is_available() is False
    # 뒤늦게 서버가 뜨면 TTL 후 폴백→LLM 자동 전환
    llm_client._checked_at -= (llm_client.LLM_PROBE_TTL + 1)
    _patch(monkeypatch, status=200)
    assert await llm_client.is_available() is True


@pytest.mark.anyio
async def test_force_check_bypasses_cache(monkeypatch):
    _patch(monkeypatch, status=200)
    assert await llm_client.is_available() is True
    _patch(monkeypatch, raise_exc=True)
    # force_check=True(=/api/health)는 TTL 무시하고 즉시 재프로브
    assert await llm_client.is_available(force_check=True) is False
