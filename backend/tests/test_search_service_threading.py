"""SearchService under a thread pool.

The Celery worker runs competitor audits on a thread pool, so concurrent audits
share one SearchService and its Brave throttle.
"""

import threading
import time
from unittest.mock import MagicMock, patch

from app.services import search_service
from app.services.search_service import SearchService


def _brave_ok() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"web": {"results": []}}
    return resp


def test_concurrent_fetches_are_spaced_by_the_throttle_interval():
    svc = SearchService(redis_client=False)
    svc.search_enabled = True
    svc.MIN_REQUEST_INTERVAL = 0.1

    call_times = []

    def fake_get(*args, **kwargs):
        call_times.append(time.time())
        return _brave_ok()

    with patch("app.services.search_service.requests.get", side_effect=fake_get):
        threads = [
            threading.Thread(target=svc._fetch_from_brave, args=(f"query {i}",))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(call_times) == 4
    call_times.sort()
    gaps = [b - a for a, b in zip(call_times, call_times[1:])]
    # Without the lock all four requests leave together; allow timer slack.
    assert all(gap >= 0.09 for gap in gaps), gaps


def test_get_search_service_builds_one_instance_across_threads():
    built = []

    def slow_build():
        time.sleep(0.05)
        instance = object()
        built.append(instance)
        return instance

    barrier = threading.Barrier(4)
    results = []

    def worker():
        barrier.wait()
        results.append(search_service.get_search_service())

    with patch.object(search_service, "_search_service", None), \
            patch.object(search_service, "SearchService", side_effect=slow_build):
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(built) == 1
    assert len({id(r) for r in results}) == 1
