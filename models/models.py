from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

    # Relationship: One user can have many job applications
    jobs = db.relationship('Job', backref='user', lazy=True)

class Job(db.Model):
    __tablename__ = 'job'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(120), nullable=False)
    link = db.Column(db.String(250), nullable=False)
    resume_filename = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(50), default="Under Consideration")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    notes = db.Column(db.Text)
    deadline = db.Column(db.Date)

class PublicJob(db.Model):
    __tablename__ = 'public_job'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    salary = db.Column(db.String(100), nullable=True)
    link = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
