import pytest

from conftest import FakeRedis
import security.webhook_event_deduplication as dedupe


class EvalRedisStub:
    def __init__(self):
        self.store = {}
        self.expirations = {}
        self.ttls = {}
        self.now = 0
        self.eval_calls = []
        self.raise_on_eval = False

    def _expire_if_needed(self, key):
        expires_at = self.expirations.get(key)
        if expires_at is not None and expires_at <= self.now:
            self.store.pop(key, None)
            self.expirations.pop(key, None)
            self.ttls.pop(key, None)

    def advance_time(self, seconds):
        self.now += seconds
        for key in list(self.expirations):
            self._expire_if_needed(key)

    def get(self, key):
        self._expire_if_needed(key)
        return self.store.get(key)

    def set(self, key, value, nx=False, ex=None):
        self._expire_if_needed(key)
        if nx and key in self.store:
            return False

        self.store[key] = value
        if ex is None:
            self.expirations.pop(key, None)
            self.ttls.pop(key, None)
        else:
            self.expirations[key] = self.now + ex
            self.ttls[key] = ex
        return True

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.expirations[key] = self.now + ttl
        self.ttls[key] = ttl

    def exists(self, key):
        self._expire_if_needed(key)
        return 1 if key in self.store else 0

    def delete(self, key):
        self.store.pop(key, None)
        self.expirations.pop(key, None)
        self.ttls.pop(key, None)

    def eval(self, script, numkeys, *args):
        self.eval_calls.append((script, numkeys, args))
        if self.raise_on_eval:
            raise RuntimeError("redis unavailable")

        if numkeys == 1:
            lock_key, token = args
            if self.get(lock_key) == token:
                self.delete(lock_key)
                return 1
            return 0

        if numkeys == 2:
            lock_key, event_key, token, ttl, processed_value = args
            if self.get(lock_key) == token:
                self.setex(event_key, int(ttl), processed_value)
                self.delete(lock_key)
                return 1
            return 0

        raise AssertionError(f"unexpected eval numkeys: {numkeys}")


@pytest.fixture
def fake_redis():
    return EvalRedisStub()


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch, fake_redis):
    monkeypatch.setattr(dedupe, "redis_client", fake_redis)
    return fake_redis


def test_acquire_event_claim_returns_processed_when_marker_exists(fake_redis):
    fake_redis.setex(dedupe.event_key("evt-processed"), 86400, dedupe.EVENT_PROCESSED_VALUE)

    status, token = dedupe.acquire_event_claim("evt-processed")

    assert status == dedupe.EVENT_CLAIM_PROCESSED
    assert token is None
    assert fake_redis.exists(dedupe.event_lock_key("evt-processed")) == 0


def test_acquire_event_claim_creates_lock_with_token_and_ttl(fake_redis):
    status, token = dedupe.acquire_event_claim("evt-new")

    assert status == dedupe.EVENT_CLAIM_ACQUIRED
    assert token
    assert fake_redis.get(dedupe.event_lock_key("evt-new")) == token
    assert fake_redis.ttls[dedupe.event_lock_key("evt-new")] == dedupe.EVENT_LOCK_TTL_SECONDS


def test_acquire_event_claim_returns_processing_when_lock_is_occupied(fake_redis):
    fake_redis.set(dedupe.event_lock_key("evt-locked"), "other-token", nx=True, ex=60)

    status, token = dedupe.acquire_event_claim("evt-locked")

    assert status == dedupe.EVENT_CLAIM_PROCESSING
    assert token is None
    assert fake_redis.get(dedupe.event_lock_key("evt-locked")) == "other-token"


def test_acquire_event_claim_returns_processed_when_marker_appears_after_lock_contention(fake_redis):
    event_id = "evt-processed-after-contention"
    fake_redis.set(dedupe.event_lock_key(event_id), "other-token", nx=True, ex=60)
    fake_redis.setex(dedupe.event_key(event_id), 86400, dedupe.EVENT_PROCESSED_VALUE)

    status, token = dedupe.acquire_event_claim(event_id)

    assert status == dedupe.EVENT_CLAIM_PROCESSED
    assert token is None


def test_acquire_event_claim_retries_once_when_lock_disappears(monkeypatch, fake_redis):
    event_id = "evt-lock-disappears"
    original_set = fake_redis.set
    calls = {"count": 0}

    def flaky_set(key, value, nx=False, ex=None):
        if key == dedupe.event_lock_key(event_id):
            calls["count"] += 1
            if calls["count"] == 1:
                return False
        return original_set(key, value, nx=nx, ex=ex)

    monkeypatch.setattr(fake_redis, "set", flaky_set)

    status, token = dedupe.acquire_event_claim(event_id)

    assert status == dedupe.EVENT_CLAIM_ACQUIRED
    assert token
    assert calls["count"] == 2
    assert fake_redis.get(dedupe.event_lock_key(event_id)) == token


def test_release_event_claim_removes_lock_only_for_owner(fake_redis):
    event_id = "evt-release-owner"
    fake_redis.set(dedupe.event_lock_key(event_id), "owner-token", nx=True, ex=60)

    dedupe.release_event_claim(event_id, "owner-token")

    assert fake_redis.exists(dedupe.event_lock_key(event_id)) == 0
    script, numkeys, args = fake_redis.eval_calls[-1]
    assert script == dedupe._RELEASE_EVENT_CLAIM_SCRIPT
    assert numkeys == 1
    assert args == (dedupe.event_lock_key(event_id), "owner-token")


def test_release_event_claim_does_not_remove_lock_for_non_owner(fake_redis):
    event_id = "evt-release-non-owner"
    fake_redis.set(dedupe.event_lock_key(event_id), "owner-token", nx=True, ex=60)

    dedupe.release_event_claim(event_id, "wrong-token")

    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "owner-token"


def test_release_event_claim_old_token_does_not_remove_new_owner(fake_redis):
    event_id = "evt-release-old-owner"
    fake_redis.set(dedupe.event_lock_key(event_id), "new-token", nx=True, ex=60)

    dedupe.release_event_claim(event_id, "old-token")

    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "new-token"


def test_expired_lock_allows_new_claim(fake_redis):
    event_id = "evt-expired-lock"
    fake_redis.set(dedupe.event_lock_key(event_id), "old-token", nx=True, ex=60)

    fake_redis.advance_time(61)
    status, token = dedupe.acquire_event_claim(event_id)

    assert status == dedupe.EVENT_CLAIM_ACQUIRED
    assert token
    assert fake_redis.get(dedupe.event_lock_key(event_id)) == token


def test_event_keys_are_independent(fake_redis):
    first_status, first_token = dedupe.acquire_event_claim("evt-a")
    second_status, second_token = dedupe.acquire_event_claim("evt-b")

    assert first_status == dedupe.EVENT_CLAIM_ACQUIRED
    assert second_status == dedupe.EVENT_CLAIM_ACQUIRED
    assert first_token != second_token
    assert fake_redis.get(dedupe.event_lock_key("evt-a")) == first_token
    assert fake_redis.get(dedupe.event_lock_key("evt-b")) == second_token


def test_mark_event_processed_preserves_value_and_ttl(fake_redis):
    event_id = "evt-mark-processed"
    status, token = dedupe.acquire_event_claim(event_id)
    assert status == dedupe.EVENT_CLAIM_ACQUIRED

    mark_status = dedupe.mark_event_processed(event_id, token)

    assert mark_status == dedupe.EVENT_CLAIM_PROCESSED
    assert fake_redis.get(dedupe.event_key(event_id)) == dedupe.EVENT_PROCESSED_VALUE
    assert fake_redis.ttls[dedupe.event_key(event_id)] == dedupe.EVENT_PROCESSED_TTL_SECONDS
    assert fake_redis.exists(dedupe.event_lock_key(event_id)) == 0
    script, numkeys, args = fake_redis.eval_calls[-1]
    assert script == dedupe._MARK_EVENT_PROCESSED_SCRIPT
    assert numkeys == 2
    assert args == (
        dedupe.event_lock_key(event_id),
        dedupe.event_key(event_id),
        token,
        dedupe.EVENT_PROCESSED_TTL_SECONDS,
        dedupe.EVENT_PROCESSED_VALUE,
    )


def test_mark_event_processed_does_not_write_when_token_is_not_owner(fake_redis):
    event_id = "evt-lost-ownership"
    fake_redis.set(dedupe.event_lock_key(event_id), "owner-token", nx=True, ex=60)

    mark_status = dedupe.mark_event_processed(event_id, "wrong-token")

    assert mark_status == dedupe.EVENT_CLAIM_LOST_OWNERSHIP
    assert fake_redis.exists(dedupe.event_key(event_id)) == 0
    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "owner-token"


def test_mark_event_processed_returns_lost_ownership_when_lock_is_missing(fake_redis):
    event_id = "evt-missing-lock"

    mark_status = dedupe.mark_event_processed(event_id, "owner-token")

    assert mark_status == dedupe.EVENT_CLAIM_LOST_OWNERSHIP
    assert fake_redis.exists(dedupe.event_key(event_id)) == 0


def test_old_owner_does_not_remove_new_lock_after_expiration(fake_redis):
    event_id = "evt-old-owner"
    fake_redis.set(dedupe.event_lock_key(event_id), "old-token", nx=True, ex=60)
    fake_redis.advance_time(61)
    fake_redis.set(dedupe.event_lock_key(event_id), "new-token", nx=True, ex=60)

    dedupe.release_event_claim(event_id, "old-token")

    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "new-token"


def test_acquire_event_claim_returns_unavailable_on_redis_failure(monkeypatch, fake_redis):
    def failing_exists(key):
        raise RuntimeError("Redis unavailable")

    monkeypatch.setattr(fake_redis, "exists", failing_exists)

    status, token = dedupe.acquire_event_claim("evt-redis-failure")

    assert status == dedupe.EVENT_CLAIM_UNAVAILABLE
    assert token is None


def test_mark_event_processed_returns_unavailable_on_redis_failure(fake_redis):
    event_id = "evt-mark-redis-failure"
    fake_redis.set(dedupe.event_lock_key(event_id), "owner-token", nx=True, ex=60)
    fake_redis.raise_on_eval = True

    status = dedupe.mark_event_processed(event_id, "owner-token")

    assert status == dedupe.EVENT_CLAIM_UNAVAILABLE
    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "owner-token"
    assert fake_redis.exists(dedupe.event_key(event_id)) == 0


def test_release_event_claim_suppresses_redis_failure(fake_redis):
    event_id = "evt-release-redis-failure"
    fake_redis.set(dedupe.event_lock_key(event_id), "owner-token", nx=True, ex=60)
    fake_redis.raise_on_eval = True

    dedupe.release_event_claim(event_id, "owner-token")

    assert fake_redis.get(dedupe.event_lock_key(event_id)) == "owner-token"


def test_shared_fake_redis_eval_marks_processed_atomically():
    redis = FakeRedis()
    event_id = "evt-shared-fake-eval"
    lock_key = dedupe.event_lock_key(event_id)
    processed_key = dedupe.event_key(event_id)

    redis.set(lock_key, "owner-token", nx=True, ex=60)

    result = redis.eval(
        dedupe._MARK_EVENT_PROCESSED_SCRIPT,
        2,
        lock_key,
        processed_key,
        "owner-token",
        dedupe.EVENT_PROCESSED_TTL_SECONDS,
        dedupe.EVENT_PROCESSED_VALUE,
    )

    assert result == 1
    assert redis.get(processed_key) == dedupe.EVENT_PROCESSED_VALUE
    assert redis.ttls[processed_key] == dedupe.EVENT_PROCESSED_TTL_SECONDS
    assert redis.exists(lock_key) == 0
