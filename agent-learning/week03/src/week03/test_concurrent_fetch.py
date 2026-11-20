import pytest
from week03.concurrent_fetch import fetch,summarize
import httpx

@pytest.mark.asyncio
async def test_fetch_returns_name():
    async with httpx.AsyncClient() as client:
        r = await fetch(client,"IP归属","http://ip-api.com/json/")
        assert r["name"] == "IP归属"
        assert "data" in r

def test_summarize_handles_unkonw_shape():
    out = summarize([{"name":"X","data":{"whatever":1}}])
    assert "X:OK" in out 