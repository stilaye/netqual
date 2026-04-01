# Sysdiagnose Analysis Guide — AirDrop Protocol Validation

**Author:** Swapnil Tilaye
**Reference capture:** `sysdiagnose_2026.03.31_07-04-51-0700_iPhone-OS_iPhone_23D8133`
**Device:** iPhone | **Event:** Live AirDrop session

---

## What Is a Sysdiagnose?

A sysdiagnose is a full-system diagnostic snapshot Apple's OS takes on demand.
It captures kernel state, daemon logs, Wi-Fi/BLE/network status, security state,
and crash reports — all frozen at the moment of capture.

For protocol QE, it is **ground truth**: not simulation, not a mock — actual device
behaviour during a real protocol session.

### How to Collect One (iPhone)

```
Simultaneously press:  Volume Up + Volume Down + Side Button (hold 1–2 sec)
```

The device vibrates and saves a `.tar.gz` to:

```
Settings → Privacy & Security → Analytics & Improvements → Analytics Data
```

Or via Xcode: **Window → Devices and Simulators → Download Logs**

Extract with:

```bash
tar -xzf sysdiagnose_*.tar.gz
```

---

## AirDrop Protocol Stack (Top-Down)

```
[BLE Advertisement]  →  [AWDL Peer Discovery]  →  [mDNS ._airdrop._tcp.local]
        ↓                        ↓                           ↓
  SHA-256 hash             Channel election             TLS mutual auth
  of phone/email           (master/slave)               (cert-based identity)
        ↓                        ↓                           ↓
  "Contacts Only"          ch6 ↔ ch149               sharingd file transfer
  filter gate              (2.4 GHz / 5 GHz)          over AWDL + TCP
```

---

## Key Files in a Sysdiagnose Bundle

```
sysdiagnose_root/
├── system_logs.logarchive       ← ALL daemon logs (query with `log show`)
├── security-sysdiagnose.txt     ← TLS certs, SecTrustEvaluate (1.6 MB)
├── WiFi/
│   ├── awdl_status.txt          ← AWDL master/peer/channel/Data state ← PRIMARY
│   ├── bluetooth_status.txt     ← BLE devices, MAC, scan state         ← PRIMARY
│   ├── ifconfig.txt             ← awdl0 interface + IPv6
│   ├── wifi_datapath-PRE.txt    ← WiFi datapath before sysdiagnose
│   └── wifi_datapath-POST.txt   ← WiFi datapath after
└── logs/Networking/
    ├── netstat.txt              ← Active sockets (579 KB)
    └── skywalk.txt              ← Apple in-kernel bypass networking (607 KB)
```

---

## AWDL Analysis (`WiFi/awdl_status.txt`)

### What to Look For

| Field | Expected (AirDrop) | What It Means |
|-------|--------------------|---------------|
| `awdl is enabled` | Present | AWDL daemon is running |
| `awdl mode = AUTO` | AUTO | Activates on-demand, not always-on |
| `AirDrop Discoverable Mode` | `Contacts Only` | SHA-256 hash filter active |
| `awdl master channel` | 1–13 (2.4 GHz) | Primary slot channel (typically ch6) |
| `awdl secondary master channel` | 36–165 (5 GHz) | Secondary slot (typically ch149 DFS) |
| `awdl state: master` | master or slave | This device won/lost election |
| `awdl encryption is DISABLED` | DISABLED | Expected — TLS above handles security |
| `# of Peers Discovered` | ≥ 1 | At least one AirDrop peer found |
| `Data` state duration | > 0 ms | Bytes were actually transferred |
| `Rx Bytes / Tx Bytes` | > 0 | Confirms real traffic |

### Real Capture Findings

From `sysdiagnose_2026.03.31_07-04-51-0700`:

```
AWDL enabled:         Yes
Mode:                 AUTO
Discoverable Mode:    Contacts Only         ← BLE hash filter active
Master channel:       6   (2.4 GHz)
Secondary channel:    149 (5 GHz DFS)
Election state:       master [9E:E9:95:BA:D8:79]  ← Device won election
Peers discovered:     1                     ← One active AirDrop peer
Data state duration:  5,194 ms              ← ~5.2 sec of real file transfer
Rx Bytes:             17,471
Tx Bytes:             4,384
awdl0 IPv6:           fe80::b86c:d6ff:fe70:5a5c   ← Link-local, correct
Encryption:           DISABLED              ← Expected — TLS above it
```

### AWDL Channel Hopping Explained

AWDL uses **alternating time slots** to coexist with infrastructure Wi-Fi:

```
Slot sequence:  149 149 149 0 0 0 0 0 6 149 149 0 0 0 0 0
                └── 5 GHz ───────────┘  └2G┘ └── 5 GHz ──┘
```

- `6` = 2.4 GHz channel 6 (overlaps with infrastructure)
- `149` = 5 GHz DFS channel (less congested)
- `0` = no AWDL transmission in this slot (yields to Wi-Fi)

---

## BLE Analysis (`WiFi/bluetooth_status.txt`)

### What to Look For

| Field | Expected (AirDrop) | What It Means |
|-------|--------------------|---------------|
| `Power: On` | On | BLE must be on for discovery |
| `Discoverable: No` | No | Classic BT discovery off; AirDrop uses BLE, not classic BT |
| `Scanning: No` | No (at rest) | Scanning happens only during discovery phase |
| MAC Address | Valid XX:XX:XX:XX:XX:XX | Device identity |

### AirDrop BLE Flow

```
1. sharingd triggers BLE scan for UUID 0x7C7D (AirDrop service UUID)
2. Receives BLE advertisement containing:
   └── Apple Company ID: 0x004C
   └── Action byte:      0x05 (AirDrop)
   └── 22-bit truncated SHA-256 of sender's phone/email
3. Hash matches contact → device becomes visible → AWDL takes over
```

### SHA-256 "Contacts Only" Privacy Gate

```python
# How the 22-bit truncated hash is generated:
import hashlib
phone = "+15551234567"
full_hash = hashlib.sha256(phone.encode()).digest()   # 32 bytes
truncated = full_hash[:2]   # First 2 bytes = 16 bits broadcast in BLE
                             # (Apple uses 22 bits internally)
```

**Privacy research note:**
- 22-bit truncation = only ~4 million possible values
- US phone numbers = 10 billion possible → brute-forceable in minutes
- Published research: **PrivateDrop (2021)**, **AirGuard** demonstrate this
- Apple has not addressed the truncation attack vector as of iOS 18

---

## TLS Security Model (`security-sysdiagnose.txt`)

| Layer | Detail |
|-------|--------|
| Protocol | TLS 1.3 (mutual authentication) |
| Certificates | Self-signed, generated per-device by `sharingd` |
| Identity | Tied to iCloud account (AppleID-linked cert) |
| Validation | `SecTrustEvaluate` — full certificate chain check |
| "Contacts Only" | TLS identity checked against contact hashes BEFORE handshake |
| Failure mode | Handshake aborted → "not in contacts" UI shown |

> **Design principle:** AWDL is an unencrypted transport layer.
> TLS 1.3 with mutual auth is the security layer — applied per-session by `sharingd`.

---

## Skywalk — Kernel Networking Bypass (`logs/Networking/skywalk.txt`)

Skywalk is Apple's **in-kernel networking bypass** (introduced iOS 12 / macOS Catalina):

```
Traditional path:   sharingd → BSD socket → kernel → awdl0 driver
Skywalk path:       sharingd → Skywalk channel → awdl0 driver  (no userspace copies)
```

- Removes userspace ↔ kernel memory copies
- Reduces AirDrop transfer latency
- AirDrop file chunks flow: `sharingd → Skywalk channel → awdl0 driver`

---

## `log show` Commands — AirDrop Timeline

```bash
# 1. Full AirDrop pipeline (BLE + AWDL + sharingd) around the transfer window
log show --archive system_logs.logarchive \
  --predicate 'process == "sharingd" OR subsystem == "com.apple.awdl" OR process == "bluetoothd"' \
  --info --start "2026-03-31 06:50:00" --end "2026-03-31 07:10:00" \
  | tee /tmp/airdrop_pipeline.log

# 2. sharingd only — file transfer daemon
log show --archive system_logs.logarchive \
  --predicate 'process == "sharingd"' --info > /tmp/sharingd.log

# 3. AWDL subsystem — peer election and channel management
log show --archive system_logs.logarchive \
  --predicate 'subsystem == "com.apple.awdl"' --info | head -300

# 4. TLS events — handshake, cert validation
log show --archive system_logs.logarchive \
  --predicate 'subsystem BEGINSWITH "com.apple.network" AND message CONTAINS "TLS"' --info

# 5. BLE AirDrop UUID scan — confirms BLE discovery phase
log show --archive system_logs.logarchive \
  --predicate 'process == "bluetoothd" AND message CONTAINS "7C7D"' --info

# 6. Contact hash matching — "Contacts Only" gate
grep -i "hash\|record\|truncat\|contact" /tmp/sharingd.log

# 7. Open full timeline in Console.app for visual inspection
open /tmp/airdrop_pipeline.log
```

---

## Using This in the Test Framework

### Automated tests (offline, no device needed)

```bash
# Run sysdiagnose analysis tests against the real capture
pytest tests/test_sysdiagnose_analysis.py -v

# Point at a different bundle
SYSDIAGNOSE_PATH=/path/to/other/sysdiagnose pytest tests/test_sysdiagnose_analysis.py -v
```

### Parser utilities

```python
from utils.sysdiagnose_parser import SysdiagnoseParser

parser = SysdiagnoseParser("path/to/sysdiagnose_root/")

awdl = parser.awdl()
print(awdl.data_duration_ms)    # 5194 — transfer happened
print(awdl.discoverable_mode)   # "Contacts Only"
print(awdl.election_state)      # "master"

ble = parser.bluetooth()
print(ble.power)                # "On"
print(ble.mac_address)          # "28:34:ff:57:12:66"
```

### Test assertions written from this capture

| Test | What It Validates | Source File |
|------|-------------------|-------------|
| `test_awdl_was_enabled` | AWDL daemon running | awdl_status.txt |
| `test_awdl_data_state_occurred` | Real transfer happened (5,194 ms) | awdl_status.txt |
| `test_awdl_peer_was_discovered` | 1 peer found | awdl_status.txt |
| `test_awdl_discoverable_mode_is_contacts_only` | Privacy gate active | awdl_status.txt |
| `test_awdl_encryption_is_disabled_at_transport_layer` | TLS above, not AWDL | awdl_status.txt |
| `test_awdl_master_channel_is_valid_wifi_channel` | ch6 = valid 2.4 GHz | awdl_status.txt |
| `test_awdl_secondary_channel_is_5ghz` | ch149 = valid 5 GHz DFS | awdl_status.txt |
| `test_awdl_ipv6_is_link_local` | fe80:: — correct for awdl0 | awdl_status.txt |
| `test_bluetooth_was_on` | BLE available for discovery | bluetooth_status.txt |
| `test_bluetooth_mac_is_valid` | Valid 48-bit MAC | bluetooth_status.txt |
| `test_bluetooth_not_discoverable_in_contacts_only_mode` | Classic BT off | bluetooth_status.txt |
| `test_full_pipeline_evidence` | BLE on + Data state > 0 | both |
| `test_contacts_only_privacy_gate_active` | Hash filter confirmed | both |
| `test_dual_band_channel_strategy` | ch6 + ch149 coexistence | awdl_status.txt |

---

## Key Learnings Summary

1. **AWDL master election won** — Device elected master (`metric 0x73 vs top 0x1fe`),
   meaning it controlled the channel schedule for the session.

2. **Real transfer confirmed** — `._airdrop._tcp.local` browsed, 1 peer discovered,
   5,194 ms of Data state = bytes actually exchanged.

3. **"Contacts Only" gate active** — Discoverable mode confirmed in `awdl_status.txt`;
   BLE advertisement carried truncated SHA-256 hashes for contact matching.

4. **AWDL is not the security layer** — `awdl encryption is DISABLED` is correct and
   expected; TLS 1.3 with mutual cert auth is the security mechanism.

5. **Dual-band channel hopping** — ch6 (2.4 GHz) + ch149 (5 GHz DFS) in alternating
   slots; AWDL avoids infrastructure Wi-Fi congestion while maintaining sync.

6. **Privacy research awareness** — 22-bit truncation in BLE advertisement is a known
   attack surface (PrivateDrop / AirGuard papers); relevant for security test design.
