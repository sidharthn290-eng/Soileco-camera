# Vision Dev architecture

## Boundary

This is a camera-and-LiDAR development demonstration. It must not be merged
into or granted authority over the main Soil Eco services, farm actuation, or
ShellHub management system.

## Target flow

```text
USB cameras + RPLIDAR
          |
          v
Raspberry Pi 4 (capture, motion gate, YOLO, local event buffer)
          |
          +-- Cloudflare Tunnel --> Cloudflare Access --> camera.soileco.dev
          |
          +-- authenticated selected-event upload --> private S3
                                                   |
                                                   +--> Roboflow dataset review/training
```

## Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| Raspberry Pi | Capture, local inference, local live preview, event buffering | Public firewall exposure, dataset access control |
| Cloudflare Tunnel | Outbound connection from Pi to Cloudflare | Camera inference or data storage |
| Cloudflare Access | Viewer authentication for the dashboard | Pi SSH access or AWS permissions |
| ShellHub | Administrator maintenance SSH | Training, public dashboard serving, or cloud storage |
| Private S3 | Approved event media, LiDAR artifacts, evaluation reports and model releases | Public live streaming |
| Roboflow | Annotation, dataset versions, training and evaluation | Pi maintenance or production deployment |

## Endpoint rule

The Tunnel's origin URL is `http://localhost:8080` **on the Raspberry Pi**.
It is not a public URL. Cloudflare creates a proxied CNAME for the planned
hostname `camera.soileco.dev`; no inbound router port-forward or public Pi IP
is required.
