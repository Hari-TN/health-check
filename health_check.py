import requests
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from api_config import APIS

# ============================================================
# STEP 1 — GET TOKEN FROM AUTH API
# ============================================================
def get_token(api):
    try:
        if api["auth_method"].upper() == "POST":
            resp = requests.post(api["auth_url"], json=api["auth_body"], timeout=10)
        else:
            resp = requests.get(api["auth_url"], params=api["auth_body"], timeout=10)

        if resp.status_code != 200:
            return None, f"Auth API returned HTTP {resp.status_code}", resp.status_code

        token = resp.json().get(api["token_field"])
        if not token:
            keys = list(resp.json().keys())
            return None, f"Token field '{api['token_field']}' not found. Keys: {keys}", resp.status_code

        return token, None, resp.status_code

    except requests.exceptions.Timeout:
        return None, "Auth API timed out", "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to Auth API", "CONN_ERR"
    except Exception as e:
        return None, f"Auth error: {str(e)}", "ERROR"


# ============================================================
# STEP 2 — CALL HEALTH CHECK API WITH TOKEN
# ============================================================
def get_nested_value(data, path):
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


def check_health(api, token):
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        if api["check_method"].upper() == "POST":
            resp = requests.post(api["check_url"], headers=headers, timeout=10)
        else:
            resp = requests.get(api["check_url"], headers=headers, timeout=10)

        if resp.status_code != 200:
            return False, f"API returned HTTP {resp.status_code}", resp.status_code

        value = get_nested_value(resp.json(), api["success_path"])

        if str(value).strip() == str(api["success_value"]).strip():
            return True, f"{api['success_path']} = {value}", resp.status_code
        else:
            return False, f"Got '{value}' expected '{api['success_value']}'", resp.status_code

    except requests.exceptions.Timeout:
        return False, "API timed out (>10 seconds)", "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API", "CONN_ERR"
    except Exception as e:
        return False, f"Error: {str(e)}", "ERROR"


# ============================================================
# RUN ALL API CHECKS
# ============================================================
def run_all_checks(apis):
    results = []
    for api in apis:
        name   = api["name"]
        result = {"name": name, "healthy": False, "detail": "", "http_code": "-", "subtitle": api.get("subtitle", "")}

        print(f"\n🔍 Checking: {name}")

        token, auth_error, auth_code = get_token(api)
        result["auth_code"] = auth_code

        if not token:
            result["detail"]    = f"Auth failed — {auth_error}"
            result["http_code"] = auth_code
            print(f"  ❌ Auth failed: {auth_error}")
            results.append(result)
            continue

        print(f"  ✅ Token received")

        is_healthy, detail, http_code = check_health(api, token)
        result["healthy"]   = is_healthy
        result["detail"]    = detail
        result["http_code"] = http_code

        print(f"  {'✅' if is_healthy else '❌'} {detail}")
        results.append(result)

    return results


# ============================================================
# BUILD HTML EMAIL — DMQ STYLE KPI CARDS
# ============================================================
def build_html_report(results, now):
    total   = len(results)
    healthy = sum(1 for r in results if r["healthy"])
    failed  = total - healthy
    pct     = round((healthy / total) * 100) if total > 0 else 0

    if pct == 100:
        pct_color    = "#16a34a"
        pct_gradient = "linear-gradient(90deg,#16a34a,#4ade80)"
        status_emoji = "✅"
        status_line  = "All APIs are healthy"
        alert_color  = "#16a34a"
        show_alert   = False
    elif pct >= 80:
        pct_color    = "#d97706"
        pct_gradient = "linear-gradient(90deg,#d97706,#fbbf24)"
        status_emoji = "⚠️"
        status_line  = f"{failed} API(s) showing degraded performance"
        alert_color  = "#d97706"
        show_alert   = True
    else:
        pct_color    = "#dc2626"
        pct_gradient = "linear-gradient(90deg,#dc2626,#f87171)"
        status_emoji = "🚨"
        status_line  = f"Some APIs Failed Health Check"
        alert_color  = "#dc2626"
        show_alert   = True

    # ── KPI cards — DMQ style ─────────────────────────────
    # Failed card gets grey background like DMQ, others stay white
    failed_card_bg = "#f5f5f5" if failed > 0 else "#fff"
    score_color    = pct_color

    kpi_cards = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e0e0e0;border-collapse:collapse;margin-bottom:24px;">
      <tr>
        <td width="25%" style="padding:20px 24px;text-align:center;border-right:1px solid #e0e0e0;background:#fff;vertical-align:top;">
          <div style="font-size:32px;font-weight:700;color:#1a56db;line-height:1;margin-bottom:6px;">{total}</div>
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Total APIs</div>
        </td>
        <td width="25%" style="padding:20px 24px;text-align:center;border-right:1px solid #e0e0e0;background:#fff;vertical-align:top;">
          <div style="font-size:32px;font-weight:700;color:#16a34a;line-height:1;margin-bottom:6px;">{healthy}</div>
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Healthy</div>
        </td>
        <td width="25%" style="padding:20px 24px;text-align:center;border-right:1px solid #e0e0e0;background:{failed_card_bg};vertical-align:top;">
          <div style="font-size:32px;font-weight:700;color:#dc2626;line-height:1;margin-bottom:6px;">{failed}</div>
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Failed</div>
        </td>
        <td width="25%" style="padding:20px 24px;text-align:center;background:#fff;vertical-align:top;">
          <div style="font-size:32px;font-weight:700;color:{score_color};line-height:1;margin-bottom:6px;">{pct}%</div>
          <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Health Score</div>
        </td>
      </tr>
    </table>"""

    # ── Alert banner ──────────────────────────────────────
    alert_html = ""
    if show_alert:
        alert_html = f"""
    <div style="background:#fee2e2;border-left:6px solid #dc2626;
        padding:14px 40px;display:flex;align-items:center;gap:12px;margin-bottom:0;">
      <span style="font-size:20px;">🚨</span>
      <div>
        <span style="font-size:14px;font-weight:700;color:#991b1b;">
          ALERT — {failed} API(s) are failing
        </span>
        <span style="font-size:12px;color:#b91c1c;margin-left:12px;">
          Immediate attention required
        </span>
      </div>
    </div>"""

    # ── Table rows ────────────────────────────────────────
    rows = ""
    for r in results:
        if r["healthy"]:
            row_bg       = "#fff"
            border_color = "#16a34a"
            badge        = '<span style="background:#dcfce7;color:#16a34a;padding:4px 12px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap;">✓ HEALTHY</span>'
            detail_color = "#64748b"
            http_bg      = "#dbeafe"
            http_color   = "#1d4ed8"
        else:
            row_bg       = "#fff9f9"
            border_color = "#dc2626"
            badge        = '<span style="background:#fee2e2;color:#dc2626;padding:4px 12px;border-radius:999px;font-size:11px;font-weight:700;white-space:nowrap;">✗ FAILED</span>'
            detail_color = "#dc2626"
            http_bg      = "#fee2e2"
            http_color   = "#dc2626"

        http_code = str(r["http_code"])
        if http_code == "TIMEOUT":
            http_bg    = "#fef3c7"
            http_color = "#d97706"

        subtitle_html = f'<div style="font-size:11px;color:#94a3b8;margin-top:2px;">{r["subtitle"]}</div>' if r.get("subtitle") else ""

        rows += f"""
        <tr style="background:{row_bg};border-left:4px solid {border_color};">
          <td style="padding:14px 16px;font-size:13px;color:#0f172a;font-weight:600;border-bottom:1px solid #f1f5f9;">
            <div>{r['name']}</div>{subtitle_html}
          </td>
          <td style="padding:14px 16px;text-align:center;border-bottom:1px solid #f1f5f9;">{badge}</td>
          <td style="padding:14px 16px;font-size:12px;color:{detail_color};border-bottom:1px solid #f1f5f9;">{r['detail']}</td>
          <td style="padding:14px 16px;text-align:center;border-bottom:1px solid #f1f5f9;">
            <span style="background:{http_bg};color:{http_color};padding:3px 8px;border-radius:6px;font-size:11px;font-weight:600;">{http_code}</span>
          </td>
        </tr>"""

    # ── Failed APIs summary ───────────────────────────────
    failed_summary = ""
    failed_apis    = [r for r in results if not r["healthy"]]
    if failed_apis:
        failed_items = ""
        for r in failed_apis:
            failed_items += f"""
          <div style="background:#fff9f9;border-radius:8px;padding:12px 16px;
              margin-bottom:8px;border-left:3px solid #dc2626;">
            <div style="font-size:13px;color:#0f172a;font-weight:600;">{r['name']}</div>
            <div style="font-size:12px;color:#dc2626;margin-top:3px;">{r['detail']}</div>
          </div>"""

        failed_summary = f"""
    <div style="background:#fff;border-radius:16px;padding:22px 28px;
        box-shadow:0 4px 12px rgba(0,0,0,0.08);border:1px solid #fee2e2;margin-bottom:24px;">
      <div style="font-size:13px;color:#991b1b;font-weight:700;margin-bottom:14px;">
        🚨 Failed APIs — Action Required
      </div>
      {failed_items}
    </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0f2a5e 0%,#1a56db 60%,#3b82f6 100%);
      padding:40px;text-align:center;position:relative;overflow:hidden;">
    <div style="position:absolute;top:-40px;right:-40px;width:200px;height:200px;
        background:rgba(255,255,255,0.05);border-radius:50%;"></div>
    <div style="position:absolute;bottom:-60px;left:-20px;width:160px;height:160px;
        background:rgba(255,255,255,0.04);border-radius:50%;"></div>
    <div style="font-size:12px;color:#93c5fd;letter-spacing:3px;
        text-transform:uppercase;margin-bottom:8px;">Automated Monitoring</div>
    <h1 style="color:#fff;margin:0;font-size:28px;font-weight:700;letter-spacing:1px;">
      {status_emoji} BOP API Health Report
    </h1>
    <p style="color:#bfdbfe;margin:10px 0 0;font-size:14px;">{now}</p>
  </div>

  {alert_html}

  <div style="padding:28px 32px;">

    <!-- Intro -->
    <p style="font-size:13px;color:#333;margin:0 0 6px;">Hi Team,</p>
    <p style="font-size:13px;color:#333;margin:0 0 12px;">
      Please find below the BOP API health check summary report.
    </p>
    <p style="font-size:13px;font-weight:700;color:{alert_color};margin:0 0 20px;">
      {status_emoji} {status_line}
    </p>

    <!-- KPI Cards — DMQ style -->
    {kpi_cards}

    <!-- Progress Bar -->
    <div style="background:#fff;border-radius:16px;padding:22px 28px;
        box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-bottom:24px;">
      <div style="display:flex;justify-content:space-between;
          align-items:center;margin-bottom:12px;">
        <span style="font-size:13px;color:#475569;font-weight:600;
            text-transform:uppercase;letter-spacing:1px;">System Health Overview</span>
        <span style="font-size:13px;color:{pct_color};font-weight:700;">
          {healthy} of {total} healthy
        </span>
      </div>
      <div style="background:#f1f5f9;border-radius:999px;height:16px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{pct_gradient};
            border-radius:999px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:8px;">
        <span style="font-size:11px;color:#94a3b8;">0%</span>
        <span style="font-size:11px;color:#94a3b8;">Critical threshold: 80%</span>
        <span style="font-size:11px;color:#94a3b8;">100%</span>
      </div>
    </div>

    <!-- Failed APIs Summary -->
    {failed_summary}

    <!-- Results Table -->
    <div style="background:#fff;border-radius:16px;padding:24px;
        box-shadow:0 4px 12px rgba(0,0,0,0.08);margin-bottom:24px;">
      <div style="display:flex;justify-content:space-between;
          align-items:center;margin-bottom:20px;">
        <span style="font-size:14px;color:#0f172a;font-weight:700;">API Status Details</span>
        <span style="font-size:12px;color:#94a3b8;">Last checked: {now}</span>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <tr style="background:#f8fafc;">
          <th style="text-align:left;padding:12px 16px;font-size:11px;color:#64748b;
              font-weight:700;border-bottom:2px solid #e2e8f0;text-transform:uppercase;
              letter-spacing:1px;">API Name</th>
          <th style="text-align:center;padding:12px 16px;font-size:11px;color:#64748b;
              font-weight:700;border-bottom:2px solid #e2e8f0;text-transform:uppercase;
              letter-spacing:1px;">Status</th>
          <th style="text-align:left;padding:12px 16px;font-size:11px;color:#64748b;
              font-weight:700;border-bottom:2px solid #e2e8f0;text-transform:uppercase;
              letter-spacing:1px;">Details</th>
          <th style="text-align:center;padding:12px 16px;font-size:11px;color:#64748b;
              font-weight:700;border-bottom:2px solid #e2e8f0;text-transform:uppercase;
              letter-spacing:1px;">Response</th>
        </tr>
        {rows}
      </table>
    </div>

    <!-- Sign off -->
    <p style="font-size:13px;color:#333;margin:0 0 4px;">Best regards,</p>
    <p style="font-size:13px;font-weight:700;color:#333;margin:0 0 20px;">
      BOP API Monitoring System
    </p>

  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:20px 24px;color:#9ca3af;font-size:11px;
      border-top:1px solid #e2e8f0;">
    Automated message from the BOP API Monitoring System.
    This mailbox is not monitored — please do not reply.
  </div>

</body>
</html>"""

    return html, total, healthy, failed


# ============================================================
# SEND EMAIL VIA GMAIL SMTP
# ============================================================
def send_email(html_body, failed_count):
    email_from = os.environ["EMAIL_FROM"]
    email_to   = os.environ["EMAIL_TO"]
    password   = os.environ["EMAIL_PASS"]
    status_str = "All APIs Healthy" if failed_count == 0 else f"{failed_count} API(s) Failed"

    msg = MIMEMultipart("alternative")
    msg["From"]    = email_from
    msg["To"]      = email_to
    msg["Subject"] = f"BOP API Health Report — {datetime.now().strftime('%d %b %Y')} — {status_str}"
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(email_from, password)
        server.send_message(msg)
        print("\n✅ Email sent successfully!")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    now = datetime.now().strftime("%d %b %Y %I:%M %p")

    print("=" * 50)
    print(f"BOP API Health Check — {now}")
    print(f"Total APIs to check: {len(APIS)}")
    print("=" * 50)

    results = run_all_checks(APIS)
    html, total, healthy, failed = build_html_report(results, now)

    print("\n" + "=" * 50)
    print(f"SUMMARY: Total={total} | Healthy={healthy} | Failed={failed}")
    print("=" * 50)

    send_email(html, failed)
