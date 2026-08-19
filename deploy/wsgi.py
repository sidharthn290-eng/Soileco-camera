"""Single-worker WSGI entry point for the Pi staging service."""

from soileco_yolo_stream import create_app


app = create_app()
