from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

    # One-to-many: User → Jobs
    jobs = db.relationship('Job', backref='user', lazy=True)

class Job(db.Model):
    __tablename__ = 'job'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(120), nullable=False)
    link = db.Column(db.String(250), nullable=False)
    resume_filename = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), default="Under Consideration")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Foreign key to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Optional fields
    notes = db.Column(db.Text)
    deadline = db.Column(db.Date)
