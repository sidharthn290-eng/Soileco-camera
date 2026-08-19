# Deployment readiness: evidence and required work

## Current evidence

The Pi dashboard is a working local Flask development server on port `8080`.
The service constructs its Flask application inside `main()` after it opens
the cameras, YOLO model, SQLite event store, and LiDAR reader.

Therefore this command is **not valid today** and must not be used:

```text
gunicorn soileco_yolo_stream:app
```

There is no module-level `app` object to import.

## Required implementation before public use

1. Refactor startup into an explicit application/runtime factory with tested
   start and graceful-stop lifecycle handling.
2. Preserve exactly one owner for each USB camera and the LiDAR serial port.
3. Add `/healthz` with camera, LiDAR, model, disk, and event-store status.
4. Add a separate staging service and port; do not replace
   `soileco-yolo-stream.service` first.
5. Run actual camera and LiDAR tests on the Pi, including restart and rollback.
6. Only then proxy the tested staging service through Cloudflare Tunnel.

## Cloudflare configuration after code readiness

The tunnel should point to a loopback service on the Pi, never to a router
port-forward or public Pi IP:

```text
camera.soileco.dev -> Cloudflare Tunnel -> http://127.0.0.1:<tested-port>
```

Cloudflare Access must deny unauthenticated viewers. Tunnel tokens and Access
credentials are runtime secrets and never belong in this repository.

## Rollback rule

Keep the current systemd unit and known model unchanged until the staging
service has passed local device tests. Rollback means stopping only the new
service/tunnel and proving the original `:8080` dashboard and LiDAR scan are
healthy again.
