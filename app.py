from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models.models import db, User
from auth.routes import auth_bp
from jobs.routes import jobs_bp
import os

app = Flask(__name__)
app.config.from_object(Config)

if app.config.get("VERCEL"):
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize extensions
db.init_app(app)
with app.app_context():
    db.create_all()
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(jobs_bp)

# User loader
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('jobs.dashboard'))
    return render_template('landing.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5005)
