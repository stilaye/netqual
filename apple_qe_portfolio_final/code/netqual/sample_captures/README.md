# Sample Captures — How to Generate Real pcap Files

## macOS Network Capture

```bash
# General network traffic (1000 packets)
sudo tcpdump -i en0 -w capture.pcap -c 1000

# mDNS / Bonjour only (port 5353)
sudo tcpdump -i en0 port 5353 -w mdns_capture.pcap

# TLS handshakes only (port 443)
sudo tcpdump -i en0 'tcp port 443' -w tls_capture.pcap

# AirDrop-related traffic (AWDL interface)
sudo tcpdump -i awdl0 -w airdrop_capture.pcap
```

## BLE / Bluetooth Capture

```bash
# macOS: Use PacketLogger.app (Xcode Additional Tools)
# Export as .logdump file

# Android: Enable btsnoop logging
# Settings > Developer Options > Enable Bluetooth HCI Snoop Log
# adb bugreport > extract btsnoop_hci.log

# Linux: Use btmon
sudo btmon -w btsnoop.log
```

## Analyze with NetQual

```bash
python netqual.py pcap capture.pcap
python netqual.py pcap mdns_capture.pcap
python netqual.py pcap btsnoop.log
python netqual.py pcap --commands    # Show all tshark commands
```
