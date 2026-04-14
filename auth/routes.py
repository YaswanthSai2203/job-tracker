import json
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
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from models.models import Job, User, db

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("jobs.dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
        else:
            hashed = generate_password_hash(password)
            user = User(email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("jobs.dashboard"))
    return render_template("auth/signup.html")


@auth_bp.route("/logout")
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
        new = request.form.get("new_password")
        confirm = request.form.get("confirm_password")

        if not check_password_hash(current_user.password, current):
            flash("Current password is incorrect", "danger")
        elif new != confirm:
            flash("New passwords do not match", "warning")
        else:
            try:
                current_user.password = generate_password_hash(new)
                db.session.commit()
                flash("Password updated successfully", "success")
                return redirect(url_for("jobs.dashboard"))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error("Error updating password: %s", e)
                flash("An unexpected error occurred. Please try again.", "danger")

    return render_template("auth/change_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
            token = s.dumps(email, salt="password-reset-salt")
            reset_link = url_for("auth.reset_token", token=token, _external=True)
            print(f"[Reset Link] {reset_link}")
            flash("Password reset link sent! Check your console.", "info")
        else:
            flash("Email not found", "danger")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_token(token):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("The reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_request"))

    if request.method == "POST":
        new_password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash("Password updated! Please login.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_token.html")
