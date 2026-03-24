# NetQual CLI — Cheat Sheet

```
python netqual.py <command> [options]
```

---

## Commands at a Glance

| Command | What it does |
|---------|-------------|
| `log <file>` | Parse and analyze a network diagnostic log |
| `pcap <file>` | Analyze a packet capture with tshark |
| `simulate` | Run an AirDrop/NameDrop protocol simulation |
| `opendrop` | Real AirDrop via OpenDrop CLI |
| `test` | Run the full test suite (60 tests) |
| `all` | log + simulate + test in one shot |

---

## `netqual log` — Log Parser

```bash
# Basic parse (all levels, all components)
python netqual.py log sample_logs/network_diag.log

# Filter by severity level
python netqual.py log sample_logs/network_diag.log --level ERROR
python netqual.py log sample_logs/network_diag.log --level WARNING
python netqual.py log sample_logs/network_diag.log --level DEBUG

# Filter by component
python netqual.py log sample_logs/network_diag.log --component DNS
python netqual.py log sample_logs/network_diag.log --component TLS BLE
python netqual.py log sample_logs/network_diag.log --component AWDL mDNS NFC

# JSON output (pipe to file or jq)
python netqual.py log sample_logs/network_diag.log --json
python netqual.py log sample_logs/network_diag.log --json > report.json

# Combine filters
python netqual.py log sample_logs/tls_handshake.log --level ERROR --component TLS --json
```

**Detected patterns:** DNS timeout (P1), TLS cert failure (P0), TLS downgrade (P0),
BLE interval drift (P2), AWDL peer timeout (P1), SharePlay sync drift (P2),
Slow HTTP (P2), Handshake abort (P0), mDNS no response (P1), NFC error (P1)

---

## `netqual pcap` — Packet Capture Analyzer

```bash
# Full analysis of a .pcap file (requires tshark)
python netqual.py pcap capture.pcap

# Analyze a .logdump file (from btsnoop)
python netqual.py pcap bluetooth.logdump

# Print all tshark commands used (no file needed)
python netqual.py pcap --commands

# Install tshark if missing
brew install wireshark
```

**7 analyses run automatically:** TLS handshakes, DNS queries, mDNS/Bonjour,
BLE advertisements, TCP retransmissions, HTTP/2 streams, traffic statistics

---

## `netqual simulate` — Protocol Simulator

```bash
# AirDrop file transfer (full 7-step protocol)
python netqual.py simulate --scenario transfer

# BLE discovery only (no file transfer)
python netqual.py simulate --scenario discovery

# NameDrop contact exchange (NFC + BLE)
python netqual.py simulate --scenario namedrop

# Simulated failure (AWDL timeout)
python netqual.py simulate --scenario failure

# Run simulation AND pipe output through log parser
python netqual.py simulate --scenario transfer --parse
python netqual.py simulate --scenario namedrop --parse
```

**Scenarios simulate:** BLE advertisement → mDNS discovery → contact resolution
→ AWDL channel setup → TLS 1.3 handshake → file transfer → session cleanup

---

## `netqual opendrop` — Real AirDrop (macOS only)

```bash
# Check if OpenDrop is installed and awdl0 is available
python netqual.py opendrop preflight

# Discover nearby AirDrop devices (default 15s timeout)
python netqual.py opendrop discover
python netqual.py opendrop discover --timeout 30

# Send a file to a specific device
python netqual.py opendrop send --file photo.heic --target "iPhone"
python netqual.py opendrop send --file video.mov --target "MacBook Pro" --timeout 60

# Receive files (listen mode)
python netqual.py opendrop receive
python netqual.py opendrop receive --output /tmp/drops --timeout 120

# Run action AND pipe session log through log_parser
python netqual.py opendrop discover --parse
python netqual.py opendrop send --file photo.heic --target "iPhone" --parse

# Save raw OpenDrop output to file
python netqual.py opendrop discover --output session.log
```

**Prerequisites:**
```bash
pip install opendrop          # Install OpenDrop
python netqual.py opendrop preflight  # Verify setup
# Set target device AirDrop to "Everyone"
```

---

## `netqual test` — Test Suite

```bash
# Run all 60 tests with verbose output
python netqual.py test

# Or use pytest directly (more control)
cd netqual/
pytest -v                             # All 60 tests
pytest -v test_log_parser.py          # 17 log parser tests
pytest -v test_pcap_parser.py         # 12 pcap parser tests
pytest -v test_opendrop.py            # 31 OpenDrop tests
pytest -v -k "not Real"               # Skip hardware-gated tests
pytest -v -k "Tier1 or Preflight"     # Only mocked tests

# With Allure reporting
pytest --alluredir=allure-results
allure serve allure-results
```

---

## `netqual all` — Full Run

```bash
# Run log analysis + simulation + all tests in sequence
python netqual.py all
```

---

## Flags Reference

| Flag | Commands | Description |
|------|----------|-------------|
| `--level LEVEL` | `log` | Filter by log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--component X [Y]` | `log` | Filter by component(s): `DNS`, `TLS`, `BLE`, `AWDL`, `mDNS`, `NFC` |
| `--json` | `log` | Output structured JSON instead of formatted text |
| `--commands` | `pcap` | Print all tshark filter strings (no file needed) |
| `--scenario S` | `simulate` | Scenario: `transfer`, `discovery`, `namedrop`, `failure` |
| `--parse` | `simulate`, `opendrop` | Pipe session output through `log_parser` |
| `--file PATH` | `opendrop send` | File to send via AirDrop |
| `--target NAME` | `opendrop send` | Target device name (partial match OK) |
| `--timeout N` | `opendrop` | Override default timeout in seconds |
| `--output PATH` | `opendrop` | Save raw output to file / receive directory |

---

## Sample Files

```
sample_logs/
├── network_diag.log       # Mixed DNS, TLS, BLE, AWDL, mDNS events
├── tls_handshake.log      # TLS-focused log with failures
└── airdrop_session.log    # AirDrop-specific session trace

sample_files/
├── photo_1mb.heic         # Small — quick send tests
├── photo_4mb.heic         # Medium — throughput tests
└── video_50mb.mov         # Large — timeout and reliability tests
    (populate via: dd if=/dev/urandom of=sample_files/photo_1mb.heic bs=1m count=1)
```

---

## Quick Troubleshooting

| Problem | Fix |
|---------|-----|
| `tshark: command not found` | `brew install wireshark` |
| `opendrop: command not found` | `pip install opendrop` |
| `awdl0 not found` | Enable Wi-Fi; AWDL only available on macOS |
| `No devices found` | Set target AirDrop to "Everyone"; run `opendrop preflight` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Tests fail on import | `pip install -r requirements.txt` (check `pyyaml` is installed) |
