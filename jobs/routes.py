import os
import re
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, send_file, abort, current_app, flash
from flask_login import login_required, current_user
from models.models import db, Job, PublicJob
from datetime import datetime
from math import ceil

jobs_bp = Blueprint('jobs', __name__, template_folder='../templates/jobs')

def sanitize_filename(name):
    return re.sub(r'\W+', '', name.lower().replace(' ', '_'))

def ensure_upload_folder():
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder

@jobs_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    ensure_upload_folder()

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
                upload_folder = ensure_upload_folder()
                filepath = os.path.join(upload_folder, filename)
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
    ensure_upload_folder()

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
    ensure_upload_folder()

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

@jobs_bp.route('/jobs-board')
def jobs_board():
    jobs = PublicJob.query.order_by(PublicJob.timestamp.desc()).all()
    return render_template('jobs/jobs_board.html', jobs=jobs)

@jobs_bp.route('/admin/jobs', methods=['GET', 'POST'])
@login_required
def admin_jobs():
    admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
    if current_user.email != admin_email:
        abort(403)

    if request.method == 'POST':
        job = PublicJob(
            title=request.form['title'],
            company=request.form['company'],
            location=request.form['location'],
            salary=request.form['salary'],
            link=request.form['link'],
            description=request.form['description']
        )
        db.session.add(job)
        db.session.commit()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('jobs.admin_jobs'))

    jobs = PublicJob.query.order_by(PublicJob.timestamp.desc()).all()
    return render_template('jobs/admin_jobs.html', jobs=jobs)

@jobs_bp.route('/admin/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_public_job(job_id):
    admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
    if current_user.email != admin_email:
        abort(403)

    job = PublicJob.query.get_or_404(job_id)

    if request.method == 'POST':
        job.title = request.form['title']
        job.company = request.form['company']
        job.location = request.form['location']
        job.salary = request.form['salary']
        job.link = request.form['link']
        job.description = request.form['description']
        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('jobs.admin_jobs'))

    return render_template('jobs/edit_job.html', job=job)

@jobs_bp.route('/admin/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_public_job(job_id):
    admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@example.com')
    if current_user.email != admin_email:
        abort(403)

    job = PublicJob.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Job deleted successfully.', 'success')
    return redirect(url_for('jobs.admin_jobs'))
