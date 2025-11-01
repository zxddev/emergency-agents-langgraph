import os
import time
import requests


def test_healthz_local():
    # 允许在 CI 或本地跳过
    if os.getenv("SKIP_LOCAL_HEALTH_TEST") == "1":
        return

    url = os.getenv("API_HEALTH_URL", "http://127.0.0.1:8008/healthz")
    # 等待服务最多 5 秒
    for _ in range(5):
        try:
            r = requests.get(url, timeout=1.0)
            if r.ok:
                assert r.json().get("status") == "ok"
                return
        except Exception:
            time.sleep(1)
    raise AssertionError(f"health check failed: {url}")


