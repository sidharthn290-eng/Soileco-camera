# Verified Pi source baseline

These files are a source-content baseline of the currently running
SoilecoCAM1 dashboard. The source files were verified by SHA-256 on
2026-08-19 before import.

| File | SHA-256 |
| --- | --- |
| `soileco_yolo_stream.py` | `f36d5d7d217ed0ae3a278a412d1d1e421418d59244dc7c2caf6e53c997c8a3f3` |
| `lidar_scan_test.py` | `05e8d78a269766e819e8e45fd1cd22d0164da257eb4ebb7e6e56b088c090a2e5` |

The live paths and raw source hashes were:

```text
/home/pi/soileco-yolo/soileco_yolo_stream.py
/home/pi/soileco-yolo/lidar_scan_test.py
```

Git stores a normalized final newline. Verification must therefore compare
source content after removing only terminal line-ending differences; it must
not claim raw-byte equality for the Git copy. The live raw hashes above remain
the authoritative evidence for the Pi snapshot.

This import does not change the live Pi systemd service, camera device paths,
LiDAR serial ownership, model, SQLite event database, or dashboard port. Any
runtime change must be developed and tested on a separate feature branch with
a documented backup and rollback step.
