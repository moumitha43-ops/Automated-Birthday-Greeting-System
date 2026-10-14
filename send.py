"""
send.py — Render birthday card via Playwright, send via Gmail SMTP
"""
import smtplib, time, base64
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from helpers import (
    cfg_get, get_template, already_sent_today,
    log_sent, logger, OUTPUT_DIR
)


# ── Card rendering ─────────────────────────────────────────────────────────────
def render_card(name: str, student_id: int) -> Path:
    """Render HTML template for name → screenshot PNG. Returns path."""
    from playwright.sync_api import sync_playwright, Error as PWError

    tpl = get_template()
    if not tpl:
        raise RuntimeError("No card template uploaded yet. Go to Card Template and upload one.")

    html     = tpl.replace("{{name}}", name)
    html_path = OUTPUT_DIR / f"card_{student_id}.html"
    img_path  = OUTPUT_DIR / f"card_{student_id}.png"
    html_path.write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 677, "height": 452},
                device_scale_factor=2,
            )
            page = ctx.new_page()
            page.goto(html_path.absolute().as_uri(), wait_until="networkidle")
            page.wait_for_timeout(600)
            page.screenshot(
                path=str(img_path),
                full_page=False,
                clip={"x": 0, "y": 0, "width": 677, "height": 452},
            )
            browser.close()
    except PWError as e:
        raise RuntimeError(f"Playwright error for '{name}': {e}")

    return img_path


# ── Email build ────────────────────────────────────────────────────────────────
def build_email(sender: str, name: str, to_email: str,
                img_path: Path) -> EmailMessage:
    """
    Send the birthday card as a pure inline PNG image embedded via CID.
    No dynamic HTML layout — the image renders identically on every email client.
    """
    cid = make_msgid(domain="bit.edu")   # stable domain keeps CID consistent

    with open(img_path, "rb") as f:
        img_data = f.read()

    msg = EmailMessage()
    msg["From"]    = sender
    msg["To"]      = to_email
    msg["Subject"] = f"Happy Birthday {name}! \U0001f382"

    # Plain-text fallback (shown if images disabled)
    msg.set_content(
        f"Happy Birthday {name}!\n\n"
        "Warm wishes from Bannari Amman Institute of Technology, Sathyamangalam.\n\n"
        "-- S V Balasubramaniam, Chairman, BIT"
    )

    # HTML part — single centred <img> pointing at CID.
    # No table tricks, no external CSS — maximum compatibility across Gmail,
    # Outlook, Apple Mail, mobile clients.
    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#ffffff;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:#ffffff;">
    <tr>
      <td align="center" style="padding:20px 0;">
        <!--
          Fixed dimensions — card must NOT stretch beyond 677x452.
          No max-width:100%, no fluid width — let it sit at natural size.
          Email clients that are narrower will scroll horizontally,
          which is correct behaviour for a fixed-size card.
        -->
        <img src="cid:{cid[1:-1]}"
             alt="Happy Birthday {name} — Bannari Amman Institute of Technology"
             width="677"
             height="452"
             style="display:block;
                    width:677px;
                    height:452px;
                    border:0;
                    outline:none;
                    text-decoration:none;">
      </td>
    </tr>
  </table>
</body>
</html>"""

    msg.add_alternative(html_body, subtype="html")

    # Attach the PNG inline (related to the HTML part)
    msg.get_payload()[1].add_related(
        img_data,
        maintype="image",
        subtype="png",
        cid=cid,
        filename="BirthdayCard.png",
        disposition="inline",
    )
    return msg


# ── Send one student ───────────────────────────────────────────────────────────
def send_one(student: dict, skip_dup_check: bool = False) -> dict:
    sid   = student["id"]
    name  = student["name"]
    email = student["email"]

    if not skip_dup_check and already_sent_today(sid):
        log_sent(sid, name, email, "skipped")
        logger.info("[SKIP] %s <%s> — already sent today", name, email)
        return {"name": name, "email": email, "status": "skipped", "error": ""}

    smtp_server = cfg_get("smtp_server", "smtp.gmail.com")
    smtp_port   = int(cfg_get("smtp_port", "587"))
    sender      = cfg_get("sender_email", "")
    app_pw      = cfg_get("app_password", "")

    if not sender or not app_pw:
        err = "Sender email or app password not configured. Go to Settings."
        log_sent(sid, name, email, "failed", err)
        return {"name": name, "email": email, "status": "failed", "error": err}

    # Render card
    try:
        img_path = render_card(name, sid)
    except Exception as e:
        log_sent(sid, name, email, "failed", str(e))
        logger.error("[RENDER-FAIL] %s: %s", name, e)
        return {"name": name, "email": email, "status": "failed", "error": str(e)}

    msg = build_email(sender, name, email, img_path)

    # Send with retry
    last_err = ""
    for attempt in range(1, 4):
        try:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(sender, app_pw)
                s.send_message(msg)
            log_sent(sid, name, email, "sent")
            logger.info("[SENT] %s <%s> (attempt %d)", name, email, attempt)
            return {"name": name, "email": email, "status": "sent", "error": ""}
        except Exception as e:
            last_err = str(e)
            logger.warning("[RETRY %d/3] %s: %s", attempt, name, e)
            time.sleep(2 ** attempt)

    log_sent(sid, name, email, "failed", last_err)
    logger.error("[FAIL] %s <%s> after 3 attempts: %s", name, email, last_err)
    return {"name": name, "email": email, "status": "failed", "error": last_err}


# ── Send all ───────────────────────────────────────────────────────────────────
def send_all(students: list, progress_cb=None) -> dict:
    results = {"sent": [], "failed": [], "skipped": [], "total": len(students)}
    for i, s in enumerate(students, 1):
        r = send_one(s)
        results.setdefault(r["status"], []).append(r)
        if progress_cb:
            progress_cb(i, len(students), r)
    logger.info(
        "Run complete — %d sent, %d failed, %d skipped",
        len(results["sent"]), len(results["failed"]), len(results["skipped"])
    )
    return results
