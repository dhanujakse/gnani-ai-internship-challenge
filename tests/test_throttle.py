import httpx
import respx

from kuralcheck.clients._http import post_with_retry
from kuralcheck.throttle import Throttle, shared_throttle


class FakeClock:
    def __init__(self) -> None:
        self.t = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(round(s, 6))
        self.t += s


def test_spaces_calls_evenly() -> None:
    clk = FakeClock()
    th = Throttle(2.0, clock=clk.now, sleep=clk.sleep)  # 0.5 s apart
    for _ in range(4):
        th.wait()
    assert clk.sleeps == [0.5, 0.5, 0.5]


def test_no_wait_after_idle_time() -> None:
    clk = FakeClock()
    th = Throttle(1.0, clock=clk.now, sleep=clk.sleep)
    th.wait()
    clk.t += 5
    th.wait()
    assert clk.sleeps == []


def test_shared_throttle_is_one_per_rate() -> None:
    assert shared_throttle(1.0) is shared_throttle(1.0)
    assert shared_throttle(0) is None


def test_every_attempt_waits_including_retry() -> None:
    calls: list[str] = []

    class Spy:
        def wait(self) -> None:
            calls.append("wait")

    with respx.mock() as router:
        router.post("https://x.test/a").mock(side_effect=[httpx.Response(429), httpx.Response(200)])
        with httpx.Client() as http:
            resp, _ = post_with_retry(http, "https://x.test/a", name="t", sleep=lambda s: None, throttle=Spy())
    assert resp.status_code == 200 and calls == ["wait", "wait"]
