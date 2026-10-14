"""
app.py — BIT Birthday Wishes · Flask backend
Single-admin, SQLite, Playwright screenshots, Gmail SMTP, APScheduler
Deploy on Render.com with persistent disk at /data
"""
import os, threading, secrets
from io import BytesIO
from pathlib import Path
from datetime import date
from flask import (Flask, request, jsonify, render_template,
                   session, send_file)
from werkzeug.utils import secure_filename

from helpers import (
    init_db, cfg_get, cfg_set, cfg_set_many, get_all_config,
    is_setup_done, create_admin, check_login, get_admin_username,
    import_csv_file, get_all_students, delete_student,
    get_todays_birthdays, get_birthdays_on, get_month_birthday_map,
    get_template, save_template, get_recent_logs,
    logger, UPLOAD_DIR, OUTPUT_DIR, DATA_DIR
)
from scheduler import start_scheduler, update_schedule, get_next_run
from send import send_all
from pdf_report import generate_birthday_report

# ── Flask setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024   # 200 MB

# SECRET_KEY — persist to disk so sessions survive restarts
_SK_PATH = DATA_DIR / "secret.key"
if _SK_PATH.exists():
    app.secret_key = _SK_PATH.read_text().strip()
else:
    _sk = secrets.token_hex(32)
    _SK_PATH.write_text(_sk)
    app.secret_key = _sk

# ── Initialise DB immediately on import ───────────────────────────────────────
init_db()
start_scheduler()

# ── In-memory send job state ───────────────────────────────────────────────────
_job = {"running": False, "progress": 0, "total": 0, "results": [], "error": ""}


def _reset_job(total=0):
    global _job
    _job = {"running": True, "progress": 0,
            "total": total, "results": [], "error": ""}


def _finish_job(error=""):
    _job["running"] = False
    if error:
        _job["error"] = error


# ── Auth helpers ───────────────────────────────────────────────────────────────
def logged_in() -> bool:
    return session.get("auth") is True


def require_login(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if not logged_in():
            return jsonify({"error": "Not authenticated."}), 401
        return fn(*a, **kw)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    """
    Called by frontend on every page load.
    setup_needed is always False — credentials are hardcoded.
    """
    return jsonify({
        "ok":           True,
        "setup_needed": False,
        "logged_in":    logged_in(),
        "username":     get_admin_username() if logged_in() else "",
    })


@app.route("/api/setup", methods=["POST"])
def api_setup():
    # Setup is disabled — credentials are hardcoded
    return jsonify({"error": "Setup is disabled."}), 400


@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(silent=True) or {}
    username = (d.get("username") or "").strip()
    password = d.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    if check_login(username, password):
        session.permanent = True
        session["auth"]   = True
        logger.info("Admin logged in: %s", username)
        return jsonify({"message": "Logged in.", "username": username})

    logger.warning("Failed login attempt for: %s", username)
    return jsonify({"error": "Incorrect username or password."}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out."})


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/dashboard", methods=["GET"])
@require_login
def api_dashboard():
    matches  = get_todays_birthdays()
    students = get_all_students()
    today    = date.today()
    return jsonify({
        "date":           today.strftime("%A, %d %B %Y"),
        "count":          len(matches),
        "matches":        matches,
        "total_students": len(students),
        "skipped":        0,
    })


# ══════════════════════════════════════════════════════════════════════════════
# STUDENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/students", methods=["GET"])
@require_login
def api_students():
    return jsonify({"students": get_all_students()})


@app.route("/api/students/<int:sid>", methods=["DELETE"])
@require_login
def api_delete_student(sid):
    delete_student(sid)
    logger.info("Deleted student id=%d", sid)
    return jsonify({"message": "Student removed."})


# ══════════════════════════════════════════════════════════════════════════════
# CSV
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/csv/upload", methods=["POST"])
@require_login
def api_csv_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted."}), 400

    dest = UPLOAD_DIR / secure_filename(f.filename)
    f.save(str(dest))
    try:
        result = import_csv_file(str(dest))
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        logger.error("CSV import error: %s", e)
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════════════
# CALENDAR
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/calendar/<int:month>", methods=["GET"])
@require_login
def api_calendar_month(month):
    if not 1 <= month <= 12:
        return jsonify({"error": "Invalid month."}), 400
    return jsonify(get_month_birthday_map(month))


@app.route("/api/calendar/pdf/<int:day>/<int:month>", methods=["GET"])
@require_login
def api_calendar_pdf(day, month):
    import calendar as cal_mod
    students = get_birthdays_on(day, month)
    try:
        qdate = date(date.today().year, month, day)
    except ValueError:
        qdate = None
    pdf_bytes = generate_birthday_report(
        students,
        query_date=qdate,
        title=f"Birthday Report — {day:02d} {cal_mod.month_name[month]}",
    )
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"BIT_Birthdays_{day:02d}_{month:02d}.pdf",
    )


@app.route("/api/report/today/pdf", methods=["GET"])
@require_login
def api_today_pdf():
    today     = date.today()
    students  = get_todays_birthdays()
    pdf_bytes = generate_birthday_report(
        students,
        query_date=today,
        title=f"Today's Birthday Report — {today.strftime('%d %B %Y')}",
    )
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"BIT_Birthdays_Today_{today.isoformat()}.pdf",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SEND
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/send", methods=["POST"])
@require_login
def api_send():
    global _job
    if _job["running"]:
        return jsonify({"error": "A send job is already in progress."}), 409

    matches = get_todays_birthdays()
    if not matches:
        return jsonify({"message": "No birthdays today — nothing to send.", "total": 0})

    _reset_job(total=len(matches))

    def _cb(i, total, r):
        _job["progress"] = i
        _job["results"].append(r)

    def _run():
        try:
            send_all(matches, progress_cb=_cb)
        except Exception as e:
            logger.error("Send job error: %s", e)
            _finish_job(error=str(e))
        finally:
            _finish_job()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({
        "message": f"Sending to {len(matches)} student(s)…",
        "total":   len(matches),
    })


@app.route("/api/send/status", methods=["GET"])
@require_login
def api_send_status():
    return jsonify(_job)


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/template", methods=["GET"])
@require_login
def api_get_template():
    return jsonify({"html": get_template()})


@app.route("/api/template", methods=["POST"])
@require_login
def api_save_template():
    d    = request.get_json(silent=True) or {}
    html = d.get("html", "").strip()
    if not html:
        return jsonify({"error": "Template cannot be empty."}), 400
    save_template(html)
    return jsonify({"message": "Template saved."})


@app.route("/api/template/upload", methods=["POST"])
@require_login
def api_upload_template():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400
    f    = request.files["file"]
    html = f.read().decode("utf-8", errors="replace").strip()
    if not html:
        return jsonify({"error": "Template file is empty."}), 400
    save_template(html)
    logger.info("Template uploaded from file")
    return jsonify({"message": "Template uploaded and saved."})


@app.route("/api/template/preview/<int:sid>", methods=["GET"])
@require_login
def api_preview(sid):
    students = get_all_students()
    student  = next((s for s in students if s["id"] == sid), None)
    if not student:
        return jsonify({"error": "Student not found."}), 404
    tpl = get_template()
    if not tpl:
        return jsonify({"error": "No template uploaded yet."}), 404
    return jsonify({"html": tpl.replace("{{name}}", student["name"])})


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/settings", methods=["GET"])
@require_login
def api_get_settings():
    cfg  = get_all_config()
    safe = {k: v for k, v in cfg.items()
            if k not in ("app_password", "admin_pass_hash")}
    safe["password_set"] = bool(cfg.get("app_password"))
    safe["next_run"]     = get_next_run()
    return jsonify(safe)


@app.route("/api/settings", methods=["POST"])
@require_login
def api_save_settings():
    d       = request.get_json(silent=True) or {}
    allowed = {"smtp_server", "smtp_port", "sender_email", "app_password",
               "send_time", "timezone", "auto_send"}
    updates = {k: v for k, v in d.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update."}), 400

    cfg_set_many(updates)

    if any(k in updates for k in ("send_time", "auto_send", "timezone")):
        update_schedule(
            send_time=updates.get("send_time"),
            auto_send=updates.get("auto_send") in (True, "true", "True"),
            timezone=updates.get("timezone"),
        )

    logger.info("Settings updated: %s",
                [k for k in updates if k != "app_password"])
    return jsonify({"message": "Settings saved.", "next_run": get_next_run()})


# ══════════════════════════════════════════════════════════════════════════════
# LOGS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/logs", methods=["GET"])
@require_login
def api_logs():
    n = int(request.args.get("n", 100))
    return jsonify({"logs": get_recent_logs(n)})


# ══════════════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("BIT Birthday Wishes starting on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
