#!/usr/bin/env python3
"""Shared-camera YOLO dashboard for a Raspberry Pi 4 USB webcam."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import serial
from flask import Flask, Response, jsonify
from ultralytics import YOLO

IST = ZoneInfo("Asia/Kolkata")
MAX_OBSERVATIONS = 100
EVENT_DB = Path("/home/pi/soileco-yolo/events.sqlite3")
LEGACY_OBSERVATIONS = Path("/home/pi/soileco-yolo/observations-before-persistence.json")
LIDAR_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0"
LIDAR_BAUD = 115200


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a YOLO dashboard from a V4L2 camera.")
    parser.add_argument("--device", default="/dev/video0", help="V4L2 device (default: /dev/video0)")
    parser.add_argument("--secondary-device", default="/dev/video2", help="Second V4L2 camera to show as a raw stream; use empty string to disable")
    parser.add_argument("--model", default="yolo11n.pt", help="Ultralytics model or local model path")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--imgsz", type=int, default=320, help="Inference size; keep low on Pi 4")
    parser.add_argument("--conf", type=float, default=0.40)
    parser.add_argument("--infer-every", type=int, default=4, help="Run YOLO once every N frames")
    parser.add_argument("--lidar-scan-seconds", type=int, default=300, help="Active LiDAR scan duration per cycle")
    parser.add_argument("--lidar-idle-seconds", type=int, default=600, help="LiDAR idle duration per cycle")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--smoke-test", action="store_true", help="Capture and infer one frame, then exit")
    return parser.parse_args(argv)


def now_text() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def open_event_store() -> tuple[sqlite3.Connection, threading.Lock]:
    """Create the durable event log and import the pre-persistence dashboard summary once."""
    connection = sqlite3.connect(EVENT_DB, check_same_thread=False)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS observation_summary (
        camera TEXT NOT NULL, label TEXT NOT NULL, first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL, count INTEGER NOT NULL, max_confidence REAL NOT NULL,
        PRIMARY KEY (camera, label))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS detection_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, camera TEXT NOT NULL,
        label TEXT NOT NULL, confidence REAL NOT NULL)""")
    empty = connection.execute("SELECT COUNT(*) FROM observation_summary").fetchone()[0] == 0
    if empty and LEGACY_OBSERVATIONS.exists():
        try:
            for row in json.loads(LEGACY_OBSERVATIONS.read_text()).get("observations", []):
                connection.execute("INSERT OR IGNORE INTO observation_summary VALUES (?, ?, ?, ?, ?, ?)",
                    (row["camera"], row["label"], row["first_seen"], row["last_seen"], row["count"], row["max_confidence"]))
            connection.commit()
            LEGACY_OBSERVATIONS.rename(LEGACY_OBSERVATIONS.with_suffix(".imported.json"))
        except (OSError, ValueError, KeyError, sqlite3.Error):
            logging.exception("Could not import pre-persistence observations")
    return connection, threading.Lock()


def load_observations(connection: sqlite3.Connection, lock: threading.Lock) -> OrderedDict[str, dict]:
    with lock:
        rows = connection.execute("SELECT camera,label,first_seen,last_seen,count,max_confidence FROM observation_summary ORDER BY last_seen ASC LIMIT ?", (MAX_OBSERVATIONS,)).fetchall()
    return OrderedDict((f"{camera}:{label}", {"camera": camera, "label": label, "first_seen": first_seen, "last_seen": last_seen, "count": count, "max_confidence": confidence}) for camera, label, first_seen, last_seen, count, confidence in rows)


def recent_events(connection: sqlite3.Connection, lock: threading.Lock) -> list[dict]:
    with lock:
        rows = connection.execute("SELECT timestamp,camera,label,confidence FROM detection_event ORDER BY id DESC LIMIT 100").fetchall()
    return [{"timestamp": timestamp, "camera": camera, "label": label, "confidence": confidence} for timestamp, camera, label, confidence in rows]


def event_cooldowns(connection: sqlite3.Connection, lock: threading.Lock) -> dict[str, datetime]:
    with lock:
        rows = connection.execute("SELECT camera,label,MAX(timestamp) FROM detection_event GROUP BY camera,label").fetchall()
    return {f"{camera}:{label}": datetime.fromisoformat(timestamp) for camera, label, timestamp in rows}


def open_camera(args: argparse.Namespace) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(args.device, cv2.CAP_V4L2)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    camera.set(cv2.CAP_PROP_FPS, args.fps)
    if not camera.isOpened():
        raise RuntimeError(f"Cannot open camera: {args.device}")
    return camera


def detect(model: YOLO, frame, args: argparse.Namespace):
    result = model(frame, imgsz=args.imgsz, conf=args.conf, verbose=False)[0]
    detections = []
    if result.boxes is not None:
        for box, cls_id, confidence in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
            detections.append({"label": result.names[int(cls_id)], "confidence": round(float(confidence), 3), "box": [round(v) for v in box]})
    return detections


def draw(frame, detections, status_text: str):
    output = frame.copy()
    for item in detections:
        x1, y1, x2, y2 = item["box"]
        label = f"{item['label']} {item['confidence']:.0%}"
        cv2.rectangle(output, (x1, y1), (x2, y2), (45, 190, 91), 2)
        cv2.putText(output, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (45, 190, 91), 2, cv2.LINE_AA)
    cv2.rectangle(output, (0, 0), (output.shape[1], 29), (20, 37, 28), -1)
    cv2.putText(output, status_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 245, 235), 1, cv2.LINE_AA)
    return output


def motion_score(previous_gray, frame) -> tuple[object, float]:
    """Return a cheap motion score; YOLO is only run when this exceeds the threshold."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    gray = cv2.GaussianBlur(gray, (15, 15), 0)
    if previous_gray is None:
        return gray, 0.0
    difference = cv2.absdiff(previous_gray, gray)
    _, threshold = cv2.threshold(difference, 25, 255, cv2.THRESH_BINARY)
    return gray, float(cv2.countNonZero(threshold)) / threshold.size


def lidar_nodes(buffer: bytearray) -> list[tuple[float, float, int]]:
    """Consume complete RPLIDAR A1 standard-measurement nodes from a byte stream.

    Serial reads need not begin or end at a five-byte node boundary.  The two
    sync bits make it safe to discard bytes until the next valid node, rather
    than plotting an arbitrary half-second batch as if it were a full scan.
    """
    nodes = []
    while len(buffer) >= 5:
        node = buffer[:5]
        valid_sync = (node[0] & 1) != ((node[0] >> 1) & 1) and (node[1] & 1) == 1
        if not valid_sync:
            del buffer[0]
            continue
        angle = ((node[2] << 7) | (node[1] >> 1)) / 64.0
        distance = (node[3] | (node[4] << 8)) / 4.0
        del buffer[:5]
        if 0 <= angle < 360:
            nodes.append((angle, distance, node[0] >> 2))
    return nodes


def dashboard_html() -> str:
    return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>SoilEco Camera</title><style>
    :root{--bg:#0d1711;--card:#14231a;--line:#294333;--ink:#ecf5ee;--muted:#aabcb0;--accent:#5ed68a}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1280px;margin:auto;padding:22px}header{display:flex;align-items:baseline;justify-content:space-between;gap:14px;margin-bottom:18px}h1{font-size:1.55rem;margin:0}small{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.cameras{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}.stream{width:100%;display:block;aspect-ratio:4/3;object-fit:contain;background:#000}.camera-title{padding:10px 14px;border-bottom:1px solid var(--line);font-weight:650;font-size:.93rem}.pad{padding:16px}h2{font-size:1rem;margin:0 0 12px}.active{display:flex;flex-wrap:wrap;gap:8px}.badge{background:#1c4d2d;color:#dcffe8;border:1px solid #367348;border-radius:99px;padding:6px 9px;font-size:.88rem}.empty{color:var(--muted)}table{width:100%;border-collapse:collapse;font-size:.88rem}th,td{text-align:left;padding:9px 4px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-weight:600}.error{color:#ffc0b7}.ok{color:var(--accent)}.lidar-note{color:var(--muted);font-size:.82rem;margin:8px 0 0}@media(max-width:800px){.grid,.cameras{grid-template-columns:1fr}main{padding:12px}}
    </style></head><body><main><header><h1>SoilEco Camera · Motion-gated Object Detection</h1><small id='health'>Connecting…</small></header><div class='cameras'><section class='card'><div class='camera-title'>Camera 1 · Logitech C270 · YOLO when motion occurs</div><img class='stream' src='/stream.mjpg' alt='Live annotated primary camera stream'></section><section class='card'><div class='camera-title'>Camera 2 · PlayStation Eye · YOLO when motion occurs</div><img class='stream' src='/secondary.mjpg' alt='Live annotated secondary camera stream'></section></div><div class='grid' style='margin-top:18px'><section class='card pad'><h2>Objects visible now</h2><div id='active' class='active'><span class='empty'>Waiting for a detection…</span></div><h2 style='margin-top:23px'>Camera status</h2><div id='meta' class='empty'>Loading…</div></section><section class='card pad'><h2>LiDAR · A1M8 last completed 360° scan</h2><div id='lidar' class='empty'>Checking USB serial link…</div><canvas id='scan' width='600' height='600' style='width:100%;aspect-ratio:1;background:#0a100c;border:1px solid #294333;margin-top:12px' aria-label='LiDAR polar range plot'></canvas><p class='lidar-note'>Fixed scale: 0–8 m. 0° is the sensor front; 90° is its right. This is range data in the sensor’s fixed coordinate frame, not a room map.</p></section></div><section class='card pad' style='margin-top:18px'><h2>Observation summary</h2><table><thead><tr><th>Camera</th><th>Object</th><th>Last seen</th><th>Count</th><th>Best confidence</th></tr></thead><tbody id='history'><tr><td colspan='5' class='empty'>No observations yet.</td></tr></tbody></table></section><section class='card pad' style='margin-top:18px'><h2>Recent detection log · stored locally</h2><table><thead><tr><th>Timestamp</th><th>Camera</th><th>Object</th><th>Confidence</th></tr></thead><tbody id='events'><tr><td colspan='4' class='empty'>No logged detections yet.</td></tr></tbody></table></section></main><script>
    const fmt=t=>t?new Date(t).toLocaleString():'—';
    function drawScan(points){const c=document.querySelector('#scan'),x=c.getContext('2d'),w=c.width,h=c.height,cx=w/2,cy=h/2,r=w*.42,furthest=Math.max(1000,...points.map(p=>p[1])),max=Math.max(2000,Math.min(8000,Math.ceil(furthest/1000)*1000));x.fillStyle='#0a100c';x.fillRect(0,0,w,h);x.strokeStyle='#294333';x.lineWidth=1;for(let m=1000;m<=max;m+=1000){x.beginPath();x.arc(cx,cy,r*m/max,0,Math.PI*2);x.stroke();x.fillStyle='#aabcb0';x.font='12px system-ui';x.fillText(`${m/1000} m`,cx+5,cy-r*m/max-3)}x.strokeStyle='#496054';x.beginPath();x.moveTo(cx-r,cy);x.lineTo(cx+r,cy);x.moveTo(cx,cy-r);x.lineTo(cx,cy+r);x.stroke();x.fillStyle='#aabcb0';x.font='14px system-ui';x.fillText('0° front',cx-25,cy-r-10);x.fillText('90° right',cx+r-64,cy-8);x.fillText('180°',cx-18,cy+r+18);x.fillText('270° left',cx-r+5,cy-8);x.fillText(`display 0–${max/1000} m`,12,22);x.fillStyle='#5ed68a';points.forEach(p=>{const a=(p[0]-90)*Math.PI/180,d=Math.min(p[1],max),px=cx+Math.cos(a)*d*r/max,py=cy+Math.sin(a)*d*r/max;x.fillRect(px-1,py-1,2,2)});x.fillStyle='#ff725c';x.beginPath();x.arc(cx,cy,5,0,Math.PI*2);x.fill()}
    function countdown(t){return t?Math.max(0,Math.ceil(t-Date.now()/1000))+' s':'—'}
    async function update(){try{const s=await fetch('/status',{cache:'no-store'}).then(r=>r.json()),q=s.secondary,l=s.lidar;document.querySelector('#health').innerHTML=(s.camera_error||q.error)?'<span class="error">Camera error</span>':'<span class="ok">Live</span> · updated '+fmt(s.updated_at||q.updated_at);document.querySelector('#meta').textContent=`C1: motion ${Math.round(s.motion*100)}%, ${s.last_inference ?? '—'} s · C2: motion ${Math.round(q.motion*100)}%, ${q.last_inference ?? '—'} s`;const scanInfo=l.last_scan_at?`last full scan ${fmt(l.last_scan_at)} · ${l.points} valid points · ${l.coverage_pct}% angular coverage · ${Math.round(l.min_mm)}–${Math.round(l.max_mm)} mm`: 'Waiting for the first complete 360° revolution…';document.querySelector('#lidar').innerHTML=l.error?`<span class="error">Scanner data unavailable: ${l.error}</span>`:l.mode==='idle'?`<span class="ok">LiDAR idle</span> · ${scanInfo} · next scan in ${countdown(l.next_change_at)}`:`<span class="ok">Scanning</span> · ${scanInfo} · idle in ${countdown(l.next_change_at)}`;drawScan(l.samples||[]);const all=[...s.detections.map(d=>({...d,c:'C1'})),...q.detections.map(d=>({...d,c:'C2'}))],a=document.querySelector('#active');a.innerHTML=all.length?all.map(d=>`<span class="badge">${d.c}: ${d.label} ${Math.round(d.confidence*100)}%</span>`).join(''):'<span class="empty">No object above threshold in the latest motion event.</span>';const h=document.querySelector('#history');h.innerHTML=s.observations.length?s.observations.map(o=>`<tr><td>${o.camera}</td><td>${o.label}</td><td>${fmt(o.last_seen)}</td><td>${o.count}</td><td>${Math.round(o.max_confidence*100)}%</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No observations yet.</td></tr>';const e=document.querySelector('#events');e.innerHTML=s.recent_events.length?s.recent_events.map(x=>`<tr><td>${fmt(x.timestamp)}</td><td>${x.camera}</td><td>${x.label}</td><td>${Math.round(x.confidence*100)}%</td></tr>`).join(''):'<tr><td colspan="4" class="empty">No logged detections yet.</td></tr>'}catch(e){document.querySelector('#health').textContent='Dashboard connection error';}}
    document.querySelector('.lidar-note').textContent='The display scale adapts from 2–8 m and is labelled on the chart. 0° is the sensor front; 90° is its right. This is range data in the sensor’s fixed coordinate frame, not a room map.';
    update();setInterval(update,1000);
    </script></body></html>"""


def create_app(
    args: argparse.Namespace | None = None,
    *,
    start_workers: bool = True,
    model=None,
    camera=None,
    event_store: tuple[sqlite3.Connection, threading.Lock] | None = None,
) -> Flask:
    """Create the dashboard application and optionally start its device workers."""
    args = args or parse_args([])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Loading model %s", args.model)
    model = model if model is not None else YOLO(args.model)
    camera = camera if camera is not None else open_camera(args)
    ok, frame = camera.read()
    if not ok:
        camera.release()
        raise RuntimeError("Camera opened but did not return a frame")
    if args.smoke_test:
        camera.release()
        raise ValueError("Smoke tests must use run_smoke_test(), not create_app()")

    connection, db_lock = event_store if event_store is not None else open_event_store()
    app = Flask(__name__)
    state = {"detections": [], "last_inference": None, "frame": 0, "camera_error": None, "updated_at": None, "device": args.device, "motion": 0.0}
    secondary_state = {"detections": [], "last_inference": None, "frame": 0, "error": None, "updated_at": None, "device": args.secondary_device, "motion": 0.0}
    lidar_state = {"port": LIDAR_PORT, "points": 0, "min_mm": 0.0, "max_mm": 0.0,
                   "samples": [], "coverage_pct": 0, "last_scan_at": None,
                   "updated_at": None, "error": "Waiting for scanner data", "mode": "starting",
                   "next_change_at": None}
    observations = load_observations(connection, db_lock)
    last_event = event_cooldowns(connection, db_lock)
    inference_lock = threading.Lock()
    latest = {"jpeg": None}
    condition = threading.Condition()

    @app.get("/")
    def index():
        return dashboard_html()

    @app.get("/status")
    def status():
        return jsonify({**state, "secondary": secondary_state, "lidar": lidar_state, "observations": list(observations.values()), "recent_events": recent_events(connection, db_lock)})

    @app.get("/healthz")
    def healthz():
        lidar_error = lidar_state["error"]
        healthy = state["camera_error"] is None and lidar_error is None
        payload = {"healthy": healthy, "model": args.model, "camera_error": state["camera_error"],
                   "lidar_error": lidar_error, "workers_started": start_workers}
        return jsonify(payload), 200 if healthy else 503

    def record(camera_name: str, detections: list[dict]) -> None:
        timestamp = now_text()
        for item in detections:
            key = f"{camera_name}:{item['label']}"
            record = observations.get(key)
            if record is None:
                record = {"camera": camera_name, "label": item["label"], "first_seen": timestamp, "last_seen": timestamp, "count": 0, "max_confidence": 0.0}
                observations[key] = record
            record["last_seen"] = timestamp
            record["count"] += 1
            record["max_confidence"] = max(record["max_confidence"], item["confidence"])
            observations.move_to_end(key)
            current_time = datetime.fromisoformat(timestamp)
            previous_time = last_event.get(key)
            with db_lock:
                if previous_time is None or (current_time - previous_time).total_seconds() >= 30:
                    connection.execute("INSERT INTO detection_event (timestamp,camera,label,confidence) VALUES (?, ?, ?, ?)", (timestamp, camera_name, item["label"], item["confidence"]))
                    last_event[key] = current_time
                connection.execute("""INSERT INTO observation_summary (camera,label,first_seen,last_seen,count,max_confidence)
                    VALUES (?, ?, ?, ?, 1, ?)
                    ON CONFLICT(camera,label) DO UPDATE SET last_seen=excluded.last_seen,
                    count=observation_summary.count+1,
                    max_confidence=MAX(observation_summary.max_confidence, excluded.max_confidence)""",
                    (camera_name, item["label"], timestamp, timestamp, item["confidence"]))
                connection.commit()
        while len(observations) > MAX_OBSERVATIONS:
            observations.popitem(last=False)

    def capture_loop():
        count = 0
        detections: list[dict] = []
        previous_gray = None
        last_detection = 0.0
        while True:
            try:
                ok, current = camera.read()
                if not ok:
                    state["camera_error"] = "Camera frame read failed"
                    time.sleep(0.2)
                    continue
                count += 1
                previous_gray, score = motion_score(previous_gray, current)
                state["motion"] = round(score, 4)
                should_infer = count == max(args.infer_every, 1) or (score >= 0.012 and count % max(args.infer_every, 1) == 0)
                if should_infer:
                    started = time.monotonic()
                    with inference_lock:
                        detections = detect(model, current, args)
                    state["detections"] = detections
                    state["last_inference"] = round(time.monotonic() - started, 3)
                    state["updated_at"] = now_text()
                    last_detection = time.monotonic()
                    record("Camera 1", detections)
                if time.monotonic() - last_detection > 3:
                    detections = []
                    state["detections"] = []
                status = f"C1 motion {score:.1%} · YOLO {state['last_inference'] or 0:.2f}s"
                displayed = draw(current, detections, status)
                state["frame"] = count
                ok, encoded = cv2.imencode(".jpg", displayed, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    with condition:
                        latest["jpeg"] = encoded.tobytes()
                        state["camera_error"] = None
                        condition.notify_all()
            except Exception as exc:
                logging.exception("Camera/inference loop failed")
                state["camera_error"] = str(exc)
                time.sleep(1)

    def frames():
        last_frame = None
        while True:
            with condition:
                condition.wait_for(lambda: latest["jpeg"] is not None and latest["jpeg"] is not last_frame, timeout=10)
                jpeg = latest["jpeg"]
            if jpeg is not None:
                last_frame = jpeg
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

    @app.get("/stream.mjpg")
    def stream():
        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    secondary = {"jpeg": None, "error": None}
    secondary_condition = threading.Condition()

    def secondary_loop():
        if not args.secondary_device:
            secondary_state["error"] = "Secondary camera disabled"
            return
        second = cv2.VideoCapture(args.secondary_device, cv2.CAP_V4L2)
        second.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
        second.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        second.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        second.set(cv2.CAP_PROP_FPS, 30)
        if not second.isOpened():
            secondary_state["error"] = f"Cannot open secondary camera: {args.secondary_device}"
            logging.error(secondary_state["error"])
            return
        count = 0
        detections: list[dict] = []
        previous_gray = None
        last_detection = 0.0
        while True:
            ok, second_frame = second.read()
            if not ok:
                secondary_state["error"] = "Secondary camera frame read failed"
                time.sleep(0.2)
                continue
            # PS Eye is a Bayer camera; OpenCV sometimes returns already decoded BGR and sometimes raw Bayer.
            if len(second_frame.shape) == 2:
                second_frame = cv2.cvtColor(second_frame, cv2.COLOR_BayerGR2BGR)
            count += 1
            previous_gray, score = motion_score(previous_gray, second_frame)
            secondary_state["motion"] = round(score, 4)
            should_infer = count == max(args.infer_every, 1) or (score >= 0.012 and count % max(args.infer_every, 1) == 0)
            if should_infer:
                started = time.monotonic()
                with inference_lock:
                    detections = detect(model, second_frame, args)
                secondary_state["detections"] = detections
                secondary_state["last_inference"] = round(time.monotonic() - started, 3)
                secondary_state["updated_at"] = now_text()
                last_detection = time.monotonic()
                record("Camera 2", detections)
            if time.monotonic() - last_detection > 3:
                detections = []
                secondary_state["detections"] = []
            secondary_state["frame"] = count
            displayed = draw(second_frame, detections, f"C2 motion {score:.1%} · YOLO {secondary_state['last_inference'] or 0:.2f}s")
            ok, encoded = cv2.imencode(".jpg", displayed, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                with secondary_condition:
                    secondary["jpeg"] = encoded.tobytes()
                    secondary_state["error"] = None
                    secondary_condition.notify_all()

    def secondary_frames():
        previous = None
        while True:
            with secondary_condition:
                secondary_condition.wait_for(lambda: secondary["jpeg"] is not None and secondary["jpeg"] is not previous, timeout=10)
                jpeg = secondary["jpeg"]
            if jpeg:
                previous = jpeg
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

    @app.get("/secondary.mjpg")
    def secondary_stream():
        return Response(secondary_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    def lidar_loop():
        while True:
            try:
                with serial.Serial(LIDAR_PORT, LIDAR_BAUD, timeout=0.1, write_timeout=0.5, rtscts=False, dsrdtr=False) as sensor:
                    sensor.dtr = False
                    sensor.rts = False
                    sensor.write(bytes.fromhex("A5 40"))  # reset; A1M8 requires this initialization after open
                    sensor.flush()
                    time.sleep(2.0)
                    sensor.reset_input_buffer()
                    sensor.write(bytes.fromhex("A5 20"))
                    sensor.flush()
                    scan_until = time.monotonic() + args.lidar_scan_seconds
                    lidar_state.update(mode="scanning", next_change_at=time.time() + args.lidar_scan_seconds, error=None)
                    serial_buffer = bytearray()
                    revolution = []
                    last_angle = None
                    while time.monotonic() < scan_until:
                        until = time.monotonic() + 0.5
                        while time.monotonic() < until:
                            serial_buffer.extend(sensor.read(4096))
                        nodes = lidar_nodes(serial_buffer)
                        if nodes:
                            for angle, distance, quality in nodes:
                                # A substantial angle drop marks the beginning of the next rotation.
                                if last_angle is not None and last_angle > 300 and angle < 60 and len(revolution) >= 100:
                                    distances = [point[1] for point in revolution]
                                    bins = {int(point[0]) for point in revolution}
                                    step = max(1, len(revolution) // 720)
                                    lidar_state.update(
                                        points=len(revolution), min_mm=min(distances), max_mm=max(distances),
                                        samples=[[round(a, 2), round(d, 1), q] for a, d, q in revolution[::step]],
                                        coverage_pct=round(len(bins) / 360 * 100), last_scan_at=now_text(),
                                        updated_at=now_text(), error=None)
                                    revolution = []
                                last_angle = angle
                                if 0 < distance <= 8000:
                                    revolution.append((angle, distance, quality))
                        elif not serial_buffer:
                            lidar_state["error"] = "no serial bytes received"
                    sensor.write(bytes.fromhex("A5 25"))
                    sensor.flush()
                    lidar_state.update(mode="idle", next_change_at=time.time() + args.lidar_idle_seconds, error=None)
                time.sleep(args.lidar_idle_seconds)
            except Exception as exc:
                lidar_state.update(error=str(exc), mode="error", next_change_at=time.time() + 2)
                time.sleep(2)

    if start_workers:
        threading.Thread(target=capture_loop, name="camera-capture", daemon=True).start()
        threading.Thread(target=secondary_loop, name="secondary-camera", daemon=True).start()
        threading.Thread(target=lidar_loop, name="lidar-reader", daemon=True).start()
    app.extensions["soileco_runtime"] = {"camera": camera, "connection": connection, "workers_started": start_workers}
    return app


def run_smoke_test(args: argparse.Namespace) -> None:
    logging.info("Loading model %s", args.model)
    model = YOLO(args.model)
    camera = open_camera(args)
    try:
        ok, frame = camera.read()
        if not ok:
            raise RuntimeError("Camera opened but did not return a frame")
        started = time.monotonic()
        detections = detect(model, frame, args)
        output = Path("/home/pi/soileco-yolo/smoke-test.jpg")
        if not cv2.imwrite(str(output), draw(frame, detections, "Smoke test")):
            raise RuntimeError(f"Could not write {output}")
        print(f"SMOKE_TEST_OK seconds={time.monotonic()-started:.2f} detections={detections} image={output}")
    finally:
        camera.release()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.smoke_test:
        run_smoke_test(args)
        return
    app = create_app(args)
    logging.info("Starting dashboard at http://0.0.0.0:%d", args.port)
    app.run(host="0.0.0.0", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
