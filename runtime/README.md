# Pi runtime baseline

This directory records the observed SoilecoCAM1 runtime needed to reproduce
or safely evolve the dashboard. It is not an instruction to reinstall the
packages or restart the Pi.

- Python: `3.13.5`
- Environment: `/home/pi/soileco-yolo/.venv`
- `pip check`: passed on the live Pi during the baseline capture
- Service: `soileco-yolo-stream.service`

The service file is a baseline copy. Any production WSGI or Cloudflare change
must use a separate service name and port first, pass health checks, and have
a rollback procedure before it replaces this service.
