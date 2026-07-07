# utils/logger.py  —  Event & incident logger
import time
from collections import deque


class EventLogger:
    def __init__(self):
        self._alerts    = deque(maxlen=120)
        self._incidents = deque(maxlen=100)

    def log(self, event: str, message: str, level: str = "INFO"):
        self._alerts.appendleft({
            "type":      level,
            "event":     event,
            "message":   message,
            "time":      time.strftime("%H:%M:%S"),
            "timestamp": time.time(),
        })

    def incident(self, zone: str, message: str):
        self._incidents.appendleft({
            "zone":      zone,
            "message":   message[:100],
            "time":      time.strftime("%H:%M:%S"),
            "timestamp": time.time(),
        })

    def get_alerts(self, n: int = 15):
        return list(self._alerts)[:n]

    def get_incidents(self, n: int = 30):
        return list(self._incidents)[:n]
