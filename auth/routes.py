from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models.models import db, User
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('jobs.dashboard'))
        flash("Invalid credentials", "danger")
    return render_template('auth/login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "warning")
        else:
            hashed = generate_password_hash(password)
            user = User(email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('jobs.dashboard'))
    return render_template('auth/signup.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/settings/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')

        if not check_password_hash(current_user.password, current):
            flash("Current password is incorrect", "danger")
        elif new != confirm:
            flash("New passwords do not match", "warning")
        else:
            try:
                current_user.password = generate_password_hash(new)
                db.session.commit()
                flash("Password updated successfully", "success")
                return redirect(url_for('jobs.dashboard'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating password: {e}")
                flash("An unexpected error occurred. Please try again.", "danger")

    return render_template('auth/change_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('auth.reset_token', token=token, _external=True)
            print(f"[Reset Link] {reset_link}")
            flash('Password reset link sent! Check your console.', 'info')
        else:
            flash('Email not found', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.reset_request'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Password updated! Please login.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_token.html')
