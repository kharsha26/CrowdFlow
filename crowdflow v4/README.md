# CrowdFlow PRO v4 — Smart City Surveillance Platform

## What Was Fixed in v4
- Heatmap alpha reduced from 55% → 38%  (no more blinding red overlay)
- Detection boxes only fire on real person-sized blobs (0.4% area filter)
- Aspect-ratio filter removes horizontal noise lines from detection
- Flow vectors only drawn when magnitude > 2.5 px/frame (no noise arrows)
- Motion accumulator Gaussian-smoothed (no speckle noise)
- All text overlays have dark background pills (readable on any background)
- Video FILE upload now fully working alongside live streams
- All 7 tabs fully working: Feed, Threat, Analytics, MultiCam, Evacuation, Speed, Report

---

## Project Structure

```
crowdflow_pro_v4/
├── app.py                   ← Flask server (run this)
├── requirements.txt
├── config/
│   ├── __init__.py
│   └── settings.py          ← Change ACTIVE_PROFILE here
├── ml/
│   ├── __init__.py
│   ├── analyzer.py          ← Core OpenCV ML pipeline (FIXED)
│   ├── predictor.py         ← scikit-learn density forecasting
│   └── threat.py            ← Weapon detection + authority classification
├── utils/
│   ├── __init__.py
│   ├── logger.py            ← Event & incident logger
│   └── reporter.py         ← HTML + JSON report generator
├── templates/
│   └── index.html           ← Full 7-tab dashboard
├── static/
│   ├── css/main.css
│   └── js/app.js
├── uploads/                 ← Video files saved here automatically
└── reports/                 ← Snapshots + exported reports saved here
```

---

## Quick Start (VS Code)

### 1. Install dependencies
```bash
pip install flask opencv-python-headless numpy scikit-learn Pillow
```

### 2. Run
```bash
python app.py
```

### 3. Open browser
```
http://localhost:5000
```

---

## How to Load Video / Connect Camera

### Option A — Upload a crowd video file
1. In the dashboard, **Video Source → Video File** is selected by default
2. Click **Browse Video File**
3. Select any `.mp4`, `.avi`, or `.mov` crowd footage
4. Analysis starts immediately — all overlays appear on the video

**Free crowd videos:**
- https://www.pexels.com/search/videos/crowd/
- https://pixabay.com/videos/search/crowd/

---

### Option B — Mobile Phone as CCTV (Demo Prototype)

**Android:**
1. Install **IP Webcam** app (by Pavel Khlebovich) from Play Store
2. Open app → scroll to bottom → tap **Start server**
3. Note the IP shown: `http://192.168.x.x:8080`
4. In dashboard: click **Mobile Phone** source button
5. Enter URL: `http://192.168.x.x:8080/video`
6. Click **Connect Stream**

**iPhone:**
1. Install **EpocCam** or **DroidCam** from App Store
2. Follow the app's instructions to get the stream URL
3. Enter in dashboard under Mobile Phone source

> Both devices must be on the **same WiFi network**

---

### Option C — RTSP IP Camera / CCTV

1. Click **CCTV / IP Cam** source button
2. Enter your RTSP URL, e.g.:
   ```
   rtsp://admin:password@192.168.1.50:554/stream1
   ```
3. Click **Connect Stream**

Common RTSP URL formats:
```
# Hikvision
rtsp://admin:pass@ip:554/Streaming/Channels/101

# Dahua
rtsp://admin:pass@ip:554/cam/realmonitor?channel=1&subtype=0

# Generic
rtsp://admin:pass@ip:554/stream1
```

---

### Option D — USB Webcam

1. Click **USB Webcam** source button
2. Enter `0` for the first webcam (or `1`, `2` for others)
3. Click **Connect Stream**

---

## Deployment Profiles

Edit `config/settings.py` and change `ACTIVE_PROFILE`:

| Profile | Use Case |
|---------|----------|
| `mobile_demo` | Phone as camera, demo/testing |
| `home_cctv` | Home security camera |
| `mall` | Shopping mall surveillance |
| `public` | Street / public space |
| `police` | High-security event monitoring |

---

## All Features

| Tab | Features |
|-----|----------|
| 📹 Live Feed | MJPEG stream, heatmap, detection boxes, trails, flow vectors, zone overlays, entry/exit counter, queue detection, ML prediction chart, live alerts |
| 🚨 Threat | Weapon detection simulation, person classification (civilian/police/army/security), civilian-only notification (authority excluded), behavior analysis |
| 📊 Analytics | 6 live charts: count trend, zone density, entry/exit flow, ML prediction, behavior mix, zone history |
| 🎥 Multi-Cam | 6-channel simulated camera grid with density indicators |
| 🚪 Evacuation | Interactive venue map, 4 evacuation routes, animated crowd flow, clearance timer |
| ⚡ Speed Map | Live velocity grid, stampede risk indicator |
| 📄 Report | Auto-generated report, export to HTML |

---

## Staff Controls

| Button | Action |
|--------|--------|
| 🚫 Close Zone | Block entry to selected zone |
| ↪ Redirect | Reduce density by 22% (redirect flow) |
| ✓ Open Zone | Reopen a closed zone |
| 📸 Snapshot | Save annotated frame to /reports/ |
| ⚠ Simulate Weapon Alert | Fire full weapon detection pipeline |
| 🚨 Trigger Evacuation | Start emergency evacuation |

**Select a zone first** by clicking it in the Zone Monitor list on the left.

---

## Weapon Alert System

When a weapon is detected on an **unknown civilian**:
- ✅ Civilian broadcast notification sent to all attendees
- ✅ Popup alert shown on dashboard
- ✅ Nearest exit directions pushed

When weapon is on **Police / Army / Security**:
- ✅ Silent alert sent via secure command channel
- ❌ NOT included in civilian broadcast (they are authorized + already on duty)

This dual-channel system prevents mass panic while ensuring rapid response.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload video file |
| POST | `/api/set_source` | Set live stream URL |
| GET | `/api/video_feed` | MJPEG annotated stream |
| GET | `/api/status` | All metrics, zones, alerts |
| POST | `/api/seek` | Seek to frame (file only) |
| POST | `/api/overlay` | Toggle overlay layers |
| POST | `/api/sensitivity` | Set ML sensitivity |
| POST | `/api/zone_action` | Close/open/redirect zone |
| POST | `/api/weapon_test` | Simulate weapon detection |
| POST | `/api/evacuation` | Trigger/clear evacuation |
| GET | `/api/report` | JSON report |
| GET | `/api/report/download` | Download HTML report |
| POST | `/api/snapshot` | Save annotated frame |

---

## Troubleshooting

**Red blurry overlay (heatmap too strong)**
- Toggle off Heatmap in Overlays panel
- Or reduce Sensitivity slider

**Too many yellow boxes on static scene**
- Reduce Sensitivity slider to 10–15
- Wait 30 seconds for background model to stabilize

**Stream not connecting**
- Ensure phone and laptop are on the same WiFi
- Try the URL in a browser first to verify it works
- For RTSP: install `ffmpeg` (`choco install ffmpeg` / `brew install ffmpeg`)

**Video file not loading**
- Ensure Flask is running (`python app.py`)
- Check the terminal for error messages
- Try converting video: `ffmpeg -i input.mov output.mp4`
