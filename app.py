import os

from flask import Flask, jsonify, redirect, render_template, url_for
from flask_login import LoginManager, current_user

from auth.routes import auth_bp
from config import Config
from jobs.routes import jobs_bp
from models.models import User, db
from utils.logging_setup import init_app_logging
from utils.schema import ensure_schema

app = Flask(__name__)
app.config.from_object(Config)

init_app_logging(app)

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

db.init_app(app)
with app.app_context():
    db.create_all()
    ensure_schema()

login_manager = LoginManager(app)
login_manager.login_view = "auth.login"

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(jobs_bp)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("jobs.dashboard"))
    return render_template("landing.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_schema()
    app.run(debug=True, port=5005)
