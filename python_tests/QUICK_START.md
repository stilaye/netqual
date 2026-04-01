# Quick Start — Apple QE pytest Framework

---

## Setup

```bash
source apple_qe_env/bin/activate
pip install -r requirements.txt
pre-commit install          # one-time: enable git hooks
```

---

## Run Tests

```bash
# CI-safe — no network, no sudo (86 tests)
pytest -m "not network and not requires_sudo" -v

# All tests
pytest -v

# Specific test file
pytest tests/test_sysdiagnose_analysis.py -v
pytest tests/test_bonjour_discovery.py -v
pytest tests/test_opendrop.py -v
pytest tests/test_network_conditioning.py -v

# By marker
pytest -m security -v
pytest -m protocol -v
pytest -m performance -v
pytest -m smoke -v

# Skip network only
pytest --offline -v

# Skip sudo only
pytest --no-sudo -v

# Parallel
pytest -n auto

# With coverage
pytest --cov=. --cov-report=html --cov-report=term
```

---

## Sysdiagnose Analysis (Real Device)

```bash
# Uses bundled iPhone AirDrop capture automatically
pytest tests/test_sysdiagnose_analysis.py -v

# Point at your own capture
SYSDIAGNOSE_PATH=/path/to/sysdiagnose_root pytest tests/test_sysdiagnose_analysis.py -v
```

---

## Network Conditioning

```bash
# Offline validation (no sudo)
pytest tests/test_network_conditioning.py -m "not requires_sudo" -v

# Live conditioning — requires: brew install comcast + sudo
pytest tests/test_network_conditioning.py -v
```

---

## Lint & Format

```bash
ruff check .              # lint check
ruff check . --fix        # auto-fix
black --check .           # format check
black .                   # auto-format
pre-commit run --all-files  # run all hooks
```

---

## Environment & Config

```bash
pytest --env=staging -v          # staging config
pytest --env=production -v       # production config
TEST_CONFIG_FILE=my.json pytest  # external JSON config
DEVICE_CONFIG_FILE=lab.yaml pytest  # custom device inventory
```

---

## Key Fixtures

```python
def test_example(
    ssl_context,         # SSLContext — TLS 1.2+
    tcp_socket,          # TCP socket with auto-cleanup
    udp_socket,          # UDP socket with auto-cleanup
    http_client,         # httpx.Client
    logger,              # logging.Logger
    test_config,         # {"api_base_url": ..., "network_timeout": 10, ...}
    device_config,       # {"dut": [...], "reference": [...], "auxiliary": [...]}
    sysdiagnose_path,    # Path to sysdiagnose bundle, or None
    measure_time,        # context manager for timing
    comcast_conditioner, # ComcastConditioner — requires sudo
    nlc_conditioner,     # NLCConditioner — offline profile builder
):
```

---

## Custom Markers

```python
@pytest.mark.network        # requires live network
@pytest.mark.security       # SSL/TLS/privacy
@pytest.mark.protocol       # mDNS, BLE, sockets
@pytest.mark.performance    # timing benchmarks
@pytest.mark.slow           # > 1 second
@pytest.mark.integration    # multi-component
@pytest.mark.smoke          # critical path
@pytest.mark.regression     # bug fix regression
@pytest.mark.requires_sudo  # comcast/pfctl
```

---

## Write a Test

```python
import pytest
from utils.sysdiagnose_parser import SysdiagnoseParser
from utils.network_conditioner import PROFILES

class TestMyProtocol:

    @pytest.mark.protocol
    def test_offline_example(self):
        """Validate something without a network."""
        result = some_calculation()
        assert result == expected, "Clear failure message"

    @pytest.mark.network
    def test_network_example(self, test_config):
        """Validate a live network call."""
        timeout = test_config["network_timeout"]
        # ... make request with timeout ...

    def test_real_device_example(self, sysdiagnose_path):
        """Validate from a real sysdiagnose capture."""
        if sysdiagnose_path is None:
            pytest.skip("No sysdiagnose bundle — set SYSDIAGNOSE_PATH")
        parser = SysdiagnoseParser(sysdiagnose_path)
        awdl = parser.awdl()
        assert awdl.data_duration_ms > 0

    def test_device_pair_example(self, device_config):
        """Run against DUT + reference device."""
        if not device_config["dut"]:
            pytest.skip("No DUT configured in device_config.yaml")
        dut = device_config["dut"][0]
        assert dut["ip_address"]

    @pytest.mark.requires_sudo
    @pytest.mark.network
    def test_conditioning_example(self, comcast_conditioner, test_config):
        """Test under degraded network (3G profile)."""
        with comcast_conditioner.profile("3g"):
            # test runs under 1 Mbps / 200 ms / 2% loss
            pass
```

---

## Documents

| Doc | What it covers |
|-----|----------------|
| [`docs/ENTERPRISE_FRAMEWORK_GUIDE.md`](docs/ENTERPRISE_FRAMEWORK_GUIDE.md) | Full framework architecture |
| [`docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md`](docs/SYSDIAGNOSE_ANALYSIS_GUIDE.md) | AirDrop sysdiagnose — collection, parsing, real findings |
| [`docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md`](docs/OPENDROP_TECHNOLOGY_ASSESSMENT.md) | OpenDrop status + pymobiledevice3/XCTest roadmap |
| [`docs/TECH_DEBT.md`](docs/TECH_DEBT.md) | 12 resolved debt items |
| [`docs/FILE_INDEX.md`](docs/FILE_INDEX.md) | Every file described |
