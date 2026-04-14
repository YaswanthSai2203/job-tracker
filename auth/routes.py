import json
import logging
import os

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from urllib.parse import urljoin, urlparse
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import limiter
from models.models import Job, User, db
from utils.mail import send_email
from utils.passwords import password_errors

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


def _safe_redirect_target(target: str | None) -> str | None:
    if not target or not isinstance(target, str):
        return None
    target = target.strip()
    if not target:
        return None
    base = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    if test.scheme not in ("http", "https"):
        return None
    if base.netloc != test.netloc:
        return None
    return target


def _user_by_email(email: str):
    """Case-insensitive match (handles legacy rows stored with mixed case)."""
    if not email:
        return None
    norm = email.strip().lower()
    return User.query.filter(func.lower(User.email) == norm).first()


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if request.method == "GET":
        nxt = _safe_redirect_target(request.args.get("next"))
        if current_user.is_authenticated:
            if not getattr(current_user, "email_verified", True):
                return redirect(
                    url_for("auth.verification_required", email=current_user.email)
                )
            if nxt:
                return redirect(nxt)
            return redirect(url_for("jobs.dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email:
            flash("Enter your email address.", "warning")
            return render_template("auth/login.html")
        user = _user_by_email(email)
        if user and user.password and check_password_hash(user.password, password):
            if not getattr(user, "email_verified", True):
                flash("Please verify your email before logging in.", "warning")
                return redirect(
                    url_for("auth.verification_required", email=user.email)
                )
            if user.email != email:
                user.email = email
                db.session.commit()
            login_user(user)
            nxt = _safe_redirect_target(
                request.form.get("next") or request.args.get("next")
            )
            if nxt:
                return redirect(nxt)
            return redirect(url_for("jobs.dashboard"))
        flash("Invalid email or password.", "danger")
    next_url = _safe_redirect_target(
        request.args.get("next") or request.form.get("next")
    )
    return render_template("auth/login.html", next_url=next_url)


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def signup():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or "@" not in email:
            flash("Enter a valid email address.", "warning")
            return render_template("auth/signup.html")
        errs = password_errors(password)
        if errs:
            for e in errs:
                flash(e, "warning")
        elif _user_by_email(email):
            flash("That email is already registered.", "warning")
        else:
            mail_ok = bool(current_app.config.get("MAIL_SERVER"))
            user = User(
                email=email,
                password=generate_password_hash(password),
                email_verified=not mail_ok,
            )
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("That email is already registered.", "warning")
                return render_template("auth/signup.html")

            if mail_ok:
                s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
                token = s.dumps(email, salt="email-verify-salt")
                link = url_for("auth.verify_email", token=token, _external=True)
                body = (
                    "Welcome to Job Tracker.\n\n"
                    "Please verify your email by opening this link (valid for 3 days):\n"
                    f"{link}\n\n"
                    "If you did not create an account, you can ignore this message."
                )
                if send_email(
                    current_app,
                    subject="Verify your email — Job Tracker",
                    body_text=body,
                    to_addr=email,
                ):
                    flash(
                        "We sent a verification link to your email. Open it to activate your account.",
                        "success",
                    )
                else:
                    user.email_verified = True
                    db.session.commit()
                    flash(
                        "We could not send the verification email (SMTP error). "
                        "Your account is active — you can log in.",
                        "warning",
                    )
                    login_user(user)
                    return redirect(url_for("jobs.dashboard"))
                return redirect(url_for("auth.verification_required", email=email))

            login_user(user)
            return redirect(url_for("jobs.dashboard"))
    return render_template("auth/signup.html")


def _send_verification_email(user_email: str) -> bool:
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    token = s.dumps(user_email.strip().lower(), salt="email-verify-salt")
    link = url_for("auth.verify_email", token=token, _external=True)
    body = (
        "Welcome to Job Tracker.\n\n"
        "Please verify your email by opening this link (valid for 3 days):\n"
        f"{link}\n\n"
        "If you did not create an account, you can ignore this message."
    )
    return send_email(
        current_app,
        subject="Verify your email — Job Tracker",
        body_text=body,
        to_addr=user_email,
    )


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="email-verify-salt", max_age=86400 * 3)
    except (SignatureExpired, BadSignature):
        flash("That verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    user = _user_by_email(email)
    if not user:
        flash("No account found for that link.", "danger")
        return redirect(url_for("auth.signup"))

    user.email_verified = True
    db.session.commit()
    flash("Your email is verified. You can log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/verification-required")
def verification_required():
    email = (request.args.get("email") or "").strip()
    return render_template("auth/pending_verification.html", email=email)


@auth_bp.route("/resend-verification", methods=["POST"])
@limiter.limit("5 per hour")
def resend_verification():
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Enter your email address.", "warning")
        return redirect(url_for("auth.login"))

    if not current_app.config.get("MAIL_SERVER"):
        flash("Email is not configured on this server.", "danger")
        return redirect(url_for("auth.login"))

    user = _user_by_email(email)
    if not user:
        flash("If an account exists, a verification email will be sent.", "info")
        return redirect(url_for("auth.login"))

    if user.email_verified:
        flash("That account is already verified. You can log in.", "info")
        return redirect(url_for("auth.login"))

    if _send_verification_email(user.email):
        flash("Verification email sent. Check your inbox.", "success")
    else:
        flash("Could not send email. Try again later.", "danger")
    return redirect(url_for("auth.verification_required", email=user.email))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/account")
@login_required
def account():
    return render_template("auth/account.html")


@auth_bp.route("/account/export")
@login_required
def export_data():
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.timestamp.desc()).all()
    payload = {
        "export_version": 1,
        "email": current_user.email,
        "applications": [
            {
                "company": j.company,
                "link": j.link,
                "resume_filename": j.resume_filename,
                "status": j.status,
                "tags": getattr(j, "tags", "") or "",
                "notes": j.notes,
                "deadline": j.deadline.isoformat() if j.deadline else None,
                "created_at": j.timestamp.isoformat() + "Z",
                "updated_at": (
                    getattr(j, "updated_at", j.timestamp).isoformat() + "Z"
                ),
            }
            for j in jobs
        ],
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    return Response(
        body,
        mimetype="application/json",
        headers={
            "Content-Disposition": "attachment; filename=job_tracker_data.json"
        },
    )


@auth_bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    confirm = (request.form.get("confirm_email") or "").strip().lower()
    if confirm != current_user.email.strip().lower():
        flash("Email confirmation did not match. Nothing was deleted.", "danger")
        return redirect(url_for("auth.account"))

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    uid = current_user.id
    user = db.session.get(User, uid)
    if not user:
        return redirect(url_for("auth.login"))
    for job in list(Job.query.filter_by(user_id=uid).all()):
        path = os.path.join(upload_folder, job.resume_filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                current_app.logger.warning("Could not remove %s", path)
        db.session.delete(job)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash("Your account and application data have been deleted.", "info")
    return redirect(url_for("home"))


@auth_bp.route("/settings/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password")
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not check_password_hash(current_user.password, current):
            flash("Current password is incorrect.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "warning")
        else:
            errs = password_errors(new)
            if errs:
                for e in errs:
                    flash(e, "warning")
            else:
                try:
                    current_user.password = generate_password_hash(new)
                    db.session.commit()
                    flash("Password updated successfully.", "success")
                    return redirect(url_for("jobs.dashboard"))
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error("Error updating password: %s", e)
                    flash("Something went wrong. Please try again.", "danger")

    return render_template("auth/change_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def reset_request():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = _user_by_email(email)
        neutral = (
            "If an account exists for that email, reset instructions have been sent "
            "or recorded for the site operator."
        )
        if user:
            s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
            token = s.dumps(email, salt="password-reset-salt")
            reset_link = url_for("auth.reset_token", token=token, _external=True)
            if current_app.config.get("MAIL_SERVER"):
                body = (
                    "You requested a password reset for Job Tracker.\n\n"
                    f"Use this link (valid for 1 hour):\n{reset_link}\n\n"
                    "If you did not request this, you can ignore this email."
                )
                ok = send_email(
                    current_app,
                    subject="Password reset",
                    body_text=body,
                    to_addr=email,
                )
                if ok:
                    flash("Check your email for a reset link.", "success")
                else:
                    logger.warning("Password reset email failed for %s", user.email)
                    flash(neutral, "info")
            else:
                logger.info("Password reset link for %s: %s", email, reset_link)
                flash(neutral, "info")
        else:
            flash(neutral, "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_token(token):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_request"))

    if request.method == "POST":
        new_password = request.form.get("password") or ""
        errs = password_errors(new_password)
        if errs:
            for e in errs:
                flash(e, "warning")
        else:
            user = _user_by_email(email)
            if user:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                flash("Password updated. You can log in now.", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/reset_token.html")
