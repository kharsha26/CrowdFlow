# ml/threat.py  —  Weapon detection & person classification
import time, random

WEAPONS = [
    "Suspected knife", "Suspected firearm",
    "Suspected blunt weapon", "Suspected explosive device",
]

SCENE_PERSONS = [
    {"id":"P-001","name":"Person A-01",  "type":"CIVILIAN", "zone":"Zone A","weapon":None,                     "threat":False},
    {"id":"P-002","name":"Person B-02",  "type":"CIVILIAN", "zone":"Zone B","weapon":None,                     "threat":False},
    {"id":"P-003","name":"Person C-03",  "type":"CIVILIAN", "zone":"Zone C","weapon":None,                     "threat":False},
    {"id":"P-004","name":"Officer K-12", "type":"POLICE",   "zone":"Zone B","weapon":"Service pistol (auth)", "threat":False},
    {"id":"P-005","name":"Sgt. Rajan V.","type":"ARMY",     "zone":"Zone C","weapon":"Auth rifle",             "threat":False},
    {"id":"P-006","name":"Guard Unit-3", "type":"SECURITY", "zone":"Zone D","weapon":"Auth baton",             "threat":False},
]

AUTH_TYPES = {"POLICE", "ARMY", "SECURITY", "GOVT_SECURITY"}


class ThreatDetector:
    def __init__(self):
        self._threats  = []
        self._persons  = [dict(p) for p in SCENE_PERSONS]
        self._log      = []

    def simulate_weapon(self, zone: str) -> dict:
        """
        Simulate weapon detection.
        RULE: Civilian → civilian broadcast.
              Police/Army/Security → secure channel ONLY (excluded from civilian alert).
        """
        weapon = random.choice(WEAPONS)
        sid    = f"P-{random.randint(100,999):03d}"
        ts     = time.strftime("%H:%M:%S")
        threat = {
            "id": sid, "name": f"Unknown ({sid})",
            "type": "CIVILIAN", "zone": zone,
            "weapon": weapon, "threat": True,
            "confidence":  round(random.uniform(0.78, 0.97), 2),
            "timestamp":   ts,
            "authority":   False,
            "civilian_notified":   True,
            "security_dispatched": True,
            "notification_text":   (
                f"{weapon} detected near {zone}. "
                f"Move calmly to the nearest exit."),
            "authority_note": (
                "Police/Army/Security excluded from civilian broadcast — "
                "briefed via silent secure command channel."),
        }
        self._threats.append(threat)
        self._persons.append({
            "id": sid, "name": f"Unknown ({sid})",
            "type": "CIVILIAN", "zone": zone,
            "weapon": weapon, "threat": True,
        })
        self._log.append({
            "time": ts, "channel": "CIVILIAN_BROADCAST",
            "msg":  f"Weapon alert sent to civilians in {zone}",
            "excluded": "Police · Army · Security",
        })
        self._log.append({
            "time": ts, "channel": "SECURE_COMMAND",
            "msg":  f"Silent alert → security team | {zone}",
            "excluded": "N/A",
        })
        return threat

    def is_authority(self, person_type: str) -> bool:
        return person_type in AUTH_TYPES

    def get_threats(self):  return self._threats
    def get_persons(self):  return self._persons
    def get_log(self):      return self._log
    def clear(self):
        self._threats = []
        self._persons = [dict(p) for p in SCENE_PERSONS]
        self._log     = []
