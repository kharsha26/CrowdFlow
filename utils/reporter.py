# utils/reporter.py  --  JSON + HTML report generation
import time


class Reporter:

    def json_report(self, metrics, threats, incidents, alerts, ee):
        s = metrics
        return {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id":   "CF-{:05d}".format(int(time.time()) % 100000),
            "summary": {
                "detected":        s.get("detected", 0),
                "avg_density":     s.get("avg_density", 0),
                "risk_level":      s.get("risk_level", "LOW"),
                "total_entries":   ee.get("total_entries", 0),
                "total_exits":     ee.get("total_exits", 0),
                "net_inside":      ee.get("net_inside", 0),
                "active_threats":  len(threats),
                "total_incidents": len(incidents),
                "total_alerts":    len(alerts),
                "behaviors":       s.get("behaviors", []),
            },
            "threats":   threats,
            "incidents": incidents[:25],
            "alerts":    alerts[:25],
        }

    def html_report(self, metrics, threats, incidents, alerts, ee):
        d  = self.json_report(metrics, threats, incidents, alerts, ee)
        s  = d["summary"]
        r  = s["risk_level"]
        color_map = {
            "CRITICAL": "#ff2040",
            "HIGH":     "#ff7b00",
            "MEDIUM":   "#ffcc00",
            "LOW":      "#00ff9d",
        }
        rc = color_map.get(r, "#aaa")

        # Threat rows
        tr_parts = []
        for t in threats:
            tr_parts.append(
                "<tr>"
                "<td>{}</td><td>{}</td>"
                "<td style='color:#ff2040'>{}</td>"
                "<td>{}</td>"
                "<td style='color:#4da6ff'>Civilian notified</td>"
                "</tr>".format(
                    t.get("id",""), t.get("zone",""),
                    t.get("weapon",""), t.get("timestamp","")
                )
            )
        threat_rows = "".join(tr_parts) if tr_parts else \
            "<tr><td colspan='5' style='color:#444'>No threats</td></tr>"

        # Incident rows
        inc_parts = []
        for i in incidents[:20]:
            inc_parts.append(
                "<tr><td style='font-size:10px'>{}</td><td>{}</td><td>{}</td></tr>".format(
                    i["time"], i["zone"], i["message"]
                )
            )
        inc_rows = "".join(inc_parts) if inc_parts else \
            "<tr><td colspan='3' style='color:#444'>No incidents</td></tr>"

        # Behavior rows
        beh_parts = []
        for b in s.get("behaviors", []):
            beh_color = "#ff2040" if b["severity"] == "CRITICAL" else "#ffcc00"
            beh_parts.append(
                "<tr><td style='color:{}'>{}</td><td>{}</td><td>{}</td></tr>".format(
                    beh_color, b["type"], b["detail"], b["zone"]
                )
            )
        beh_rows = "".join(beh_parts) if beh_parts else \
            "<tr><td colspan='3' style='color:#444'>Normal behavior</td></tr>"

        gen = d["generated_at"]
        sid = d["session_id"]
        det = s["detected"]
        dens_pct = round(s["avg_density"] * 100)
        entries  = s["total_entries"]
        exits    = s["total_exits"]
        net      = s["net_inside"]
        t_count  = s["active_threats"]
        i_count  = s["total_incidents"]

        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>CrowdFlow PRO v4 Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#020b10;color:#aac8d8;font-family:'Courier New',monospace;padding:32px;line-height:1.65;}}
h1{{font-size:19px;letter-spacing:3px;color:#00e0ff;margin-bottom:4px;}}
h2{{font-size:11px;letter-spacing:2px;color:#00e0ff;margin:22px 0 8px;border-bottom:1px solid #0a2030;padding-bottom:5px;text-transform:uppercase;}}
.meta{{font-size:10px;color:#2a5a6a;margin-bottom:18px;}}
.stats{{display:flex;flex-wrap:wrap;gap:11px;margin:14px 0 20px;}}
.sc{{background:#09202e;border:1px solid rgba(0,224,255,0.12);border-radius:5px;padding:10px 15px;}}
.sv{{font-size:20px;font-weight:700;color:#00e0ff;}}
.sl{{font-size:9px;color:#2a5a6a;letter-spacing:1px;margin-top:2px;}}
.risk{{font-size:20px;font-weight:700;color:{rc};}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin-top:6px;}}
th{{text-align:left;padding:6px 10px;color:#2a5a6a;border-bottom:1px solid #0a2030;font-size:9px;text-transform:uppercase;}}
td{{padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.03);}}
.note{{background:rgba(77,166,255,0.07);border:1px solid rgba(77,166,255,0.2);border-radius:4px;padding:11px 14px;font-size:11px;color:#4da6ff;margin-top:6px;line-height:1.75;}}
.footer{{margin-top:36px;font-size:10px;color:#2a5a6a;border-top:1px solid #0a2030;padding-top:12px;}}
</style>
</head>
<body>
<h1>CROWDFLOW PRO v4 -- CROWD FLOW INCIDENT REPORT</h1>
<div class="meta">Generated: {gen} | Session: {sid}</div>
<div class="stats">
  <div class="sc"><div class="sv">{det}</div><div class="sl">Detected</div></div>
  <div class="sc"><div class="sv">{dens_pct}%</div><div class="sl">Avg Density</div></div>
  <div class="sc"><div class="risk">{r}</div><div class="sl">Risk Level</div></div>
  <div class="sc"><div class="sv" style="color:#00ff9d">{entries}</div><div class="sl">Entries</div></div>
  <div class="sc"><div class="sv" style="color:#ff2040">{exits}</div><div class="sl">Exits</div></div>
  <div class="sc"><div class="sv">{net}</div><div class="sl">Net Inside</div></div>
  <div class="sc"><div class="sv" style="color:#ff2040">{t_count}</div><div class="sl">Threats</div></div>
  <div class="sc"><div class="sv" style="color:#ffcc00">{i_count}</div><div class="sl">Incidents</div></div>
</div>
<h2>Weapon and Threat Incidents</h2>
<table><tr><th>ID</th><th>Zone</th><th>Weapon</th><th>Time</th><th>Action</th></tr>
{threat_rows}
</table>
<h2>Civilian Notification Policy</h2>
<div class="note">
  All weapon alerts broadcast exclusively to civilian attendees.<br/>
  Police, Army, Security excluded -- briefed via silent secure command channel.<br/>
  Dual-channel approach: prevents panic + ensures rapid authorised response.
</div>
<h2>Behavior Analysis</h2>
<table><tr><th>Type</th><th>Detail</th><th>Zone</th></tr>
{beh_rows}
</table>
<h2>Incident Log</h2>
<table><tr><th>Time</th><th>Zone</th><th>Description</th></tr>
{inc_rows}
</table>
<div class="footer">CrowdFlow PRO v4.0 | Smart Surveillance Platform | {gen}</div>
</body>
</html>""".format(
            rc=rc, gen=gen, sid=sid,
            det=det, dens_pct=dens_pct, r=r,
            entries=entries, exits=exits, net=net,
            t_count=t_count, i_count=i_count,
            threat_rows=threat_rows, beh_rows=beh_rows, inc_rows=inc_rows,
        )
