# Decision log

| ID | Decision | Status | Reason |
| --- | --- | --- | --- |
| V-001 | Keep Vision Dev separate from the main Soil Eco service | Accepted | Protects the working platform and allows independent experimentation |
| V-002 | Use ShellHub for Pi maintenance only | Accepted | Dashboard sharing and training require separate access boundaries |
| V-003 | Use Cloudflare Tunnel + Access for `camera.soileco.dev` | Planned | Avoids inbound Pi port exposure and supports named viewers |
| V-004 | Use Roboflow first for annotation/training | Planned | Browser/phone workflow and YOLO-oriented dataset lifecycle |
| V-005 | Keep S3 private and upload only selected artifacts | Planned | Reduces privacy, cost, and credential exposure |
| V-006 | Use `main` / `develop` / feature-branch workflow | Accepted | Allows reviewed integration before releases |
