# SoilEco Camera Vision Dev

An isolated development repository for the SoilEco Raspberry Pi camera and
LiDAR demonstration system. It is intentionally separate from the main Soil
Eco application and from ShellHub's device-management service.

## What is live today

| Component | Current location | Purpose | Exposure |
| --- | --- | --- | --- |
| Pi dashboard | `http://SoilecoCAM1:8080/` | Two USB-camera previews, motion-gated YOLO, event history and LiDAR scan view | Local network only |
| Pi status API | `http://SoilecoCAM1:8080/status` | Camera/LiDAR health and current observations | Local network only |
| Pi source | `/home/pi/soileco-yolo/` | Current running dashboard and systemd service | Pi-local; not yet imported into Git |
| ShellHub | `https://shellhub.soileco.dev/` | Maintenance SSH only | Authenticated administrators only |

The `SoilecoCAM1` hostname is preferred over a fixed IP address because its
LAN address can change. Do **not** expose the Pi's port `8080` to the public
internet.

## Planned addresses

| Address | Planned role | State |
| --- | --- | --- |
| `https://camera.soileco.dev` | Cloudflare Access-protected camera/LiDAR demo | Pending Cloudflare Tunnel setup |
| Private S3 bucket | Selected event frames, clips, LiDAR artifacts, models and logs | Pending non-root AWS setup |
| Roboflow project | Dataset upload, annotation, dataset versions and YOLO training | Pending project creation |

## Repository workflow

```text
feature branch → develop → main
```

- `main`: approved, tested release history only.
- `develop`: integration branch for validated feature work.
- `codex/<feature>`: one focused change at a time; open a pull request into
  `develop` after verification.
- Do not commit tokens, private keys, raw camera imagery, cloud credentials,
  or large model weights. See [Security and data boundaries](docs/SECURITY.md).

## Documentation map

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment plan](docs/DEPLOYMENT_PLAN.md)
- [Training workflow](docs/TRAINING_WORKFLOW.md)
- [Current runtime inventory](docs/RUNTIME_INVENTORY.md)
- [Security and data boundaries](docs/SECURITY.md)
- [Decision log](docs/DECISIONS.md)

## Current deployment status

The current Pi dashboard is running locally and has been health-checked. This
repository records the deployment plan; it does not claim that Cloudflare,
AWS storage, remote training, or public access is already deployed.
