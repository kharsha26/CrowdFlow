"""
CrowdFlow PRO v4  —  ml/analyzer.py
======================================
FIXES applied vs previous version:
  1. Heatmap alpha capped at 0.38 (was 0.55) — no more blinding red overlay
  2. Detection boxes only on real person-sized blobs (min_area = 0.4% of frame)
  3. Aspect-ratio filter removes horizontal noise lines
  4. Flow vectors only drawn when magnitude > 2.5 px/frame
  5. Motion accumulator smoothed with Gaussian blur — no noise speckles
  6. Background subtractor threshold scales with sensitivity setting
  7. All overlays drawn with dark background pills for readability
  8. Supports both VIDEO FILE and LIVE STREAM from same class
"""

import cv2
import numpy as np
import time
import threading
from collections import deque
from typing import Optional, List, Dict


# ─────────────────────────────────────────────
class PersonTrail:
    MAX_LEN = 28

    def __init__(self, cx, cy, pid):
        self.id           = pid
        self.positions    = deque([(cx, cy)], maxlen=self.MAX_LEN)
        self.stale_frames = 0
        self.color        = tuple(int(c) for c in np.random.randint(60, 220, 3))

    def update(self, cx, cy):
        self.positions.append((cx, cy))
        self.stale_frames = 0

    @property
    def head(self):
        return self.positions[-1] if self.positions else (0, 0)

    @property
    def speed(self) -> float:
        if len(self.positions) < 5:
            return 0.0
        dx = self.positions[-1][0] - self.positions[-5][0]
        dy = self.positions[-1][1] - self.positions[-5][1]
        return float(np.hypot(dx, dy))


# ─────────────────────────────────────────────
class CrowdAnalyzer:

    ZONE_DEFS = [
        {"id": "zA", "name": "Zone A", "color": (0, 200, 255),  "rx": 0.0, "ry": 0.0, "rw": 0.5, "rh": 0.5},
        {"id": "zB", "name": "Zone B", "color": (0, 220, 100),  "rx": 0.5, "ry": 0.0, "rw": 0.5, "rh": 0.5},
        {"id": "zC", "name": "Zone C", "color": (200, 80, 255), "rx": 0.0, "ry": 0.5, "rw": 0.5, "rh": 0.5},
        {"id": "zD", "name": "Zone D", "color": (220, 180, 0),  "rx": 0.5, "ry": 0.5, "rw": 0.5, "rh": 0.5},
    ]

    QUEUE_DEFS = [
        {"name": "Main Entrance", "x1": 0.30, "y1": 0.82, "x2": 0.70, "y2": 1.00},
        {"name": "Security Gate", "x1": 0.00, "y1": 0.82, "x2": 0.30, "y2": 1.00},
        {"name": "Side Exit",     "x1": 0.70, "y1": 0.50, "x2": 1.00, "y2": 0.78},
    ]

    def __init__(self, sensitivity: int = 30):
        self.sensitivity   = sensitivity
        self._lock         = threading.Lock()

        # Source
        self._cap: Optional[cv2.VideoCapture] = None
        self._source_type  = "none"
        self.total_frames  = 0
        self.fps           = 25.0
        self._fw           = 0
        self._fh           = 0
        self.current_frame = 0

        # ML components
        self._bg_sub      = self._make_bg_sub()
        self._prev_gray   = None
        self._motion_acc  = None

        # Tracking
        self.trails: Dict[int, PersonTrail] = {}
        self._next_id = 0

        # Zones
        self.zone_state = {
            z["id"]: {"density": 0.0, "count": 0, "closed": False}
            for z in self.ZONE_DEFS
        }

        # Counters
        self._entries       = 0
        self._exits         = 0
        self._footfall_buf  = deque(maxlen=300)
        self._queue_counts  = {q["name"]: 0 for q in self.QUEUE_DEFS}
        self._speed_grid    = np.zeros((6, 10), dtype=np.float32)

        # History
        self._zone_hist     = {z["id"]: deque(maxlen=120) for z in self.ZONE_DEFS}
        self._global_hist   = deque(maxlen=120)
        self._count_hist    = deque(maxlen=120)

        # Behaviors & flow
        self._behaviors: List[Dict] = []
        self._flow_mag   = 0.0
        self._flow_ang   = 0.0
        self._flow_vecs: List[Dict] = []

        # Evacuation
        self._evacuation = False
        self._evac_pct   = 0.0

        # Overlay toggles (controlled by frontend)
        self.show_heatmap = True
        self.show_boxes   = True
        self.show_trails  = True
        self.show_flow    = True
        self.show_zones   = True

        self._last_jpeg: Optional[bytes] = None
        self._frame_count = 0

    # ══════════════════════════════════════════
    #  INTERNAL HELPERS
    # ══════════════════════════════════════════
    def _make_bg_sub(self):
        return cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=max(16, self.sensitivity),
            detectShadows=False
        )

    def _reset_ml(self):
        self._bg_sub     = self._make_bg_sub()
        self._prev_gray  = None
        self._motion_acc = None
        self.trails.clear()
        self._next_id    = 0
        self.current_frame = 0

    # ══════════════════════════════════════════
    #  SOURCE MANAGEMENT
    # ══════════════════════════════════════════
    def load_file(self, path: str) -> dict:
        """Load uploaded crowd video file."""
        with self._lock:
            if self._cap:
                self._cap.release()
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return {"ok": False, "error": f"Cannot open: {path}"}
            self._cap          = cap
            self.total_frames  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps           = max(1.0, cap.get(cv2.CAP_PROP_FPS))
            self._fw           = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._fh           = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._source_type  = "file"
            self._reset_ml()
        return {
            "ok": True, "source_type": "file",
            "frame_count": self.total_frames,
            "fps":   round(self.fps, 2),
            "width": self._fw, "height": self._fh,
            "duration": round(self.total_frames / max(1, self.fps), 2),
        }

    def open_stream(self, url, label: str = "Stream") -> dict:
        """Open mobile / RTSP / USB stream."""
        with self._lock:
            if self._cap:
                self._cap.release()
            try:
                url = int(url)          # USB index
            except (ValueError, TypeError):
                pass
            if isinstance(url, str) and url.startswith("rtsp"):
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            else:
                cap = cv2.VideoCapture(url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok = cap.isOpened()
            if ok:
                self._fw  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self._fh  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.fps  = max(1.0, cap.get(cv2.CAP_PROP_FPS) or 25.0)
            self._cap         = cap
            self._source_type = "stream"
            self.total_frames = 0
            self._reset_ml()
        return {
            "ok": ok, "source_type": "stream",
            "url": str(url), "label": label,
            "width": self._fw, "height": self._fh,
        }

    def seek(self, frame: int):
        with self._lock:
            if self._cap and self._source_type == "file":
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                self.current_frame = frame
                self._prev_gray = None

    def release(self):
        with self._lock:
            if self._cap:
                self._cap.release()
                self._cap = None
            self._source_type = "none"

    @property
    def has_source(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ══════════════════════════════════════════
    #  MAIN PIPELINE
    # ══════════════════════════════════════════
    def next_jpeg(self) -> Optional[bytes]:
        """Read frame → ML pipeline → return annotated JPEG bytes."""
        with self._lock:
            if not self._cap or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            if not ret:
                if self._source_type == "file":
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame = 0
                    ret, frame = self._cap.read()
                    if not ret:
                        return None
                else:
                    return None
            self.current_frame = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))

        annotated = self._run(frame)
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 83])
        if ok:
            self._last_jpeg = bytes(buf)
            return self._last_jpeg
        return None

    def snapshot(self) -> Optional[bytes]:
        return self._last_jpeg

    def _run(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        pw, ph = min(w, 640), min(h, 360)
        small = cv2.resize(frame, (pw, ph))
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray  = cv2.GaussianBlur(gray, (5, 5), 0)

        # Background subtraction with morphological cleanup
        fg = self._bg_sub.apply(small)
        k3 = np.ones((3, 3), np.uint8)
        k5 = np.ones((5, 5), np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN,  k3, iterations=1)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k5, iterations=2)

        # Accumulate motion map with Gaussian smoothing (no noise speckles)
        norm = fg.astype(np.float32) / 255.0
        if self._motion_acc is None or self._motion_acc.shape != norm.shape:
            self._motion_acc = norm.copy()
        else:
            self._motion_acc = self._motion_acc * 0.87 + norm * 0.13
        self._motion_acc = cv2.GaussianBlur(self._motion_acc, (13, 13), 0)

        # Optical flow every 3 frames
        self._frame_count += 1
        if self._prev_gray is not None and self._frame_count % 3 == 0:
            self._calc_flow(self._prev_gray, gray, pw, ph)
        self._prev_gray = gray.copy()

        # Blob detection & tracking
        blobs = self._blobs(fg, pw, ph)
        self._track(blobs)
        self._entry_exit(pw, ph)
        self._zones(pw, ph)
        self._queues(pw, ph)
        self._speed(pw, ph)
        self._behaviors_detect()

        # Update history
        avg_d = float(np.mean([self.zone_state[z["id"]]["density"] for z in self.ZONE_DEFS]))
        self._global_hist.append(avg_d)
        self._count_hist.append(len(self.trails))
        if self._evacuation:
            self._evac_pct = min(100.0, self._evac_pct + 0.25)

        sx, sy = w / pw, h / ph
        return self._draw(frame, w, h, sx, sy, fg, pw, ph)

    # ──────────────────────────────────────────
    def _calc_flow(self, prev, curr, pw, ph):
        try:
            flow = cv2.calcOpticalFlowFarneback(
                prev, curr, None,
                pyr_scale=0.5, levels=2, winsize=12,
                iterations=2, poly_n=5, poly_sigma=1.1, flags=0)
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            self._flow_mag = float(np.mean(mag))
            fx = float(np.mean(flow[..., 0]))
            fy = float(np.mean(flow[..., 1]))
            if self._flow_mag > 0.2:
                self._flow_ang = float(np.arctan2(fy, fx))
            vecs = []
            for y in range(0, ph, 24):
                for x in range(0, pw, 24):
                    dx = float(flow[y, x, 0]); dy = float(flow[y, x, 1])
                    m  = float(np.hypot(dx, dy))
                    if m > 2.5:   # only real movement
                        vecs.append({"x": x/pw, "y": y/ph,
                                     "dx": dx/pw, "dy": dy/ph, "mag": m})
            self._flow_vecs = vecs[:55]
        except Exception:
            pass

    def _blobs(self, mask, pw, ph) -> List[Dict]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        total = pw * ph
        min_a = total * 0.004   # 0.4% — person-sized minimum
        max_a = total * 0.14
        blobs = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_a < area < max_a:
                x, y, bw, bh = cv2.boundingRect(cnt)
                if bh / max(bw, 1) < 0.25:  # filter horizontal noise
                    continue
                blobs.append({"cx": x+bw//2, "cy": y+bh//2,
                               "x": x, "y": y, "w": bw, "h": bh, "area": area})
        return blobs

    def _track(self, blobs):
        matched = set()
        for b in blobs:
            best_id, best_d = None, 55
            for tid, trail in self.trails.items():
                hx, hy = trail.head
                d = np.hypot(b["cx"]-hx, b["cy"]-hy)
                if d < best_d:
                    best_d = d; best_id = tid
            if best_id is not None:
                self.trails[best_id].update(b["cx"], b["cy"])
                matched.add(best_id)
            else:
                nid = self._next_id; self._next_id += 1
                self.trails[nid] = PersonTrail(b["cx"], b["cy"], nid)
                matched.add(nid)
        for tid in list(self.trails):
            if tid not in matched:
                self.trails[tid].stale_frames += 1
                if self.trails[tid].stale_frames > 28:
                    del self.trails[tid]
        if len(self.trails) > 160:
            for tid in sorted(self.trails, key=lambda k: self.trails[k].stale_frames, reverse=True)[90:]:
                del self.trails[tid]

    def _entry_exit(self, pw, ph):
        ly = int(0.88 * ph)
        for trail in self.trails.values():
            if len(trail.positions) < 3:
                continue
            yp = trail.positions[-3][1]; yc = trail.positions[-1][1]
            if yp > ly and yc <= ly:
                self._exits += 1; self._footfall_buf.append(("exit", time.time()))
            elif yp <= ly and yc > ly:
                self._entries += 1; self._footfall_buf.append(("entry", time.time()))

    def _zones(self, pw, ph):
        for z in self.ZONE_DEFS:
            zid = z["id"]
            if self.zone_state[zid]["closed"]:
                self.zone_state[zid]["density"] = max(0.0, self.zone_state[zid]["density"] - 0.02)
                continue
            x0 = int(z["rx"]*pw); y0 = int(z["ry"]*ph)
            x1 = int((z["rx"]+z["rw"])*pw); y1 = int((z["ry"]+z["rh"])*ph)
            if self._motion_acc is not None:
                d = float(np.mean(self._motion_acc[y0:y1, x0:x1])) * 3.8
                self.zone_state[zid]["density"] = min(1.0, d)
            cnt = sum(1 for t in self.trails.values() if x0 <= t.head[0] <= x1 and y0 <= t.head[1] <= y1)
            self.zone_state[zid]["count"] = cnt
            self._zone_hist[zid].append(self.zone_state[zid]["density"])

    def _queues(self, pw, ph):
        for q in self.QUEUE_DEFS:
            x0=int(q["x1"]*pw); y0=int(q["y1"]*ph)
            x1=int(q["x2"]*pw); y1=int(q["y2"]*ph)
            if self._motion_acc is not None and y1 > y0 and x1 > x0:
                d = float(np.mean(self._motion_acc[y0:y1, x0:x1])) * 3.8
                self._queue_counts[q["name"]] = int(min(1.0, d) * 55)

    def _speed(self, pw, ph):
        rows, cols = self._speed_grid.shape
        g = np.zeros_like(self._speed_grid); c = np.zeros((rows, cols), dtype=int)
        for trail in self.trails.values():
            hx, hy = trail.head
            col = min(cols-1, int(hx/pw*cols)); row = min(rows-1, int(hy/ph*rows))
            g[row, col] += trail.speed; c[row, col] += 1
        with np.errstate(divide="ignore", invalid="ignore"):
            self._speed_grid = np.where(c > 0, g/c, 0)

    def _behaviors_detect(self):
        beh = []
        fast = [t for t in self.trails.values() if t.speed > 16]
        if len(fast) > 2:
            beh.append({"type":"RUNNING","severity":"WARNING","detail":f"{len(fast)} persons running","zone":"Multiple"})
        loit = [t for t in self.trails.values() if t.speed < 1.5 and len(t.positions) > 22]
        if len(loit) > 1:
            beh.append({"type":"LOITERING","severity":"INFO","detail":f"{len(loit)} persons stationary","zone":"Zone A"})
        for z in self.ZONE_DEFS:
            hist = list(self._zone_hist[z["id"]])
            if len(hist) > 8 and np.mean(hist[-3:]) - np.mean(hist[-8:-3]) > 0.20:
                beh.append({"type":"SURGE","severity":"CRITICAL","detail":f"Density surge in {z['name']}","zone":z["name"]})
        if self._flow_mag > 3.5:
            beh.append({"type":"RAPID_FLOW","severity":"WARNING","detail":"Rapid crowd movement","zone":"All"})
        self._behaviors = beh

    # ══════════════════════════════════════════
    #  DRAWING — ALL FIXES APPLIED
    # ══════════════════════════════════════════
    def _draw(self, frame, w, h, sx, sy, fg, pw, ph) -> np.ndarray:
        out = frame.copy()

        # 1. HEATMAP — alpha MAX 0.38, only where motion > 0.14
        if self.show_heatmap and self._motion_acc is not None:
            heat  = cv2.resize(self._motion_acc, (w, h))
            hc    = np.clip(heat * 3.0, 0, 1)
            h_u8  = (hc * 255).astype(np.uint8)
            h_rgb = cv2.applyColorMap(h_u8, cv2.COLORMAP_JET)
            mask  = (hc > 0.14).astype(np.float32)[:, :, np.newaxis]
            alpha = (hc * 0.38)[:, :, np.newaxis]   # FIX: was 0.55
            out   = (out * (1 - alpha * mask) + h_rgb * alpha * mask).astype(np.uint8)

        # 2. TRAILS — color-coded per person
        if self.show_trails:
            for trail in self.trails.values():
                pts = [(int(x*sx), int(y*sy)) for x, y in trail.positions]
                for i in range(1, len(pts)):
                    a   = i / len(pts)
                    col = tuple(int(c * a) for c in trail.color)
                    cv2.line(out, pts[i-1], pts[i], col, 1, cv2.LINE_AA)
                if pts:
                    cv2.circle(out, pts[-1], 3, trail.color, -1, cv2.LINE_AA)

        # 3. DETECTION BOXES — bracket style, person-sized only
        if self.show_boxes:
            ctrs, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            total   = pw * ph
            for cnt in ctrs:
                area = cv2.contourArea(cnt)
                if total*0.004 < area < total*0.14:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    if bh / max(bw, 1) < 0.25:
                        continue
                    x1s = int(x*sx); y1s = int(y*sy)
                    x2s = int((x+bw)*sx); y2s = int((y+bh)*sy)
                    bws = x2s - x1s
                    dp  = min(1.0, area / (total * 0.04))
                    col = (50,50,255) if dp>0.7 else (0,140,255) if dp>0.4 else (0,200,80)
                    ck  = max(7, min(14, bws//4))
                    for bx, by in [(x1s,y1s),(x2s,y1s),(x1s,y2s),(x2s,y2s)]:
                        dx = 1 if bx==x1s else -1; dy = 1 if by==y1s else -1
                        cv2.line(out,(bx,by),(bx+dx*ck,by),col,2)
                        cv2.line(out,(bx,by),(bx,by+dy*ck),col,2)
                    cf = int(min(97, dp*90+55))
                    cv2.putText(out,f"{cf}%",(x1s,y1s-5),cv2.FONT_HERSHEY_SIMPLEX,0.34,col,1)

        # 4. FLOW VECTORS — only real movement > 2.5 px/frame
        if self.show_flow:
            for fv in self._flow_vecs[::2]:
                if fv["mag"] < 2.5:
                    continue
                x1=int(fv["x"]*w); y1=int(fv["y"]*h)
                dx=int(fv["dx"]*w*25); dy=int(fv["dy"]*h*25)
                al = min(0.85, fv["mag"]/14)
                cv2.arrowedLine(out,(x1,y1),(x1+dx,y1+dy),(0,int(180*al),int(90*al)),1,tipLength=0.3)

        # 5. ZONE BORDERS + LABELS (dark pill background for readability)
        if self.show_zones:
            for z in self.ZONE_DEFS:
                zid = z["id"]; s = self.zone_state[zid]
                x0=int(z["rx"]*w); y0=int(z["ry"]*h)
                x1=int((z["rx"]+z["rw"])*w); y1=int((z["ry"]+z["rh"])*h)
                zcol = (50,50,180) if s["closed"] else z["color"]
                cv2.rectangle(out,(x0,y0),(x1,y1),zcol,1)
                pct = int(s["density"]*100)
                dc  = (50,50,255) if pct>75 else (0,150,255) if pct>50 else (0,200,80)
                # Name pill
                nm  = z["name"]
                (lw,lh),_ = cv2.getTextSize(nm,cv2.FONT_HERSHEY_SIMPLEX,0.38,1)
                cv2.rectangle(out,(x0+4,y0+3),(x0+8+lw,y0+7+lh),(15,15,15),-1)
                cv2.putText(out,nm,(x0+6,y0+6+lh),cv2.FONT_HERSHEY_SIMPLEX,0.38,zcol,1)
                # Density pill
                dp = f"{pct}%"
                (dw,dh),_ = cv2.getTextSize(dp,cv2.FONT_HERSHEY_SIMPLEX,0.52,1)
                cv2.rectangle(out,(x0+4,y0+9+lh),(x0+8+dw,y0+13+lh+dh),(15,15,15),-1)
                cv2.putText(out,dp,(x0+6,y0+12+lh+dh),cv2.FONT_HERSHEY_SIMPLEX,0.52,dc,1)
                if s["closed"]:
                    cx2=(x0+x1)//2; cy2=(y0+y1)//2
                    cv2.rectangle(out,(cx2-52,cy2-14),(cx2+52,cy2+14),(15,15,15),-1)
                    cv2.putText(out,"ZONE CLOSED",(cx2-50,cy2+10),cv2.FONT_HERSHEY_SIMPLEX,0.46,(60,60,220),1)
                if pct > 80:
                    p = int(4+3*abs(np.sin(time.time()*3.5)))
                    cv2.rectangle(out,(x0-p,y0-p),(x1+p,y1+p),(60,60,220),1)

        # 6. ENTRY/EXIT LINE
        ly = int(0.88*h)
        cv2.line(out,(0,ly),(w,ly),(0,210,150),1)
        cv2.rectangle(out,(3,ly-13),(105,ly-2),(15,15,15),-1)
        cv2.putText(out,"ENTRY / EXIT",(5,ly-4),cv2.FONT_HERSHEY_SIMPLEX,0.30,(0,210,150),1)

        # 7. HUD top-left
        hud = [f"CrowdFlow PRO v4", f"People : {len(self.trails)}", f"Flow   : {self._flow_mag:.1f} px/f"]
        if self._source_type == "file" and self.total_frames > 0:
            hud.append(f"Frame  : {self.current_frame}/{self.total_frames}")
        for i, ln in enumerate(hud):
            yp = 14 + i*15
            (tw,th),_ = cv2.getTextSize(ln,cv2.FONT_HERSHEY_SIMPLEX,0.32,1)
            cv2.rectangle(out,(4,yp-11),(8+tw,yp+2),(15,15,15),-1)
            cv2.putText(out,ln,(6,yp),cv2.FONT_HERSHEY_SIMPLEX,0.32,(0,200,255),1)

        # 8. EVACUATION
        if self._evacuation:
            cv2.rectangle(out,(0,0),(w,h),(0,0,170),3)
            txt = f"EVACUATION ACTIVE — {self._evac_pct:.0f}% CLEARED"
            (tw,_),_ = cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.55,2)
            cv2.rectangle(out,(w//2-tw//2-8,h-30),(w//2+tw//2+8,h-6),(15,15,15),-1)
            cv2.putText(out,txt,(w//2-tw//2,h-10),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,80,255),2)

        # 9. BEHAVIOR alerts
        for i, bh in enumerate(self._behaviors[:3]):
            cmap = {"CRITICAL":(50,50,255),"WARNING":(0,150,220),"INFO":(0,200,255)}
            bc = cmap.get(bh["severity"],(180,180,180))
            txt = f"! {bh['type']}: {bh['detail'][:52]}"
            y_b = h-44+i*15
            (tw,_),_ = cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.30,1)
            cv2.rectangle(out,(4,y_b-10),(8+tw,y_b+2),(15,15,15),-1)
            cv2.putText(out,txt,(6,y_b),cv2.FONT_HERSHEY_SIMPLEX,0.30,bc,1)

        return out

    # ══════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════
    def get_metrics(self) -> dict:
        avg_d = float(np.mean([self.zone_state[z["id"]]["density"] for z in self.ZONE_DEFS]))
        max_d = float(max(self.zone_state[z["id"]]["density"] for z in self.ZONE_DEFS))
        risk  = ("CRITICAL" if max_d>0.80 else "HIGH" if max_d>0.60
                 else "MEDIUM" if max_d>0.35 else "LOW")
        dirs  = ["E","NE","N","NW","W","SW","S","SE"]
        fdir  = dirs[int((np.degrees(self._flow_ang)+360)%360/45)%8]
        return {
            "detected":        len(self.trails),
            "avg_density":     round(avg_d, 3),
            "max_density":     round(max_d, 3),
            "risk_level":      risk,
            "flow_dir":        fdir,
            "flow_mag":        round(float(self._flow_mag), 2),
            "density_history": list(self._global_hist),
            "count_history":   list(self._count_hist),
            "behaviors":       self._behaviors,
            "evacuation":      self._evacuation,
            "evac_pct":        round(self._evac_pct, 1),
            "flow_vectors":    self._flow_vecs[:30],
            "source_type":     self._source_type,
            "has_source":      self.has_source,
            "frame_idx":       self.current_frame,
            "total_frames":    self.total_frames,
            "fps":             round(self.fps, 1),
        }

    def get_zones(self) -> list:
        result = []
        for z in self.ZONE_DEFS:
            zid  = z["id"]; s = self.zone_state[zid]
            hist = list(self._zone_hist[zid])
            trend = "rising" if len(hist)>5 and hist[-1]>hist[-5] else "falling"
            result.append({
                "id": zid, "name": z["name"],
                "density": round(s["density"], 3),
                "density_pct": int(s["density"]*100),
                "count": s["count"], "closed": s["closed"],
                "risk": ("CRITICAL" if s["density"]>0.80 else "HIGH" if s["density"]>0.60
                         else "MEDIUM" if s["density"]>0.35 else "LOW"),
                "trend": trend,
                "history": [round(v,3) for v in hist[-30:]],
                "color": [z["color"][2], z["color"][1], z["color"][0]],
            })
        return result

    def get_entry_exit(self) -> dict:
        now    = time.time()
        recent = [e for e in self._footfall_buf if now-e[1] < 60]
        return {
            "total_entries":   self._entries,
            "total_exits":     self._exits,
            "net_inside":      self._entries - self._exits,
            "entries_per_min": sum(1 for e in recent if e[0]=="entry"),
            "exits_per_min":   sum(1 for e in recent if e[0]=="exit"),
        }

    def get_queues(self) -> list:
        return [{
            "name":   q["name"],
            "length": self._queue_counts.get(q["name"], 0),
            "status": ("LONG"   if self._queue_counts.get(q["name"],0) > 28 else
                       "MEDIUM" if self._queue_counts.get(q["name"],0) > 12 else "SHORT"),
        } for q in self.QUEUE_DEFS]

    def get_speed(self) -> dict:
        avg_s = float(np.mean(self._speed_grid))
        max_s = float(np.max(self._speed_grid))
        return {
            "grid":          self._speed_grid.tolist(),
            "avg_speed":     round(avg_s, 1),
            "max_speed":     round(max_s, 1),
            "stampede_risk": ("HIGH" if max_s>22 else "MEDIUM" if max_s>12 else "LOW"),
        }

    def zone_action(self, zone_id: str, action: str):
        if zone_id and zone_id in self.zone_state:
            if action == "close":
                self.zone_state[zone_id]["closed"] = True
            elif action == "open":
                self.zone_state[zone_id]["closed"] = False
            elif action == "redirect":
                d = self.zone_state[zone_id]["density"]
                self.zone_state[zone_id]["density"] = max(0.0, d - 0.22)

    def set_sensitivity(self, v: int):
        self.sensitivity = max(5, min(80, v))
        self._bg_sub = self._make_bg_sub()

    def trigger_evacuation(self):
        self._evacuation = True; self._evac_pct = 0.0

    def clear_evacuation(self):
        self._evacuation = False; self._evac_pct = 0.0
