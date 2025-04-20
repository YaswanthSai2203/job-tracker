from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from config import Config
from models.models import db, User
from auth.routes import auth_bp
from jobs.routes import jobs_bp

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(jobs_bp)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Landing page or dashboard redirect
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('jobs.dashboard'))
    return render_template('landing.html')


# ✅ Auto-create tables on startup (important for Render Free tier without shell)
with app.app_context():
    try:
        db.create_all()
        print("✅ Tables created successfully.")
    except Exception as e:
        print("❌ Error creating tables:", e)

if __name__ == '__main__':
    app.run(debug=True, port=5005)
