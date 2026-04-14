import csv
import io
import os
import re
from datetime import date, datetime, timedelta
from math import ceil

import pandas as pd
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import limiter
from models.models import Job, PublicJob, db

jobs_bp = Blueprint("jobs", __name__, template_folder="../templates/jobs")

_ALLOWED_RESUME_EXT = {".pdf"}


def sanitize_filename(name):
    return re.sub(r"\W+", "", name.lower().replace(" ", "_"))


def ensure_upload_folder():
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder


def _resume_filename_ok(name):
    if not name or "/" in name or "\\" in name or ".." in name:
        return False
    ext = os.path.splitext(name)[1].lower()
    return ext in _ALLOWED_RESUME_EXT


def _job_for_resume_file(user_id, filename):
    if not _resume_filename_ok(filename):
        return None
    return Job.query.filter_by(user_id=user_id, resume_filename=filename).first()


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _dashboard_sort_clause(sort):
    if sort == "deadline":
        return (Job.deadline.isnot(None).desc(), Job.deadline.asc(), Job.timestamp.desc())
    if sort == "company":
        return (Job.company.asc(), Job.timestamp.desc())
    if sort == "updated":
        u = getattr(Job, "updated_at", None) or Job.timestamp
        return (u.desc(), Job.id.desc())
    if sort == "submitted":
        return (Job.timestamp.desc(), Job.id.desc())
    return (Job.timestamp.desc(), Job.id.desc())


def _per_page(raw):
    try:
        n = int(raw or 5)
    except ValueError:
        return 5
    if n not in (5, 10, 25, 50):
        return 5
    return n


@jobs_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@limiter.limit("200 per minute")
def dashboard():
    ensure_upload_folder()
    today = date.today()
    week_end = today + timedelta(days=(6 - today.weekday()))

    if request.method == "POST":
        if request.form.get("delete_job"):
            job_id = request.form.get("job_id")
            try:
                jid = int(job_id)
            except (TypeError, ValueError):
                jid = None
            job = db.session.get(Job, jid) if jid else None
            if job and job.user_id == current_user.id:
                path = os.path.join(current_app.config["UPLOAD_FOLDER"], job.resume_filename)
                db.session.delete(job)
                db.session.commit()
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        current_app.logger.warning("Could not remove resume file %s", path)
                flash("Application removed.", "success")
            else:
                flash("Could not delete that application.", "danger")
            return redirect(_dashboard_redirect_url())

        if request.form.get("duplicate_job"):
            job_id = request.form.get("job_id")
            try:
                jid = int(job_id)
            except (TypeError, ValueError):
                jid = None
            src = db.session.get(Job, jid) if jid else None
            if src and src.user_id == current_user.id:
                ext = os.path.splitext(src.resume_filename)[1] or ".pdf"
                if not _resume_filename_ok("x" + ext):
                    ext = ".pdf"
                base = sanitize_filename(src.company) + "_resume"
                fn = base + ext
                n = 1
                upload_folder = ensure_upload_folder()
                while os.path.exists(os.path.join(upload_folder, fn)) or Job.query.filter_by(
                    user_id=current_user.id, resume_filename=fn
                ).first():
                    n += 1
                    fn = f"{base}_{n}{ext}"
                old_path = os.path.join(upload_folder, src.resume_filename)
                new_path = os.path.join(upload_folder, fn)
                try:
                    with open(old_path, "rb") as inf, open(new_path, "wb") as outf:
                        outf.write(inf.read())
                except OSError:
                    flash("Could not copy resume file (original missing?).", "danger")
                    return redirect(_dashboard_redirect_url())
                now = datetime.utcnow()
                dup = Job(
                    company=src.company,
                    link=src.link,
                    resume_filename=fn,
                    user_id=current_user.id,
                    notes=(src.notes or "") + " — duplicate / applied again",
                    deadline=src.deadline,
                    status="Under Consideration",
                    timestamp=now,
                    updated_at=now,
                )
                db.session.add(dup)
                db.session.commit()
                flash("Duplicated application with a copy of the resume.", "success")
            return redirect(_dashboard_redirect_url())

        if request.form.get("update_status"):
            job_id = request.form.get("job_id")
            new_status = request.form.get("status")
            job = None
            if job_id:
                try:
                    job = db.session.get(Job, int(job_id))
                except (TypeError, ValueError):
                    pass
            if job and job.user_id == current_user.id:
                job.status = new_status
                job.updated_at = datetime.utcnow()
                db.session.commit()
        else:
            company = request.form.get("company")
            link = request.form.get("link")
            resume = request.files.get("resume")
            notes = request.form.get("notes")
            deadline = _parse_date(request.form.get("deadline"))

            if company and link and resume:
                ext = os.path.splitext(resume.filename or "")[1].lower()
                if ext not in _ALLOWED_RESUME_EXT:
                    flash("Please upload a PDF resume.", "warning")
                    return redirect(_dashboard_redirect_url())
                filename = f"{sanitize_filename(company)}_resume{ext}"
                upload_folder = ensure_upload_folder()
                filepath = os.path.join(upload_folder, filename)
                n = 1
                while os.path.exists(filepath) or Job.query.filter_by(
                    user_id=current_user.id, resume_filename=filename
                ).first():
                    n += 1
                    filename = f"{sanitize_filename(company)}_resume_{n}{ext}"
                    filepath = os.path.join(upload_folder, filename)
                resume.save(filepath)
                now = datetime.utcnow()
                job = Job(
                    company=company,
                    link=link,
                    resume_filename=filename,
                    user_id=current_user.id,
                    notes=notes,
                    deadline=deadline,
                    timestamp=now,
                    updated_at=now,
                )
                db.session.add(job)
                db.session.commit()

        return redirect(_dashboard_redirect_url())

    search = (request.args.get("search") or "").strip().lower()
    status_filter = (request.args.get("status") or "").strip()
    sort = (request.args.get("sort") or "updated").strip()
    per_page = _per_page(request.args.get("per_page"))
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    query = Job.query.filter_by(user_id=current_user.id)
    if search:
        query = query.filter(Job.company.ilike(f"%{search}%"))
    if status_filter:
        query = query.filter_by(status=status_filter)

    query = query.order_by(*_dashboard_sort_clause(sort))

    due_week_q = Job.query.filter(
        Job.user_id == current_user.id,
        Job.deadline.isnot(None),
        Job.deadline >= today,
        Job.deadline <= week_end,
    ).order_by(Job.deadline.asc())
    due_this_week = due_week_q.all()

    reminder_jobs = []
    for j in Job.query.filter_by(user_id=current_user.id).all():
        if not j.deadline:
            continue
        days = (j.deadline - today).days
        if 0 <= days <= 7 and j.status not in ("Rejected", "Offered"):
            reminder_jobs.append(j)

    if not session.get("reminders_shown"):
        session["reminders_shown"] = True
        show_reminder_banner = True
    else:
        show_reminder_banner = False

    total_jobs = query.count()
    total_pages = max(1, ceil(total_jobs / per_page)) if total_jobs else 1
    page = min(page, total_pages)
    jobs = query.offset((page - 1) * per_page).limit(per_page).all()

    return render_template(
        "jobs/dashboard.html",
        jobs=jobs,
        total_jobs=total_jobs,
        search=search,
        status_filter=status_filter,
        sort=sort,
        per_page=per_page,
        page=page,
        total_pages=total_pages,
        due_this_week=due_this_week,
        reminder_jobs=reminder_jobs,
        show_reminder_banner=show_reminder_banner,
        today=today,
        week_end=week_end,
    )


def _dashboard_redirect_url():
    src = request.form if request.method == "POST" else request.args

    def pick(*keys, default=""):
        for k in keys:
            v = src.get(k)
            if v not in (None, ""):
                return v
        return default

    return url_for(
        "jobs.dashboard",
        search=pick("return_search", "search", default=""),
        status=pick("return_status", "status", default=""),
        sort=pick("return_sort", "sort", default="updated"),
        per_page=pick("return_per_page", "per_page", default=5),
        page=pick("return_page", "page", default=1),
    )


@jobs_bp.route("/applications/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@limiter.limit("120 per minute")
def edit_application(job_id):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        company = request.form.get("company", "").strip()
        link = request.form.get("link", "").strip()
        notes = request.form.get("notes")
        deadline = _parse_date(request.form.get("deadline"))
        resume = request.files.get("resume")

        if not company or not link:
            flash("Company and job link are required.", "warning")
            return render_template("jobs/edit_application.html", job=job)

        job.company = company
        job.link = link
        job.notes = notes
        job.deadline = deadline
        job.updated_at = datetime.utcnow()

        if resume and resume.filename:
            ext = os.path.splitext(resume.filename)[1].lower()
            if ext not in _ALLOWED_RESUME_EXT:
                flash("Only PDF resumes are allowed.", "warning")
                return render_template("jobs/edit_application.html", job=job)
            upload_folder = ensure_upload_folder()
            old_name = job.resume_filename
            old_path = os.path.join(upload_folder, old_name)
            base = f"{sanitize_filename(company)}_resume"
            n = 0
            while True:
                filename = f"{base}{ext}" if n == 0 else f"{base}_{n}{ext}"
                filepath = os.path.join(upload_folder, filename)
                conflict_other = (
                    Job.query.filter_by(user_id=current_user.id, resume_filename=filename)
                    .filter(Job.id != job.id)
                    .first()
                )
                same_file = os.path.abspath(filepath) == os.path.abspath(old_path)
                if same_file or (not os.path.exists(filepath) and not conflict_other):
                    break
                n += 1
            resume.save(filepath)
            if os.path.isfile(old_path) and old_name != filename:
                try:
                    os.remove(old_path)
                except OSError:
                    pass
            job.resume_filename = filename

        db.session.commit()
        flash("Application updated.", "success")
        return redirect(url_for("jobs.dashboard"))

    return render_template("jobs/edit_application.html", job=job)


@jobs_bp.route("/resume/<path:filename>/download")
@login_required
@limiter.limit("300 per minute")
def download_resume(filename):
    if not _job_for_resume_file(current_user.id, filename):
        abort(404)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.isfile(path):
        return send_file(path, as_attachment=True)
    abort(404)


@jobs_bp.route("/resume/<path:filename>/preview")
@login_required
@limiter.limit("300 per minute")
def preview_resume(filename):
    if not _job_for_resume_file(current_user.id, filename):
        abort(404)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if os.path.isfile(path):
        return send_file(path)
    abort(404)


@jobs_bp.route("/resume/<path:filename>")
@login_required
@limiter.limit("300 per minute")
def download_resume_legacy(filename):
    """Backward compatibility for old /resume/<file> download links."""
    return redirect(url_for("jobs.download_resume", filename=filename))


@jobs_bp.route("/preview_resume/<path:filename>")
@login_required
@limiter.limit("300 per minute")
def preview_resume_legacy(filename):
    return redirect(url_for("jobs.preview_resume", filename=filename))


def _job_row_dict(job):
    return {
        "Company": job.company,
        "Link": job.link,
        "Resume": job.resume_filename,
        "Status": job.status,
        "Timestamp": job.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "Updated": getattr(job, "updated_at", job.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "Notes": job.notes or "",
        "Deadline": job.deadline.strftime("%Y-%m-%d") if job.deadline else "",
    }


@jobs_bp.route("/export/<int:job_id>")
@login_required
@limiter.limit("60 per minute")
def export_single(job_id):
    ensure_upload_folder()
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    if (request.args.get("format") or "").lower() == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(_job_row_dict(job).keys()))
        w.writeheader()
        w.writerow(_job_row_dict(job))
        mem = io.BytesIO(buf.getvalue().encode("utf-8"))
        mem.seek(0)
        return send_file(
            mem,
            as_attachment=True,
            download_name=f"job_{job.id}.csv",
            mimetype="text/csv",
        )
    data = [_job_row_dict(job)]
    df = pd.DataFrame(data)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"job_{job.id}.xlsx")
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)


@jobs_bp.route("/download_excel")
@login_required
@limiter.limit("30 per minute")
def download_excel():
    ensure_upload_folder()
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.timestamp.desc()).all()
    data = [_job_row_dict(j) for j in jobs]
    df = pd.DataFrame(data)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], "job_applications.xlsx")
    df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)


@jobs_bp.route("/download_csv")
@login_required
@limiter.limit("30 per minute")
def download_csv():
    jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.timestamp.desc()).all()
    if not jobs:
        rows = []
        fieldnames = [
            "Company",
            "Link",
            "Resume",
            "Status",
            "Timestamp",
            "Updated",
            "Notes",
            "Deadline",
        ]
    else:
        fieldnames = list(_job_row_dict(jobs[0]).keys())
        rows = [_job_row_dict(j) for j in jobs]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
    mem = io.BytesIO(buf.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name="job_applications.csv",
        mimetype="text/csv",
    )


@jobs_bp.route("/jobs-board")
@limiter.limit("120 per minute")
def jobs_board():
    q = (request.args.get("q") or "").strip()
    featured_only = request.args.get("featured") == "1"
    sort = (request.args.get("sort") or "newest").strip()

    query = PublicJob.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                PublicJob.title.ilike(like),
                PublicJob.company.ilike(like),
                PublicJob.description.ilike(like),
            )
        )
    if featured_only:
        query = query.filter(PublicJob.featured.is_(True))

    if sort == "oldest":
        query = query.order_by(PublicJob.timestamp.asc())
    elif sort == "company":
        query = query.order_by(PublicJob.company.asc(), PublicJob.timestamp.desc())
    else:
        query = query.order_by(PublicJob.featured.desc(), PublicJob.timestamp.desc())

    jobs = query.all()
    return render_template(
        "jobs/jobs_board.html",
        jobs=jobs,
        q=q,
        featured_only=featured_only,
        sort=sort,
    )


@jobs_bp.route("/admin/jobs", methods=["GET", "POST"])
@login_required
@limiter.limit("120 per minute")
def admin_jobs():
    admin_email = current_app.config.get("ADMIN_EMAIL", "admin@example.com")
    if current_user.email != admin_email:
        abort(403)

    if request.method == "POST":
        job = PublicJob(
            title=request.form["title"],
            company=request.form["company"],
            location=request.form["location"],
            salary=request.form.get("salary") or None,
            link=request.form["link"],
            description=request.form["description"],
            featured=bool(request.form.get("featured")),
        )
        db.session.add(job)
        db.session.commit()
        flash("Job posted successfully!", "success")
        return redirect(url_for("jobs.admin_jobs"))

    jobs = PublicJob.query.order_by(
        PublicJob.featured.desc(), PublicJob.timestamp.desc()
    ).all()
    return render_template("jobs/admin_jobs.html", jobs=jobs)


@jobs_bp.route("/admin/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@limiter.limit("120 per minute")
def edit_public_job(job_id):
    admin_email = current_app.config.get("ADMIN_EMAIL", "admin@example.com")
    if current_user.email != admin_email:
        abort(403)

    job = PublicJob.query.get_or_404(job_id)

    if request.method == "POST":
        job.title = request.form["title"]
        job.company = request.form["company"]
        job.location = request.form["location"]
        job.salary = request.form.get("salary") or None
        job.link = request.form["link"]
        job.description = request.form["description"]
        job.featured = bool(request.form.get("featured"))
        db.session.commit()
        flash("Job updated successfully!", "success")
        return redirect(url_for("jobs.admin_jobs"))

    return render_template("jobs/edit_job.html", job=job)


@jobs_bp.route("/admin/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@limiter.limit("60 per minute")
def delete_public_job(job_id):
    admin_email = current_app.config.get("ADMIN_EMAIL", "admin@example.com")
    if current_user.email != admin_email:
        abort(403)

    job = PublicJob.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash("Job deleted successfully.", "success")
    return redirect(url_for("jobs.admin_jobs"))
