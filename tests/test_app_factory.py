import argparse
import importlib.util
import sqlite3
import sys
import threading
import types
import unittest
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "src" / "soileco_yolo_stream.py"


class FakeCamera:
    def read(self):
        return True, object()

    def release(self):
        pass


def load_module():
    previous = sys.modules.get("ultralytics")
    fake = types.ModuleType("ultralytics")
    fake.YOLO = object
    sys.modules["ultralytics"] = fake
    try:
        spec = importlib.util.spec_from_file_location("vision_under_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules["ultralytics"]
        else:
            sys.modules["ultralytics"] = previous


class AppFactoryTests(unittest.TestCase):
    def test_healthz_is_available_without_hardware_workers(self):
        module = load_module()
        args = argparse.Namespace(model="test-model", device="fake", secondary_device="", smoke_test=False)
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE observation_summary (camera TEXT, label TEXT, first_seen TEXT, last_seen TEXT, count INTEGER, max_confidence REAL)")
        connection.execute("CREATE TABLE detection_event (id INTEGER PRIMARY KEY, timestamp TEXT, camera TEXT, label TEXT, confidence REAL)")
        app = module.create_app(
            args, start_workers=False, model=object(), camera=FakeCamera(),
            event_store=(connection, threading.Lock()),
        )
        response = app.test_client().get("/healthz")
        self.assertEqual(503, response.status_code)
        self.assertEqual({"camera_error": None, "healthy": False, "lidar_error": "Waiting for scanner data",
                          "model": "test-model", "workers_started": False}, response.get_json())


if __name__ == "__main__":
    unittest.main()
