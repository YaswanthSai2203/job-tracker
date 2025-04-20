import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, send_file, abort, current_app
from flask_login import login_required, current_user
from models.models import db, Job
from datetime import datetime
from math import ceil
import pandas as pd

jobs_bp = Blueprint('jobs', __name__, template_folder='../templates/jobs')

def sanitize_filename(name):
    return re.sub(r'\W+', '', name.lower().replace(' ', '_'))

@jobs_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        if request.form.get('update_status'):
            job_id = request.form.get('job_id')
            new_status = request.form.get('status')
            job = Job.query.get(job_id)
            if job and job.user_id == current_user.id:
                job.status = new_status
                db.session.commit()
        else:
            company = request.form.get('company')
            link = request.form.get('link')
            resume = request.files.get('resume')
            notes = request.form.get('notes')
            deadline_str = request.form.get('deadline')
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

            if company and link and resume:
                filename = f"{sanitize_filename(company)}_resume{os.path.splitext(resume.filename)[1]}"
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

                # Save file
                resume.save(filepath)

                job = Job(
                    company=company,
                    link=link,
                    resume_filename=filename,
                    user_id=current_user.id,
                    notes=notes,
                    deadline=deadline
                )
                db.session.add(job)
                db.session.commit()

        return redirect(url_for('jobs.dashboard'))

    search = request.args.get('search', '').lower()
    status_filter = request.args.get('status', '')
    page = int(request.args.get('page', 1))
    per_page = 5

    query = Job.query.filter_by(user_id=current_user.id)
    if search:
        query = query.filter(Job.company.ilike(f'%{search}%'))
    if status_filter:
        query = query.filter_by(status=status_filter)

    query = query.order_by(Job.timestamp.desc())
    total_jobs = query.count()
    jobs = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = ceil(total_jobs / per_page)

    return render_template('jobs/dashboard.html',
                           jobs=jobs,
                           search=search,
                           status_filter=status_filter,
                           page=page,
                           total_pages=total_pages)

@jobs_bp.route('/resume/<filename>')
@login_required
def download_resume(filename):
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    abort(404)

@jobs_bp.route('/preview_resume/<filename>')
@login_required
def preview_resume(filename):
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path)
    abort(404)

@jobs_bp.route('/export/<int:job_id>')
@login_required
def export_single(job_id):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    data = [{
        'Company': job.company,
        'Link': job.link,
        'Resume': job.resume_filename,
        'Status': job.status,
        'Timestamp': job.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'Notes': job.notes,
        'Deadline': job.deadline.strftime('%Y-%m-%d') if job.deadline else ''
    }]
    df = pd.DataFrame(data)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], f'job_{job.id}.xlsx')
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

@jobs_bp.route('/download_excel')
@login_required
def download_excel():
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.timestamp.desc()).all()
    data = [{
        'Company': j.company,
        'Link': j.link,
        'Resume': j.resume_filename,
        'Status': j.status,
        'Timestamp': j.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'Notes': j.notes,
        'Deadline': j.deadline.strftime('%Y-%m-%d') if j.deadline else ''
    } for j in jobs]

    df = pd.DataFrame(data)
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'job_applications.xlsx')
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)
