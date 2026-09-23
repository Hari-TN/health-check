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
    """
    Calls the auth URL with credentials.
    Returns the token string or None if failed.
    """
    try:
        if api["auth_method"].upper() == "POST":
            resp = requests.post(
                api["auth_url"],
                json=api["auth_body"],
                timeout=10
            )
        else:
            resp = requests.get(
                api["auth_url"],
                params=api["auth_body"],
                timeout=10
            )

        if resp.status_code != 200:
            return None, f"Auth API returned HTTP {resp.status_code}"

        token = resp.json().get(api["token_field"])
        if not token:
            keys = list(resp.json().keys())
            return None, f"Token field '{api['token_field']}' not found. Response keys: {keys}"

        return token, None

    except requests.exceptions.Timeout:
        return None, "Auth API timed out"
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to Auth API"
    except Exception as e:
        return None, f"Auth error: {str(e)}"


# ============================================================
# STEP 2 — CALL HEALTH CHECK API WITH TOKEN
# ============================================================
def get_nested_value(data, path):
    """
    Reads a dot-separated path from a dict.
    e.g. path="status.code" reads data["status"]["code"]
    """
    keys = path.split(".")
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data


def check_health(api, token):
    """
    Calls the health check URL with Bearer token.
    Returns (is_healthy, detail_message)
    """
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json"
        }

        if api["check_method"].upper() == "POST":
            resp = requests.post(
                api["check_url"],
                headers=headers,
                timeout=10
            )
        else:
            resp = requests.get(
                api["check_url"],
                headers=headers,
                timeout=10
            )

        if resp.status_code != 200:
            return False, f"API returned HTTP {resp.status_code}"

        # Check the success field in response
        value = get_nested_value(resp.json(), api["success_path"])

        if str(value).strip() == str(api["success_value"]).strip():
            return True, f"Healthy — {api['success_path']}={value}"
        else:
            return False, f"Got '{value}' expected '{api['success_value']}'"

    except requests.exceptions.Timeout:
        return False, "API timed out"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================
# RUN ALL API CHECKS — DYNAMIC FOR ANY NUMBER OF APIs
# ============================================================
def run_all_checks(apis):
    """
    Loops through every API in config.
    Returns list of result dicts.
    """
    results = []

    for api in apis:
        name   = api["name"]
        result = {"name": name, "healthy": False, "detail": ""}

        print(f"\n🔍 Checking: {name}")

        # Step 1 — get token
        token, auth_error = get_token(api)
        if not token:
            result["detail"] = f"Auth failed — {auth_error}"
            print(f"  ❌ Auth failed: {auth_error}")
            results.append(result)
            continue

        print(f"  ✅ Token received")

        # Step 2 — check health
        is_healthy, detail = check_health(api, token)
        result["healthy"] = is_healthy
        result["detail"]  = detail

        if is_healthy:
            print(f"  ✅ {detail}")
        else:
            print(f"  ❌ {detail}")

        results.append(result)

    return results


# ============================================================
# BUILD HTML EMAIL REPORT — KPI CARDS + TABLE
# ============================================================
def build_html_report(results, now):
    total   = len(results)
    healthy = sum(1 for r in results if r["healthy"])
    failed  = total - healthy
    pct     = round((healthy / total) * 100) if total > 0 else 0

    # Color based on health score
    if pct == 100:
        pct_color = "#16a34a"
        status_emoji = "✅"
    elif pct >= 80:
        pct_color = "#d97706"
        status_emoji = "⚠️"
    else:
        pct_color = "#dc2626"
        status_emoji = "❌"

    # Build table rows dynamically
    rows = ""
    for i, r in enumerate(results):
        bg     = "#ffffff" if i % 2 == 0 else "#f8fafc"
        badge  = (
            '<span style="background:#dcfce7;color:#16a34a;padding:3px 10px;'
            'border-radius:999px;font-size:11px;font-weight:700;">✓ HEALTHY</span>'
            if r["healthy"] else
            '<span style="background:#fee2e2;color:#dc2626;padding:3px 10px;'
            'border-radius:999px;font-size:11px;font-weight:700;">✗ FAILED</span>'
        )
        rows += f"""
        <tr style="background:{bg};">
            <td style="padding:12px 16px;font-size:13px;color:#1e293b;
                font-weight:500;border-bottom:1px solid #f1f5f9;">
                {r['name']}
            </td>
            <td style="padding:12px 16px;text-align:center;
                border-bottom:1px solid #f1f5f9;">
                {badge}
            </td>
            <td style="padding:12px 16px;font-size:12px;color:#6b7280;
                border-bottom:1px solid #f1f5f9;">
                {r['detail']}
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">

  <!-- ── Header ── -->
  <div style="background:linear-gradient(135deg,#1a3c6e,#2563eb);
      padding:36px 40px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:26px;
        letter-spacing:1px;">
      {status_emoji} BOP API Health Report
    </h1>
    <p style="color:#93c5fd;margin:10px 0 0;font-size:14px;">{now}</p>
  </div>

  <div style="padding:28px 32px;">

    <!-- ── KPI Cards ── -->
    <div style="display:flex;gap:16px;margin-bottom:20px;">

      <div style="flex:1;background:#ffffff;border-radius:12px;
          padding:20px 22px;border-top:4px solid #2563eb;
          box-shadow:0 2px 8px rgba(0,0,0,0.07);">
        <p style="margin:0;font-size:11px;color:#6b7280;
            text-transform:uppercase;letter-spacing:1px;">Total APIs</p>
        <p style="margin:8px 0 0;font-size:36px;font-weight:700;
            color:#1e293b;">{total}</p>
      </div>

      <div style="flex:1;background:#ffffff;border-radius:12px;
          padding:20px 22px;border-top:4px solid #16a34a;
          box-shadow:0 2px 8px rgba(0,0,0,0.07);">
        <p style="margin:0;font-size:11px;color:#6b7280;
            text-transform:uppercase;letter-spacing:1px;">Healthy</p>
        <p style="margin:8px 0 0;font-size:36px;font-weight:700;
            color:#16a34a;">{healthy}</p>
      </div>

      <div style="flex:1;background:#ffffff;border-radius:12px;
          padding:20px 22px;border-top:4px solid #dc2626;
          box-shadow:0 2px 8px rgba(0,0,0,0.07);">
        <p style="margin:0;font-size:11px;color:#6b7280;
            text-transform:uppercase;letter-spacing:1px;">Failed</p>
        <p style="margin:8px 0 0;font-size:36px;font-weight:700;
            color:#dc2626;">{failed}</p>
      </div>

      <div style="flex:1;background:#ffffff;border-radius:12px;
          padding:20px 22px;border-top:4px solid {pct_color};
          box-shadow:0 2px 8px rgba(0,0,0,0.07);">
        <p style="margin:0;font-size:11px;color:#6b7280;
            text-transform:uppercase;letter-spacing:1px;">Health Score</p>
        <p style="margin:8px 0 0;font-size:36px;font-weight:700;
            color:{pct_color};">{pct}%</p>
      </div>

    </div>

    <!-- ── Progress Bar ── -->
    <div style="background:#ffffff;border-radius:12px;padding:20px 22px;
        box-shadow:0 2px 8px rgba(0,0,0,0.07);margin-bottom:20px;">
      <p style="margin:0 0 10px;font-size:11px;color:#6b7280;font-weight:600;
          text-transform:uppercase;letter-spacing:1px;">Overall Health</p>
      <div style="background:#f1f5f9;border-radius:999px;
          height:14px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{pct_color};
            border-radius:999px;"></div>
      </div>
      <p style="margin:8px 0 0;font-size:12px;color:#6b7280;">
        {healthy} of {total} APIs are healthy
      </p>
    </div>

    <!-- ── Results Table ── -->
    <div style="background:#ffffff;border-radius:12px;padding:22px;
        box-shadow:0 2px 8px rgba(0,0,0,0.07);">
      <p style="margin:0 0 16px;font-size:11px;color:#6b7280;font-weight:600;
          text-transform:uppercase;letter-spacing:1px;">API Status Details</p>
      <table style="width:100%;border-collapse:collapse;">
        <tr style="background:#f8fafc;">
          <th style="text-align:left;padding:10px 16px;font-size:11px;
              color:#6b7280;font-weight:600;border-bottom:2px solid #e2e8f0;
              text-transform:uppercase;">API Name</th>
          <th style="text-align:center;padding:10px 16px;font-size:11px;
              color:#6b7280;font-weight:600;border-bottom:2px solid #e2e8f0;
              text-transform:uppercase;">Status</th>
          <th style="text-align:left;padding:10px 16px;font-size:11px;
              color:#6b7280;font-weight:600;border-bottom:2px solid #e2e8f0;
              text-transform:uppercase;">Details</th>
        </tr>
        {rows}
      </table>
    </div>

  </div>

  <!-- ── Footer ── -->
  <div style="text-align:center;padding:20px;color:#9ca3af;font-size:11px;">
    BOP API Health Monitor &nbsp;•&nbsp;
    Auto-generated report &nbsp;•&nbsp;
    {now}
  </div>

</body>
</html>"""

    return html, total, healthy, failed


# ============================================================
# SEND EMAIL VIA OUTLOOK SMTP
# ============================================================
def send_email(html_body, failed_count):
    email_from = os.environ["EMAIL_FROM"]
    email_to   = os.environ["EMAIL_TO"]
    password   = os.environ["EMAIL_PASS"]

    status_str = (
        "✅ All APIs Healthy"
        if failed_count == 0
        else f"❌ {failed_count} API(s) Failed"
    )

    msg = MIMEMultipart("alternative")
    msg["From"]    = email_from
    msg["To"]      = email_to
    msg["Subject"] = (
        f"BOP API Health Report — "
        f"{datetime.now().strftime('%d %b %Y')} — "
        f"{status_str}"
    )
    msg.attach(MIMEText(html_body, "html"))

#   with smtplib.SMTP("smtp.office365.com", 587) as server:
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(email_from, password)
        server.send_message(msg)
        print("\n✅ Email sent successfully!")


# ============================================================
# MAIN — runs everything
# ============================================================
if __name__ == "__main__":
    now = datetime.now().strftime("%d %b %Y %I:%M %p")

    print("=" * 50)
    print(f"BOP API Health Check — {now}")
    print(f"Total APIs to check: {len(APIS)}")
    print("=" * 50)

    # Run all checks
    results = run_all_checks(APIS)

    # Build report
    html, total, healthy, failed = build_html_report(results, now)

    # Print summary
    print("\n" + "=" * 50)
    print(f"SUMMARY: Total={total} Healthy={healthy} Failed={failed}")
    print("=" * 50)

    # Send email
    send_email(html, failed)
