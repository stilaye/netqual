# sample_files/

This directory holds test files used by the OpenDrop automated send tests
(referenced in `netqual_config.yaml` under `opendrop.test_files`).

Binary files are **not committed** to the repo. Add your own before running
hardware-gated Tier 2 tests:

```bash
# Option 1 — copy any files you have and rename them
cp ~/Desktop/photo.heic sample_files/photo_1mb.heic
cp ~/Desktop/large_photo.heic sample_files/photo_4mb.heic
cp ~/Desktop/clip.mov sample_files/video_50mb.mov

# Option 2 — generate dummy files for size testing (no real media needed)
dd if=/dev/urandom of=sample_files/photo_1mb.heic  bs=1m count=1
dd if=/dev/urandom of=sample_files/photo_4mb.heic  bs=1m count=4
dd if=/dev/urandom of=sample_files/video_50mb.mov  bs=1m count=50
```

## Expected files

| File | Size | Used by |
|------|------|---------|
| `photo_1mb.heic` | ~1 MB | `test_send_small_file` |
| `photo_4mb.heic` | ~4 MB | `test_send_medium_file` |
| `video_50mb.mov` | ~50 MB | `test_send_large_file` |

These files are only required for **Tier 2** hardware tests
(`@requires_opendrop`). All Tier 1 mocked tests run without them.
