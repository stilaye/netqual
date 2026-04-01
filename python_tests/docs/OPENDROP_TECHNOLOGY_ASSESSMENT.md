# OpenDrop — Technology Assessment & Modern Alternatives

**Status:** Research tool — not recommended for new enterprise QE work
**Decision:** Use protocol-level validation + pymobiledevice3 + sysdiagnose analysis
**Last reviewed:** 2026-03-31

---

## OpenDrop Status

| Property | Detail |
|----------|--------|
| Repository | https://github.com/seemoo-lab/opendrop |
| Last meaningful commit | **2021** (3+ years stale) |
| Python support | Python 3.8 only (no 3.9+ compatibility fixes) |
| Platform | Linux + macOS with OWL kernel patch |
| Maintainer | SEEMOO Lab, TU Darmstadt (research group) |
| Production use | ❌ Not intended for production |
| Enterprise use | ❌ Not supported |

### Why It Was Used Here

`test_opendrop.py` uses OpenDrop as a **protocol reference** — not as a running tool.
The tests validate the AirDrop protocol format (plist structure, BLE advertisement
byte layout, mDNS service record) using only Python stdlib (`plistlib`, `struct`,
`hashlib`). OpenDrop itself is never invoked at runtime.

### Why It Should Not Be a Runtime Dependency

1. **Abandoned** — No releases since 2021. Python 3.10+ compatibility is broken.
2. **Research-grade** — Requires OWL (Open Wireless Link), a kernel-patched AWDL
   userspace stack that is itself unmaintained.
3. **Root/kernel access** — Requires `CAP_NET_ADMIN` on Linux or SIP-disabled macOS.
4. **Fragile** — Breaks with Wi-Fi driver updates and macOS security patches.
5. **Not Apple-signed** — Cannot run on locked-down enterprise Macs without MDM exceptions.
6. **No CI support** — Cannot run in GitHub Actions, Buildkite, or any standard CI
   environment without custom kernel images.

---

## What This Framework Does Instead

### Current Approach — Valid for Enterprise QE

| What We Test | How We Test It | File |
|---|---|---|
| AirDrop `/Discover` plist format | `plistlib` — build + parse, no network needed | `test_opendrop.py` |
| BLE advertisement byte layout | `struct.pack` — exact byte-map validation | `test_opendrop.py` |
| mDNS service record format | Raw UDP packet construction | `test_opendrop.py` |
| Contact hash privacy (22-bit truncation) | `hashlib.sha256` — offline | `test_network_protocols.py` |
| AWDL state from real device | Sysdiagnose parser | `test_sysdiagnose_analysis.py` |
| TLS 1.3 enforcement | Live connection to apple.com | `test_network_protocols.py` |

This approach:
- ✅ Runs fully offline in CI
- ✅ No root / kernel access required
- ✅ Python 3.8–3.13 compatible
- ✅ Validates the same protocol spec OpenDrop implements
- ✅ Ground-truth validated against a real sysdiagnose capture

---

## Modern Alternatives for Enterprise Apple QE

### 1. pymobiledevice3 ⭐ Recommended

**What it is:** Actively maintained Python library for communicating with iOS/iPadOS
devices over USB and Wi-Fi using the same private protocols Xcode uses.

| Property | Detail |
|----------|--------|
| Repository | https://github.com/doronz88/pymobiledevice3 |
| Last commit | Active (weekly commits, 2024–2026) |
| Python | 3.9+ |
| Maintainer | doronz88 (independent, very active) |
| Capabilities | Syslog streaming, instruments, app install, crash reports, screenshots, booting simulator, tunneling |

```python
# Example: Stream sharingd logs in real time during an AirDrop test
from pymobiledevice3.services.os_trace import OsTraceService
from pymobiledevice3.lockdown import create_using_usbmux

lockdown = create_using_usbmux()
with OsTraceService(lockdown) as service:
    for entry in service.watch(process="sharingd"):
        print(entry["message"])
```

**Enterprise use cases:**
- Stream `sharingd` / `bluetoothd` / `awdld` logs during a live AirDrop test
- Collect sysdiagnose programmatically after a test failure
- Install a test app via `AppInstallService`
- Run Instruments traces via `DvtSecureSocketProxyService`

---

### 2. XCTest + xcodebuild (Official Apple)

**What it is:** Apple's official UI and unit test framework. The right tool
for testing AirDrop trigger UI, Handoff continuity, NameDrop flows, etc.

```bash
# Run a specific XCTest target against a connected device
xcodebuild test \
  -scheme AirDropUITests \
  -destination 'platform=iOS,id=<UDID>' \
  -resultBundlePath TestResults.xcresult

# Parse result bundle
xcrun xcresulttool get --format json --path TestResults.xcresult
```

**Enterprise use cases:**
- Tap "Accept" / "Decline" in the AirDrop prompt
- Verify Handoff activity appears on reference device
- Validate NameDrop contact card UI

---

### 3. xctrace (Instruments CLI)

**What it is:** CLI wrapper for Instruments. Records performance traces during
protocol sessions without opening the GUI.

```bash
# Record a 30-second networking trace during an AirDrop transfer
xctrace record \
  --device <UDID> \
  --template "Network" \
  --output airdrop_trace.trace \
  --time-limit 30s

# Export data
xctrace export --input airdrop_trace.trace --xpath '//network-activity-summary'
```

**Enterprise use cases:**
- Measure AirDrop throughput (Mbps) and latency
- Profile `sharingd` CPU/memory during transfer
- Detect TCP retransmissions or TLS handshake delays

---

### 4. log (macOS/iOS Unified Logging) — Already Partially Used

**What it is:** Apple's `log` CLI tool — queries `system_logs.logarchive`
from a sysdiagnose or streams live from a connected device.

```bash
# Live stream from connected iPhone (requires pymobiledevice3 tunnel or USB)
log stream \
  --predicate 'process == "sharingd" OR subsystem == "com.apple.awdl"' \
  --level info

# Query captured archive (our current approach)
log show --archive system_logs.logarchive \
  --predicate 'process == "sharingd"' \
  --info > /tmp/sharingd.log
```

**Already integrated:** `tests/test_sysdiagnose_analysis.py` validates
AWDL + BLE state from a real logarchive.

**Next step:** Add live log streaming via pymobiledevice3 for device-in-the-loop tests.

---

### 5. Network Framework + Swift Testing (Future)

Apple's `Network.framework` (Swift) is the modern replacement for BSD sockets
and the foundation for all Continuity/Sharing protocols on Apple platforms.

```swift
// Detect AirDrop service advertisement using NWBrowser
let browser = NWBrowser(
    for: .bonjour(type: "_airdrop._tcp", domain: "local"),
    using: .tcp
)
browser.browseResultsChangedHandler = { results, changes in
    for result in results {
        print("Found AirDrop peer: \(result.endpoint)")
    }
}
browser.start(queue: .main)
```

Relevant for: `swift_tests/SharingFeatureTests.swift` in this portfolio — see
the Swift test suite for current coverage.

---

## Decision Matrix

| Tool | Runtime Needed | CI-Safe | Real Device | Maintained | Recommended |
|------|---------------|---------|-------------|------------|-------------|
| **OpenDrop** | OWL kernel patch | ❌ | ❌ (Linux only) | ❌ Abandoned 2021 | ❌ |
| **Protocol tests (current)** | None (offline) | ✅ | ✅ (validates spec) | ✅ | ✅ |
| **Sysdiagnose parser (current)** | None (static files) | ✅ | ✅ (real data) | ✅ | ✅ |
| **pymobiledevice3** | USB/Wi-Fi device | ✅ (with device) | ✅ | ✅ Active | ✅ |
| **XCTest / xcodebuild** | Xcode + device | ✅ (Buildkite Mac) | ✅ | ✅ Official | ✅ |
| **xctrace** | Xcode CLI | ✅ (Mac CI) | ✅ | ✅ Official | ✅ |
| **log show / stream** | macOS CLI | ✅ | ✅ | ✅ Official | ✅ |

---

## Recommended Evolution Path for This Framework

```
Phase 1 (Current — done)
  ├── Protocol format tests     ← test_opendrop.py, test_bonjour_discovery.py
  ├── Network stack tests       ← test_network_protocols.py
  ├── Sysdiagnose analysis      ← test_sysdiagnose_analysis.py
  └── Network conditioning      ← test_network_conditioning.py

Phase 2 (Next — pymobiledevice3)
  ├── Live sharingd log streaming during AirDrop transfer
  ├── Programmatic sysdiagnose collection on test failure
  └── Device inventory validation (UDID, OS version, BT MAC)

Phase 3 (Device-in-the-loop)
  ├── XCTest: AirDrop prompt accept/decline automation
  ├── XCTest: NameDrop contact card validation
  ├── xctrace: AirDrop throughput benchmarks
  └── Multi-device matrix: iPhone ↔ Mac, iPhone ↔ iPad, etc.
```

---

## What To Tell Interviewers About OpenDrop

> "Our framework includes OpenDrop protocol tests, but we treat OpenDrop as a
> **protocol specification reference**, not a runtime tool. The tests validate
> the exact plist structure, BLE advertisement byte layout, and mDNS record format
> that OpenDrop documents — using only Python stdlib, with zero external dependencies.
>
> OpenDrop itself hasn't been updated since 2021 and requires a patched AWDL kernel
> stack that can't run in CI. For live device testing, the modern approach is
> **pymobiledevice3** for log streaming and device control, combined with
> **sysdiagnose analysis** for post-hoc protocol validation — which is exactly
> what `test_sysdiagnose_analysis.py` demonstrates using a real capture from my
> iPhone during an actual AirDrop session."
