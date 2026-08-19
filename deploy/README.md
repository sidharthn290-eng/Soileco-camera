# Staging deployment artifacts

These files are for a future Pi staging deployment only. They are not
installed by this repository and must not replace `soileco-yolo-stream.service`.

The staging service uses one Gunicorn worker because the application owns USB
camera and LiDAR devices. It binds only to `127.0.0.1:8081`; Cloudflare Tunnel
will be the only future external proxy after a Pi staging acceptance test.

Before installation, verify the current Pi dashboard, take a backup, install
the source into the stated staging directory, run the unit test and a real
camera/LiDAR health check, then test `/healthz`. Rollback consists of stopping
only this staging service and confirming the original `:8080` dashboard works.
