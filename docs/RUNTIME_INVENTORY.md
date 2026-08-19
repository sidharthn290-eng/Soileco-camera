# Current runtime inventory

This is an observed runtime inventory, not a source-code import or a cloud
deployment claim. Recheck it before changing the Pi.

| Item | Observed value |
| --- | --- |
| Device hostname | `SoilecoCAM1` |
| Platform | Raspberry Pi 4, Debian 13, arm64 |
| Dashboard service | `soileco-yolo-stream.service` |
| Service source | `/home/pi/soileco-yolo/soileco_yolo_stream.py` |
| Service port | `8080` |
| Python environment | `/home/pi/soileco-yolo/.venv` |
| Primary camera path | `/dev/v4l/by-id/usb-046d_C270_HD_WEBCAM_E8AE4D60-video-index0` |
| LiDAR | RPLIDAR A1M8 via CP2102 USB-UART, normally `/dev/ttyUSB0` |
| Local event data | `/home/pi/soileco-yolo/events.sqlite3` |
| Model currently loaded | `yolo11n.pt` |

## Last health-check evidence

- Dashboard service: active.
- Both USB camera error fields: `None`.
- LiDAR state: scanning, with 155 points reported during the check.
- Pi power-throttle status: `0x0`.
- ShellHub device: accepted and reachable through the authenticated web
  terminal.

## Source migration rule

The running Pi source must be copied into this repository only after a
read-only inventory, checksum record, secret scan, and service-preserving
backup. Do not overwrite the known working dashboard during a documentation
or cloud-tunnel change.
