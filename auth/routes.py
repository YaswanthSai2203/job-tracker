import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required, login_user, logout_user, current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import limiter
from models.models import User, db
from utils.mail import send_email
from utils.passwords import password_errors

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email:
            flash("Enter your email address.", "warning")
            return render_template("auth/login.html")
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("jobs.dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html")


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
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "warning")
        else:
            user = User(email=email, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("jobs.dashboard"))
    return render_template("auth/signup.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


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
        user = User.query.filter_by(email=email).first()
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
                    to_addr=user.email,
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
            user = User.query.filter_by(email=email).first()
            if user:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                flash("Password updated. You can log in now.", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/reset_token.html")
