# config/settings.py
# ──────────────────────────────────────────────
# Change ACTIVE_PROFILE to switch deployment mode
# ──────────────────────────────────────────────
ACTIVE_PROFILE = "mobile_demo"

PROFILES = {
    "mobile_demo": {
        "name": "Mobile Demo",
        "description": "Phone as CCTV via IP Webcam app",
        "default_source": "http://192.168.1.100:8080/video",
        "source_type": "mobile",
        "sensitivity": 30,
        "alert_threshold": 0.75,
        "enable_weapon": True,
        "enable_face_blur": False,
    },
    "home_cctv": {
        "name": "Home CCTV",
        "description": "IP camera or USB webcam at home",
        "default_source": "rtsp://admin:admin@192.168.1.50:554/stream1",
        "source_type": "rtsp",
        "sensitivity": 25,
        "alert_threshold": 0.80,
        "enable_weapon": False,
        "enable_face_blur": True,
    },
    "mall": {
        "name": "Shopping Mall",
        "description": "Multi-zone mall surveillance",
        "default_source": "rtsp://admin:mall123@10.0.1.20:554/stream",
        "source_type": "rtsp",
        "sensitivity": 35,
        "alert_threshold": 0.70,
        "enable_weapon": True,
        "enable_face_blur": False,
    },
    "public": {
        "name": "Public Space",
        "description": "Street / public area monitoring",
        "default_source": "rtsp://admin:pub@10.0.2.10:554/stream",
        "source_type": "rtsp",
        "sensitivity": 28,
        "alert_threshold": 0.65,
        "enable_weapon": True,
        "enable_face_blur": True,
    },
    "police": {
        "name": "Police / Security",
        "description": "High-security event monitoring",
        "default_source": "rtsp://admin:secure@172.16.0.10:554/stream",
        "source_type": "rtsp",
        "sensitivity": 40,
        "alert_threshold": 0.60,
        "enable_weapon": True,
        "enable_face_blur": False,
    },
}

def get_profile():
    return PROFILES.get(ACTIVE_PROFILE, PROFILES["mobile_demo"])
