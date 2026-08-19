# Cloud-visible demo deployment plan

## Release gates

1. Preserve the current local Pi dashboard and create a verified backup.
2. Create a named Cloudflare Tunnel: `soileco-camera-dev`.
3. Route only `camera.soileco.dev` to `http://localhost:8080` on the Pi.
4. Protect the hostname with Cloudflare Access before sharing it.
5. Replace the Flask development server with a tested production WSGI path
   before broader external use; do not restart the working service until the
   replacement has passed local health checks and rollback is ready.
6. Test an authorized remote viewer, an unauthorized viewer denial, camera
   streams, LiDAR data, reconnect behavior, and the local dashboard after a
   tunnel restart.

## Cloudflare administrator inputs

- Control of the `soileco.dev` Cloudflare zone.
- Permission to create a Cloudflare Tunnel and Access application.
- Initial Access users: project administrator and named intern only.
- No router port-forwarding and no DNS A record for the home/Pi IP.

## AWS comes second

AWS is not required for the first Cloudflare-protected live dashboard. Create
the isolated S3 storage only after the external dashboard works and a
non-root AWS development identity is available. Keep the bucket private and
use short-lived access, not permanent credentials embedded on the Pi.
