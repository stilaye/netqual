# Technical Debt Register
**Project:** Apple QE Portfolio — Python Test Framework
**Last Updated:** 2026-03-29
**Audit Basis:** Framework quality review against: Maintainable, Scalable, Configurable, Simple, Modular, Readable, Debuggable

---

## Summary

| Quality Pillar | Current Score | Primary Gap |
|----------------|--------------|-------------|
| Maintainable | 6/10 | Duplicate helper code, hardcoded config |
| Scalable | 5/10 | No parametrization, no parallel-safe fixtures |
| Configurable | 5/10 | No config file support, hardcoded timeouts |
| Simple | 6/10 | Overstuffed functions, deep nesting |
| Modular | 5/10 | Test helpers trapped inside test files |
| Readable | 7/10 | Inconsistent assertion messages, missing byte docs |
| Debuggable | 5/10 | Silent failures, missing assertion messages |

---

## Open Debt Items

### TD-001 — Extract MDNSHelper into utils/
**Pillar:** Modular
**Priority:** High
**File:** `tests/test_bonjour_discovery.py:15–80`

`MDNSHelper` (packet build, parse, multicast send) lives inside the test file. Any future test that needs mDNS utilities must duplicate it or import from a test file — both are wrong.

**Fix:**
```
Create utils/mdns_helpers.py
Move MDNSHelper class there
Update test_bonjour_discovery.py to import from utils.mdns_helpers
```

---

### TD-002 — Extract OpenDrop helpers into utils/
**Pillar:** Modular, Maintainable
**Priority:** High
**File:** `tests/test_opendrop.py:25–60`

`_contact_hash`, `_build_discover_request`, `_parse_discover_response`, `_build_ble_advertisement` are private helper functions inside the test file. They duplicate logic already present in `utils/test_data_factory.py` and cannot be reused by other tests.

**Fix:**
```
Create utils/opendrop_helpers.py
Move all four helpers there (public names, no underscore prefix)
Update test_opendrop.py imports
Delete duplicated logic
```

---

### TD-003 — Silent PermissionError in mDNS send_query()
**Pillar:** Debuggable
**Priority:** High
**File:** `tests/test_bonjour_discovery.py:~110`

`send_query()` catches `PermissionError` and returns an empty list with no log output. A test running on a machine without multicast permissions silently passes instead of surfacing the root cause.

**Fix:**
```python
except PermissionError as e:
    logger.warning(
        "PermissionError in send_query('%s'): %s — "
        "multicast requires elevated privileges or --offline flag", name, e
    )
    return []
```

---

### TD-004 — Silent subprocess failure in ComcastConditioner.apply()
**Pillar:** Debuggable
**Priority:** High
**File:** `utils/network_conditioner.py:~100`

If `subprocess.run(cmd, check=True)` raises `CalledProcessError`, the stderr from `comcast` is lost. The test gets an opaque Python traceback with no indication of what `pfctl`/`dnctl` actually reported.

**Fix:**
```python
except subprocess.CalledProcessError as e:
    logger.error(
        "comcast failed (exit %d): %s",
        e.returncode,
        e.stderr.decode(errors="replace") if e.stderr else "(no stderr)"
    )
    raise
```

---

### TD-005 — Assertion messages missing across test files
**Pillar:** Debuggable, Readable
**Priority:** High
**Files:** `tests/test_network_protocols.py`, `tests/test_opendrop.py`, `tests/test_bonjour_discovery.py`

Most `assert` statements have no message. When a test fails in CI the output is just `AssertionError` with no context. Example:

```python
# Current — unhelpful on failure
assert ssock.version() == "TLSv1.3"

# Fixed — shows actual vs expected
assert ssock.version() == "TLSv1.3", (
    f"Expected TLSv1.3 but got {ssock.version()}. "
    "Check apple.com TLS configuration."
)
```

**Scope:** ~25 assertions across 3 test files need messages added.

---

### TD-006 — Hardcoded timeouts in test files
**Pillar:** Configurable
**Priority:** Medium
**Files:** `tests/test_network_protocols.py` (timeout=10 appears in multiple tests)

Timeouts are magic numbers scattered across test methods. Running on a slow CI runner or under a network conditioning profile requires manual edits to every occurrence.

**Fix:**
```python
# conftest.py — already has test_config; add timeout key
cfg["network_timeout"] = int(os.getenv("TEST_NETWORK_TIMEOUT", 10))

# test files — use fixture
def test_tls_handshake(self, test_config):
    with socket.create_connection(("apple.com", 443),
                                   timeout=test_config["network_timeout"]):
        ...
```

---

### TD-007 — retry log level is WARNING instead of DEBUG
**Pillar:** Debuggable
**Priority:** Medium
**File:** `utils/network_helpers.py:43–50`

Retry attempts are logged at `WARNING`. WARNING implies something unexpected is happening. A retry is an expected, transient event and should be `DEBUG` so it doesn't pollute CI logs.

**Fix:**
```python
# Before
logger.warning(f"Attempt {attempt+1} failed: {e}")

# After
logger.debug("Connection attempt %d/%d to %s:%d failed: %s",
             attempt + 1, self.retry_count, host, port, e)
```

---

### TD-008 — No parametrization on host-specific tests
**Pillar:** Scalable
**Priority:** Medium
**File:** `tests/test_network_protocols.py`

Tests like `test_dns_resolves_apple_services` hardcode `["apple.com", "icloud.com"]` inline. Adding a new domain means editing the test body. Parametrization would let the domain list live in config.

**Fix:**
```python
@pytest.mark.parametrize("host", ["apple.com", "icloud.com", "me.com"])
@pytest.mark.network
def test_dns_resolves_apple_services(self, host):
    result = socket.getaddrinfo(host, None)
    assert result, f"DNS resolution failed for {host}"
```

---

### TD-009 — ssl_context fixture is session-scoped but not thread-safe
**Pillar:** Scalable
**Priority:** Medium
**File:** `conftest.py:~180`

`ssl_context` is `scope="session"` — one instance shared across all tests. `SSLContext` objects are not documented as thread-safe. Under `pytest-xdist` parallel execution this can cause intermittent failures.

**Fix:**
```python
@pytest.fixture  # function-scoped — cheap to create, safe under -n auto
def ssl_context() -> ssl.SSLContext:
    ...
```

---

### TD-010 — conftest.py mixes hooks and fixtures in one file
**Pillar:** Modular, Maintainable
**Priority:** Low
**File:** `conftest.py`

Pytest hooks (`pytest_configure`, `pytest_addoption`, `pytest_collection_modifyitems`, `pytest_runtest_setup`) and fixtures (`ssl_context`, `tcp_socket`, etc.) all live in one 420-line file. As the framework grows this becomes hard to navigate.

**Fix:**
```
conftest.py              ← hooks only (pytest_configure, addoption, etc.)
conftest_fixtures.py     ← all @pytest.fixture definitions
conftest_conditioner.py  ← comcast_conditioner, nlc_conditioner fixtures
```
Note: pytest only auto-discovers `conftest.py` — fixtures must be imported explicitly or via plugin.

---

### TD-011 — byte layout docs incomplete in OpenDrop helpers
**Pillar:** Readable
**Priority:** Low
**File:** `tests/test_opendrop.py:65–90`

`_build_ble_advertisement` has a comment block but it doesn't fully document each byte offset. A reader must mentally parse the struct pack to understand the layout.

**Fix:** Add a full byte-map docstring (see TD-002 — this debt is resolved when helpers are extracted to `utils/opendrop_helpers.py` with proper docs).

---

### TD-012 — pytest.ini marker list has no usage guidance
**Pillar:** Readable, Maintainable
**Priority:** Low
**File:** `pytest.ini`

Markers are listed but there's no guidance on:
- Which markers can be combined
- Which require `--offline` or `--no-sudo`
- What the performance threshold for `@slow` is

**Fix:** Add inline comments to the markers block in `pytest.ini`.

---

## Completed Items

| ID | Description | Resolved In |
|----|-------------|-------------|
| — | `--offline` and `--no-sudo` flags added | Current session |
| — | `comcast_conditioner` / `nlc_conditioner` moved to conftest.py | Current session |
| — | `requires_sudo` marker registered in conftest + pytest.ini | Current session |
| — | `test_config` supports `TEST_CONFIG_FILE`, `TEST_API_BASE_URL`, `TEST_TIMEOUT` env vars | Current session |
| — | `--log-level` CLI flag + `TEST_LOG_LEVEL` env var added | Current session |

---

## How to Contribute a Fix

1. Pick an open item by ID (e.g. TD-003)
2. Create a branch: `git checkout -b fix/td-003-mdns-permission-error`
3. Apply the fix described above
4. Run `pytest -m "not requires_sudo and not network"` — all offline tests must pass
5. Open a PR referencing the TD ID in the title
