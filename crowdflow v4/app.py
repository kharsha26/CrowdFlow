"""
CrowdFlow PRO v4  —  app.py
============================
Run:  python app.py
Open: http://localhost:5000

Supports:
  - Video file upload (MP4 / AVI / MOV)
  - Mobile phone stream (IP Webcam app)
  - RTSP IP camera / CCTV
  - USB webcam
"""

import os
import time
import socket
import cv2
import numpy as np
from flask import (Flask, render_template, request,
                   jsonify, Response, send_from_directory)

from ml.analyzer  import CrowdAnalyzer
from ml.predictor import FlowPredictor
from ml.threat    import ThreatDetector
from utils.logger   import EventLogger
from utils.reporter import Reporter
from config.settings import get_profile

# ── App ───────────────────────────────────────────────────────
app     = Flask(__name__)
app.config["UPLOAD_FOLDER"]       = "uploads"
app.config["MAX_CONTENT_LENGTH"]  = 600 * 1024 * 1024   # 600 MB

# ── Global instances ──────────────────────────────────────────
profile   = get_profile()
analyzer  = CrowdAnalyzer(sensitivity=profile["sensitivity"])
predictor = FlowPredictor()
threat    = ThreatDetector()
logger    = EventLogger()
reporter  = Reporter()

logger.log("SYSTEM", f"CrowdFlow PRO v4 started — profile: {profile['name']}")


# ════════════════════════════════════════════════════════════
#  PAGE
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html", profile=profile)


# ════════════════════════════════════════════════════════════
#  VIDEO FILE UPLOAD
# ════════════════════════════════════════════════════════════

@app.route("/api/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["video"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    os.makedirs("uploads", exist_ok=True)
    ext  = os.path.splitext(f.filename)[1].lower()
    path = os.path.join("uploads", f"crowd{ext}")
    f.save(path)

    info = analyzer.load_file(path)
    if not info.get("ok"):
        return jsonify(info), 400

    logger.log("VIDEO_LOADED", f"File: {f.filename} | {info['frame_count']} frames @ {info['fps']} fps")
    return jsonify(info)


# ════════════════════════════════════════════════════════════
#  LIVE STREAM SOURCE
# ════════════════════════════════════════════════════════════

@app.route("/api/set_source", methods=["POST"])
def set_source():
    data  = request.json or {}
    url   = data.get("url", "")
    label = data.get("label", "Stream")
    if not str(url).strip():
        return jsonify({"ok": False, "error": "url required"}), 400
    info = analyzer.open_stream(url, label)
    logger.log("SOURCE_CHANGED", f"Source: {label} → {url}")
    return jsonify(info)


@app.route("/api/source_info")
def source_info():
    m = analyzer.get_metrics()
    return jsonify({
        "has_source":   m["has_source"],
        "source_type":  m["source_type"],
        "total_frames": m["total_frames"],
        "fps":          m["fps"],
    })


# ════════════════════════════════════════════════════════════
#  MJPEG STREAM  —  annotated frames from OpenCV
# ════════════════════════════════════════════════════════════

@app.route("/api/video_feed")
def video_feed():
    def generate():
        while True:
            if not analyzer.has_source:
                # No source — send a dark placeholder
                ph = _placeholder(640, 360, "Load a video or connect a camera")
                ok, buf = cv2.imencode(".jpg", ph)
                if ok:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + bytes(buf) + b"\r\n"
                time.sleep(0.15)
                continue

            data = analyzer.next_jpeg()
            if data is None:
                time.sleep(0.04)
                continue

            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            time.sleep(0.04)   # ~25 fps

    return Response(generate(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


def _placeholder(w: int, h: int, msg: str) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # Grid
    for x in range(0, w, 40):
        cv2.line(img, (x,0), (x,h), (20,30,35), 1)
    for y in range(0, h, 40):
        cv2.line(img, (0,y), (w,y), (20,30,35), 1)
    # Logo text
    cv2.putText(img, "CrowdFlow PRO v4", (w//2-120, h//2-20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,180,220), 1)
    cv2.putText(img, msg, (w//2-len(msg)*5, h//2+14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60,90,100), 1)
    cv2.putText(img, "Load a video file  or  connect a stream to begin",
                (w//2-195, h//2+40), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (40,70,80), 1)
    return img


# ════════════════════════════════════════════════════════════
#  STATUS  (polled every 700 ms by frontend)
# ════════════════════════════════════════════════════════════

@app.route("/api/status")
def status():
    metrics   = analyzer.get_metrics()
    zones     = analyzer.get_zones()
    ee        = analyzer.get_entry_exit()
    queues    = analyzer.get_queues()
    speed     = analyzer.get_speed()
    threats   = threat.get_threats()
    prediction = predictor.predict(metrics.get("density_history", []))
    alerts    = logger.get_alerts(12)
    incidents = logger.get_incidents(30)

    # Auto-fire alert if zone density > threshold
    for z in zones:
        if z["density_pct"] > 85 and not z["closed"]:
            logger.log("DENSITY_ALERT", f"Crush risk in {z['name']} — {z['density_pct']}%", level="CRITICAL")
        elif z["density_pct"] > 70:
            logger.log("DENSITY_WARN", f"High density in {z['name']} — {z['density_pct']}%", level="WARNING")

    return jsonify({
        "metrics":    metrics,
        "zones":      zones,
        "entry_exit": ee,
        "queues":     queues,
        "speed":      speed,
        "threats":    threats,
        "prediction": prediction,
        "alerts":     logger.get_alerts(12),
        "incidents":  incidents,
        "profile":    profile["name"],
    })


# ════════════════════════════════════════════════════════════
#  SEEK (video file only)
# ════════════════════════════════════════════════════════════

@app.route("/api/seek", methods=["POST"])
def seek():
    data  = request.json or {}
    frame = int(data.get("frame", 0))
    analyzer.seek(frame)
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
#  OVERLAY TOGGLES
# ════════════════════════════════════════════════════════════

@app.route("/api/overlay", methods=["POST"])
def overlay():
    data = request.json or {}
    if "heatmap" in data:  analyzer.show_heatmap = bool(data["heatmap"])
    if "boxes"   in data:  analyzer.show_boxes   = bool(data["boxes"])
    if "trails"  in data:  analyzer.show_trails  = bool(data["trails"])
    if "flow"    in data:  analyzer.show_flow     = bool(data["flow"])
    if "zones"   in data:  analyzer.show_zones    = bool(data["zones"])
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
#  ZONE / STAFF ACTIONS
# ════════════════════════════════════════════════════════════

@app.route("/api/zone_action", methods=["POST"])
def zone_action():
    data = request.json or {}
    zid  = data.get("zone_id", "")
    act  = data.get("action", "")
    analyzer.zone_action(zid, act)
    logger.log("ZONE_ACTION", f"{act.upper()} on {zid}", level="WARNING")
    logger.incident(zid, f"Zone {act} by operator")
    return jsonify({"ok": True})


@app.route("/api/sensitivity", methods=["POST"])
def sensitivity():
    data = request.json or {}
    v    = int(data.get("value", 30))
    analyzer.set_sensitivity(v)
    return jsonify({"ok": True})


@app.route("/api/alert", methods=["POST"])
def manual_alert():
    data = request.json or {}
    msg  = data.get("message", "Manual alert by operator")
    logger.log("MANUAL_ALERT", msg, level="CRITICAL")
    logger.incident("MANUAL", msg)
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
#  WEAPON / THREAT
# ════════════════════════════════════════════════════════════

@app.route("/api/weapon_test", methods=["POST"])
def weapon_test():
    data   = request.json or {}
    zone   = data.get("zone", "Zone A")
    result = threat.simulate_weapon(zone)
    logger.log("WEAPON_DETECTED",
               f"Weapon in {zone} — civilian notified, auth secure channel",
               level="CRITICAL")
    logger.incident(zone, f"WEAPON: {result['weapon']} | Civilian notified | Auth excluded")
    return jsonify({"ok": True, "threat": result})


@app.route("/api/clear_threats", methods=["POST"])
def clear_threats():
    threat.clear()
    logger.log("THREATS_CLEARED", "All threats cleared by operator")
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
#  EVACUATION
# ════════════════════════════════════════════════════════════

@app.route("/api/evacuation", methods=["POST"])
def evacuation():
    data   = request.json or {}
    action = data.get("action", "trigger")
    if action == "trigger":
        analyzer.trigger_evacuation()
        logger.log("EVACUATION", "Emergency evacuation triggered", level="CRITICAL")
        logger.incident("SYSTEM", "Evacuation initiated by operator")
    elif action == "clear":
        analyzer.clear_evacuation()
        logger.log("EVACUATION", "All-clear — evacuation ended")
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════
#  SNAPSHOT
# ════════════════════════════════════════════════════════════

@app.route("/api/snapshot", methods=["POST"])
def snapshot():
    data = analyzer.snapshot()
    if data:
        os.makedirs("reports", exist_ok=True)
        path = os.path.join("reports", f"snap_{int(time.time())}.jpg")
        with open(path, "wb") as fh:
            fh.write(data)
        logger.incident("SYSTEM", f"Snapshot saved: {path}")
        return jsonify({"ok": True, "path": path})
    return jsonify({"ok": False, "error": "No frame available"}), 400


# ════════════════════════════════════════════════════════════
#  REPORT
# ════════════════════════════════════════════════════════════

@app.route("/api/report")
def report_json():
    m  = analyzer.get_metrics()
    th = threat.get_threats()
    inc = logger.get_incidents(50)
    al  = logger.get_alerts(50)
    ee  = analyzer.get_entry_exit()
    return jsonify(reporter.json_report(m, th, inc, al, ee))


@app.route("/api/report/download")
def report_download():
    m   = analyzer.get_metrics()
    th  = threat.get_threats()
    inc = logger.get_incidents(50)
    al  = logger.get_alerts(50)
    ee  = analyzer.get_entry_exit()
    html = reporter.html_report(m, th, inc, al, ee)
    return Response(html, mimetype="text/html",
                    headers={"Content-Disposition":
                             f"attachment; filename=crowdflow_report_{int(time.time())}.html"})


# ════════════════════════════════════════════════════════════
#  STATIC FILES
# ════════════════════════════════════════════════════════════

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory("uploads", filename)

@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory("reports", filename)


# ════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "127.0.0.1"

    print()
    print("=" * 62)
    print("   CrowdFlow PRO v4 — Smart City Surveillance Platform")
    print(f"   Profile  : {profile['name']} — {profile['description']}")
    print(f"   Laptop   : http://localhost:5000")
    print(f"   Network  : http://{local_ip}:5000")
    print("=" * 62)
    print()
    print("  HOW TO USE:")
    print("  1. Open http://localhost:5000 in Chrome/Edge")
    print("  2. Upload a crowd video  OR  connect a live stream")
    print("  3. All overlays, tabs, alerts work in real time")
    print()
    print("  VIDEO FILE  →  Upload MP4/AVI/MOV from the dashboard")
    print("  MOBILE      →  Install IP Webcam on Android, paste URL")
    print("  RTSP CCTV   →  Paste rtsp://... URL in source switcher")
    print("  USB WEBCAM  →  Enter  0  in source switcher")
    print()

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
