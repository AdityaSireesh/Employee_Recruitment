import os
import uuid
from datetime import datetime
from functools import wraps

from flask import request, current_app  # Ensure this is imported at the top
from flask import (Blueprint, flash, jsonify, make_response, redirect,
                   render_template, session, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from config import Config
from models import db  # Ensure 'db' is the instance of SQLAlchemy
from models import (Certification, Company, Coupon,  # , JobApplication
                    Couponuser, Favorite, Job, JobApplication, Login,
                    Notification, ResumeCertification, User)
from utils import allowed_file  # Assuming your config file is named config.py

  # Assuming your model is in 'models.py'

user_blueprint = Blueprint('user', __name__)
import re
from datetime import (  # Ensure these are imported if not already; Ensure date is imported
    date, datetime, timedelta)
from urllib.parse import urlparse

import pytz
import requests
from flask import (flash, jsonify, redirect, render_template, request, session,
                   url_for)
from sqlalchemy import or_

from models import (Communication,  # make sure db is imported from your app
                    Job, JobApplication, Notification, ResumeCertification,
                    User, db)
from utils_url import url_seems_reachable

# ==============================================================================
# SETUP & DECORATORS
# ==============================================================================

def no_cache(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = make_response(f(*args, **kwargs))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    return decorated_function


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'login_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# DASHBOARD & ANALYTICS
# ==============================================================================

@user_blueprint.route('/user_dashboard')
@no_cache
@login_required
def user_dashboard():
    login_id = session.get('login_id')  # Use 'login_id' instead of 'user_id'
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    # Get the User object using login_id from the Login table
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    user_id = user.id  # This is the User table's id, used for job application queries
   
    db.session.commit()
    db.session.expire_all()  # Forces fresh query results
   
    # Paginate the jobs query with filters
    page = request.args.get('page', 1, type=int)
    per_page = 5  # Changed from 10 to 5
   
    # Get current date for deadline comparison
    current_date = datetime.utcnow().date()
    print(current_date)
    # Query jobs with filters:
    # 1. Exclude jobs where vacancy is full (filled_vacancy >= total_vacancy)
    # 2. Exclude jobs from banned companies
    # 3. Only show active jobs
    # 4. Exclude jobs where deadline has passed
    jobs_query = Job.query.join(Login, Job.created_by == Login.id)\
        .join(Company, Login.id == Company.login_id)\
        .filter(
            Job.filled_vacancy < Job.total_vacancy,  # Not fully filled
            Company.is_banned == False,  # Company not banned
            Job.status == 'open',  # Job is active
            Job.deadline > current_date  # Deadline has not passed
        )\
        .order_by(Job.created_at.desc())
   
    jobs_pagination = jobs_query.paginate(page=page, per_page=per_page, error_out=False)
    jobs = jobs_pagination.items
    total_pages = jobs_pagination.pages
   
    # Get user's applied jobs
    applied_jobs = db.session.query(JobApplication.job_id)\
        .filter(JobApplication.user_id == user_id)\
        .subquery()
   
    # Get user's saved jobs
    saved_jobs = db.session.query(Favorite.job_id)\
        .filter(Favorite.user_id == user_id)\
        .subquery()
   
    # Create sets for easier lookup in template
    applied_job_ids = {str(app.job_id) for app in JobApplication.query.filter_by(user_id=user_id).all()}
    saved_job_ids = {str(saved.job_id) for saved in Favorite.query.filter_by(user_id=user_id).all()}
   
    # Remove chart data; only upcoming events and notifications remain
    current_date = datetime.utcnow()
    upcoming_events = db.session.query(Job.title, Job.deadline)\
        .join(JobApplication, Job.job_id == JobApplication.job_id)\
        .filter(JobApplication.user_id == user_id, Job.deadline > current_date)\
        .order_by(Job.deadline.asc()).all()
    recent_notifications = Notification.query.filter_by(user_id=user_id, hidden=False)\
        .order_by(Notification.timestamp.desc()).limit(5).all()
   
    return render_template('/user/user_dashboard.html',
                           user=user,
                           jobs=jobs,
                           upcoming_events=upcoming_events,
                           recent_notifications=recent_notifications,
                           page=page,
                           total_pages=total_pages,
                           applied_job_ids=applied_job_ids,
                           saved_job_ids=saved_job_ids)


def get_chart_data_for_user(user_id):
    """
    Retrieves dynamic chart data, recent activities, and live feed for the given user.
    Returns four items:
      - user_success_rate: counts of applications by status (hired, rejected, pending, interviewed)
      - application_trends: daily count of applications (as a trend over time) - LIMITED TO LAST 5 DAYS
      - recent_activities: list of user's recent job applications with company names
      - live_feed: list of recent job postings
    """
    # Define IST timezone
    ist_timezone = pytz.timezone('Asia/Kolkata')
    
    # Chart data: User success rate
    hired = db.session.query(db.func.count(JobApplication.id))\
        .filter(JobApplication.user_id == user_id, JobApplication.status == 'Hired').scalar() or 0
    rejected = db.session.query(db.func.count(JobApplication.id))\
        .filter(JobApplication.user_id == user_id, JobApplication.status == 'Rejected').scalar() or 0
    pending = db.session.query(db.func.count(JobApplication.id))\
        .filter(JobApplication.user_id == user_id, JobApplication.status == 'Pending').scalar() or 0
    interviewed = db.session.query(db.func.count(JobApplication.id))\
        .filter(JobApplication.user_id == user_id, JobApplication.status == 'Interviewed').scalar() or 0
    
    user_success_rate = {"hired": hired, "rejected": rejected, "pending": pending, "interviewed": interviewed}
    
    # Chart data: Application trends (daily count) - LIMITED TO LAST 5 DAYS
    # Calculate the date 5 days ago from today in IST
    today = datetime.now(ist_timezone).date()
    five_days_ago = today - timedelta(days=4)  # 4 days ago + today = 5 days total
    
    # Convert IST dates to UTC for database comparison
    five_days_ago_utc = ist_timezone.localize(datetime.combine(five_days_ago, datetime.min.time())).astimezone(pytz.utc)
    today_end_utc = ist_timezone.localize(datetime.combine(today, datetime.max.time())).astimezone(pytz.utc)
    
    # Query for applications in the last 5 days (in UTC range)
    applications = db.session.query(JobApplication)\
        .filter(
            JobApplication.user_id == user_id,
            JobApplication.date_applied >= five_days_ago_utc,
            JobApplication.date_applied <= today_end_utc
        ).all()
    
    # Group applications by IST date
    date_counts = {}
    for app in applications:
        # Convert UTC datetime to IST
        if app.date_applied.tzinfo is None:
            # If datetime is naive, assume it's UTC
            utc_datetime = pytz.utc.localize(app.date_applied)
        else:
            utc_datetime = app.date_applied.astimezone(pytz.utc)
        
        # Convert to IST
        ist_datetime = utc_datetime.astimezone(ist_timezone)
        ist_date = ist_datetime.date()
        
        # Count applications per IST date
        if ist_date in date_counts:
            date_counts[ist_date] += 1
        else:
            date_counts[ist_date] = 1
    
    # Create a complete list of the last 5 days (including days with 0 applications)
    date_range = []
    count_range = []
    
    for i in range(5):
        current_date = five_days_ago + timedelta(days=i)
        date_range.append(current_date.strftime('%Y-%m-%d'))
        
        # Get count for this date
        count_for_date = date_counts.get(current_date, 0)
        count_range.append(count_for_date)
    
    application_trends = {"labels": date_range, "counts": count_range}
    
    # ==============================================================================
    # CONSOLIDATED LIVE FEED (Recent 5 Interactions)
    # ==============================================================================
    
    # 1. Job Applications (User applied)
    # ------------------------------------------------------------------------------
    recent_applications = db.session.query(JobApplication, Job.title, Company.company_name)\
        .join(Job, Job.job_id == JobApplication.job_id)\
        .join(Login, Login.id == Job.created_by)\
        .join(Company, Company.login_id == Login.id)\
        .filter(JobApplication.user_id == user_id)\
        .order_by(JobApplication.date_applied.desc())\
        .limit(5).all()

    # 2. Status Updates (Status changed)
    # ------------------------------------------------------------------------------
    # We filter where status_updated_at is different from date_applied (approx) 
    # or just show all status updates that are recent.
    # For simplicity, we'll fetch recent applications and check if status is not 'Pending'
    # In a real event sourcing system, these would be separate table entries.
    recent_updates = db.session.query(JobApplication, Job.title, Company.company_name)\
        .join(Job, Job.job_id == JobApplication.job_id)\
        .join(Login, Login.id == Job.created_by)\
        .join(Company, Company.login_id == Login.id)\
        .filter(
            JobApplication.user_id == user_id,
            JobApplication.status != 'Pending'
        )\
        .order_by(JobApplication.status_updated_at.desc())\
        .limit(5).all()

    # 3. New Job Postings (Platform activity)
    # ------------------------------------------------------------------------------
    recent_jobs = db.session.query(Job.title, Job.created_at, Company.company_name)\
        .join(Login, Login.id == Job.created_by)\
        .join(Company, Company.login_id == Login.id)\
        .filter(Job.deadline >= current_date)\
        .order_by(Job.created_at.desc())\
        .limit(5).all()

    # Merge and Normalize
    # ------------------------------------------------------------------------------
    consolidated_feed = []

    # Process Applications
    for app, job_title, company_name in recent_applications:
        consolidated_feed.append({
            'activity': f"Applied for {job_title} at {company_name}",
            'timestamp': app.date_applied,
            'type': 'application'
        })
    
    # Process Updates
    for app, job_title, company_name in recent_updates:
        # Check timestamps to avoid showing "Applied" and "Status Updated" as duplicates if they happen instantly (e.g. auto-reject)
        # But for now, we'll just add them.
         consolidated_feed.append({
            'activity': f"Application status updated to '{app.status}' for {job_title}",
            'timestamp': app.status_updated_at,
            'type': 'status_update'
        })

    # Process New Jobs
    for job_title, created_at, company_name in recent_jobs:
        consolidated_feed.append({
            'activity': f"New job posted: {job_title} at {company_name}",
            'timestamp': created_at,
            'type': 'job_post'
        })

    # Sort by Timestamp Descending
    # ------------------------------------------------------------------------------
    # Ensure all timestamps are timezone-aware (UTC) before sorting
    for item in consolidated_feed:
        ts = item['timestamp']
        if ts:
            if ts.tzinfo is None:
                item['timestamp'] = pytz.utc.localize(ts)
            else:
                item['timestamp'] = ts.astimezone(pytz.utc)
        else:
            # Fallback for missing timestamps
             item['timestamp'] = pytz.utc.localize(datetime.min)

    consolidated_feed.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Take top 5
    live_feed_list = consolidated_feed[:5]
    
    # We keep recent_activities as empty or separate if needed, but per request, 
    # we are consolidating into 'live_feed'. The 'recent_activities' variable 
    # is still used in the return signature, so we should keep it populated 
    # OR update the return signature. The user said "consolidate", likely meaning 
    # the "Live Feed" on UI should show this. 
    # The current UI has TWO tables. "Recent Activities" (User's stuff) and "Live Feed" (Job postings).
    # The request says "consolidated... put into a table which shows the latest 5 interaction as live feed".
    # This implies ONE table.
    
    # Let's populate 'live_feed_list' with the consolidated data.
    # We will pass this consolidated list as 'live_feed' to the template.
    # We can pass an empty list for 'recent_activities' or just ignore it in template.
    
    # However, to be safe and "not break current idea", we will pass the SAME consolidated list
    # or just keep 'recent_activities_list' as the user-specific subset if needed.
    # But user asked to "consolidate".
    
    # Let's populate recent_activities_list with just the User Actions subset for backward compat if needed,
    # or just replicate the feed if the UI expects two lists.
    # Actuallly, the prompt implies replacing the "Live Feed" content.
    # I will pass the consolidated list as `live_feed_list` and keep `recent_activities_list` 
    # as just the application history to avoid breaking the "Recent Activities" table if the user decides to keep it.
    # Wait, the user said "Live Feed... doesn't have updated at... modify to display last 5 interactions... put into a table... as live feed".
    # This suggests the "Live Feed" section should now become this consolidated feed.
    
    # I will leave recent_activities_list as is (Application History) for the "Recent Activities" table 
    # (which we just fixed sorting for) unless the user wants to REMOVE that table.
    # The user said "consolidate... into a table... as live feed".
    # So I will overwrite `live_feed_list` with the consolidated data.
    
    # Using existing logic for recent_activities_list (User specific)
    recent_activities_list = [
        {
            'job_title': f"{job_title} ({company_name})",
            'status': app.status
        }
        for app, job_title, company_name in recent_applications 
    ]
    
    return user_success_rate, application_trends, recent_activities_list, live_feed_list


@user_blueprint.route('/analytics')
@no_cache
@login_required
def analytics():
    login_id = session.get('login_id')  # Use 'login_id' instead of 'user_id'
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    # Get the User object using login_id from the Login table
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    user_id = session.get('user_id')
    user_success_rate, application_trends, recent_activities, live_feed = get_chart_data_for_user(user_id)
    return render_template(
        '/user/analytics.html',
        user=user,
        user_success_rate=user_success_rate,
        application_trends=application_trends,
        recent_activities=recent_activities,
        live_feed=live_feed
    )


# ==============================================================================
# PROFILE MANAGEMENT
# ==============================================================================

# ============================================================================
# USER PROFILE ROUTE WITH ENHANCED VALIDATION
# ============================================================================
@user_blueprint.route('/profile', methods=['GET', 'POST'])
@no_cache
@login_required
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to log in to access your profile.', 'error')
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('user.user_dashboard'))
    
    # Retrieve related data
    resumes = ResumeCertification.query.filter_by(user_id=user_id).all()
    certifications = Certification.query.filter_by(user_id=user_id).all()

    # Get user's coupon information
    user_coupon_mapping = Couponuser.query.filter_by(user_id=user_id).first()
    user_coupon = None
    if user_coupon_mapping:
        user_coupon = Coupon.query.filter_by(id=user_coupon_mapping.coupon_id).first()

    edit_mode = request.args.get('edit', 'false').lower() == 'true'
    form_values = {}
    errors = {}

    if request.method == 'POST':
        # Get raw inputs
        raw_name = request.form.get('name', '').strip()
        raw_email = request.form.get('email', '').strip()
        raw_phone = request.form.get('phone', '').strip()
        raw_age = request.form.get('age', '').strip()
        raw_manual_college = request.form.get('college_name', '').strip()
        raw_about_me = request.form.get('about_me', '').strip()
        raw_coupon_code = request.form.get('coupon_code', '').strip()

        # Store for repopulation
        form_values = {
            'name': raw_name,
            'email': raw_email,
            'phone': raw_phone,
            'age': raw_age,
            'college_name': raw_manual_college,
            'about_me': raw_about_me,
            'coupon_code': raw_coupon_code
        }

        # 1. Invalid Character Check (< or >)
        text_fields_to_check = [
            ('Name', raw_name, 'name'),
            ('Email', raw_email, 'email'),
            ('Phone', raw_phone, 'phone'),
            ('College Name', raw_manual_college, 'college_name'),
            ('About Me', raw_about_me, 'about_me'),
            ('Coupon Code', raw_coupon_code, 'coupon_code')
        ]
        for field_label, raw_value, field_key in text_fields_to_check:
            if '<' in raw_value or '>' in raw_value:
                errors[field_key] = f"Invalid characters (< or >) not allowed in {field_label}."
        
        if errors:
             return render_template('/user/profile.html', user=user, resumes=resumes, certifications=certifications, user_coupon=user_coupon, edit_mode=True, form_values=form_values, errors=errors)

        # Sanitize inputs
        name_input = sanitize_text(raw_name)
        email_input = sanitize_text(raw_email)
        phone_input = sanitize_text(raw_phone)
        age_input = sanitize_text(raw_age)
        manual_college = sanitize_text(raw_manual_college)
        about_me_input = sanitize_text(raw_about_me)
        coupon_code = sanitize_text(raw_coupon_code)

        # 2. Name Validation
        if not name_input:
            errors['name'] = "Name is required."
        elif not re.match(r"^[a-zA-Z\s\.\']+$", name_input):
            errors['name'] = "Name must contain only letters, spaces, dots, or apostrophes."
        elif len(name_input) < 2:
            errors['name'] = "Name must be at least 2 characters long."
        elif len(name_input) > 100:
            errors['name'] = "Name cannot exceed 100 characters."

        # 3. Email Validation
        if not email_input:
            errors['email'] = "Email is required."
        elif not is_valid_email(email_input):
            errors['email'] = "Please enter a valid email address."
        elif email_input != user.email:
            existing_email_user = User.query.filter_by(email=email_input).first()
            if existing_email_user:
                errors['email'] = "This email is already registered."

        # 4. Phone Validation
        if phone_input:
            if not phone_input.isdigit():
                 errors['phone'] = "Phone number must contain only digits."
            elif all(c == '0' for c in phone_input):
                 errors['phone'] = "Phone number cannot be all zeros."
            elif len(phone_input) < 10 or len(phone_input) > 15:
                 errors['phone'] = "Phone number must be between 10 and 15 digits."
            else:
                existing_phone_user = User.query.filter(User.phone == phone_input, User.id != user_id).first()
                if existing_phone_user:
                    errors['phone'] = "This phone number is already in use."

        # 5. Age Validation
        if age_input:
            try:
                age_val = int(age_input)
                if age_val < 18 or age_val > 80:
                    errors['age'] = "Age must be between 18 and 80."
            except ValueError:
                errors['age'] = "Invalid age."

        # 6. About Me Validation
        if about_me_input:
            length_check = len(about_me_input)
            if length_check > 2000:
                 errors['about_me'] = "About Me cannot exceed 2000 characters."
            
            word_count = len(about_me_input.split())
            if word_count > 200:
                 errors['about_me'] = f"About Me cannot exceed 200 words. (Current: {word_count})"

        # 7. College Name Validation
        if manual_college and len(manual_college) > 200:
            errors['college_name'] = "College name cannot exceed 200 characters."

        # 8. Coupon validation
        if coupon_code and not user_coupon:
            coupon = Coupon.query.filter_by(code=coupon_code).first()
            if not coupon:
                errors['coupon_code'] = "Invalid coupon code provided."
            else:
                cutoff = datetime.now() - timedelta(days=730)
                if coupon.created_at < cutoff:
                    errors['coupon_code'] = "Coupon has expired."
                
                # Apply coupon (only if no errors so far prevents partial state)
                if not errors:
                    existing_map = Couponuser.query.filter_by(user_id=user_id, coupon_id=coupon.id).first()
                    if not existing_map:
                        new_map = Couponuser(user_id=user_id, coupon_id=coupon.id)
                        db.session.add(new_map)
                        if coupon.college:
                            user.college_name = coupon.college.college_name
                        flash("Coupon code applied successfully!", "success")
                        # Refresh coupon info
                        user_coupon = coupon
        db.session.commit()

        if errors:
            return render_template('/user/profile.html', user=user, resumes=resumes, certifications=certifications, user_coupon=user_coupon, edit_mode=True, form_values=form_values, errors=errors)

        # Update User fields if no errors
        user.name = name_input
        user.email = email_input
        user.phone = phone_input if phone_input else None
        user.age = int(age_input) if age_input else None
        user.about_me = about_me_input if about_me_input else None
        
        try:
            db.session.commit()
            flash("Profile updated successfully!", "success")
            return redirect(url_for('user.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {str(e)}", "error")
            return render_template('/user/profile.html', user=user, resumes=resumes, certifications=certifications, user_coupon=user_coupon, edit_mode=True, form_values=form_values, errors=errors)

    return render_template('/user/profile.html', user=user, resumes=resumes, certifications=certifications, user_coupon=user_coupon, edit_mode=edit_mode, form_values=form_values, errors=errors)

@user_blueprint.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))

    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        
        if file and file.filename != '':
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
            
            if allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"profile_{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                
                profile_pics_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_pics')
                if not os.path.exists(profile_pics_dir):
                    os.makedirs(profile_pics_dir)
                    
                file_path = os.path.join(profile_pics_dir, unique_filename)
                file.save(file_path)
                
                # Update the database
                user.profile_picture = f"/static/uploads/profile_pics/{unique_filename}"
                db.session.commit()
                flash('Profile picture updated successfully!', 'success')
            else:
                flash('Invalid image format. Only JPG, PNG, and GIF are allowed.', 'danger')
        else:
            flash('No file selected.', 'danger')
            
    return redirect(url_for('user.profile'))

# ==============================================================================
# RESUMES & CERTIFICATIONS
# ==============================================================================

@user_blueprint.route('/resume_certifications', methods=['GET', 'POST'])
@no_cache
@login_required
def resume_certifications():
    login_id = session.get('login_id')  # Use 'login_id' instead of 'user_id'
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    # Get the User object using login_id from the Login table
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    # Fetch user data
    users = User.query.get(user_id)
    print(user_id, users)
    if not users:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Check if the form submission is for a resume or a certification
        if 'resume' in request.files:
            # Handle Resume Upload
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            resume = request.files.get('resume')
            # Check for 0-byte file
            resume.seek(0, os.SEEK_END)
            file_length = resume.tell()
            resume.seek(0)  # Reset cursor
            if file_length == 0:
                flash("File cannot be empty.", "error")
                return redirect(url_for('user.resume_certifications'))
            
            if resume and allowed_file(resume.filename):
                resume_filename = secure_filename(resume.filename)
                resume_path = os.path.join(upload_folder, f"resume_{users.name}_{resume_filename}")
                resume.save(resume_path)
                resume_path = resume_path.replace('\\', '/')  # Normalize path for web use
                
                # Save Resume Entry
                resume_entry = ResumeCertification(user_id=users.id, resume_path=resume_path)
                db.session.add(resume_entry)
                db.session.commit()
                flash('Resume uploaded successfully!', 'success')
                
        elif 'certification_name' in request.form:
            # Handle Certification/Skill Additions
            raw_input = request.form.get('certification_name', '')
            skill_names = [s.strip() for s in raw_input.split(',') if s.strip()]
            
            if skill_names:
                added_skills = []
                duplicate_skills = []
                
                for skill_name in skill_names:
                    # Check if certification already exists (case insensitive)
                    existing_certification = Certification.query.filter(
                        Certification.user_id == users.id,
                        db.func.lower(Certification.certification_name) == skill_name.lower()
                    ).first()
                    
                    if existing_certification:
                        duplicate_skills.append(skill_name)
                    else:
                        certification = Certification(
                            user_id=users.id,
                            certification_name=skill_name,
                            verification_status=False
                        )
                        db.session.add(certification)
                        added_skills.append(skill_name)
                
                if added_skills:
                    db.session.commit()
                    flash(f'Skills added: {", ".join(added_skills)}', 'success')
                
                if duplicate_skills:
                    flash(f'Skills already exist: {", ".join(duplicate_skills)}', 'warning')
            else:
                flash('Please enter a skill name.', 'error')
        
        return redirect(url_for('user.resume_certifications'))
    
    # Retrieve dynamic chart data, recent activities, and live feed using the helper function
    user_success_rate, applications_overview, recent_activities, live_feed = get_chart_data_for_user(user_id)
    
    # Retrieve data for display - Sorted by uploaded_at descending
    resumes = ResumeCertification.query.filter_by(user_id=user_id).order_by(ResumeCertification.uploaded_at.desc()).all()
    certifications = Certification.query.filter_by(user_id=user_id).all()
    
    return render_template(
        '/user/resume_certifications.html',
        user=user,
        resume_certifications=resumes,
        certifications=certifications,
        user_success_rate=user_success_rate,
        applications_overview=applications_overview,
        recent_activities=recent_activities,
        live_feed=live_feed
    )


@user_blueprint.route('/delete_resume/<uuid:resume_id>', methods=['POST'])
@no_cache
@login_required
def delete_resume(resume_id):
    # Check if user is logged in
    if 'username' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        username = session['username']
        
        # Get the login record first
        login = Login.query.filter_by(username=username).first()
        if not login:
            flash('Login not found!', 'error')
            return redirect(url_for('user.resume_certifications'))
        
        # Get the user record using the login_id
        user = User.query.filter_by(login_id=login.id).first()
        if not user:
            flash('User not found!', 'error')
            return redirect(url_for('user.resume_certifications'))
        
        # Find the resume for this specific user
        resume = ResumeCertification.query.filter_by(
            id=resume_id, 
            user_id=user.id
        ).first()
        
        if resume:
            # Delete the file from filesystem
            import os
            if resume.resume_path and os.path.exists(resume.resume_path):
                os.remove(resume.resume_path)
            
            # Delete the record from database
            db.session.delete(resume)
            db.session.commit()
            
            flash('Resume deleted successfully!', 'success')
        else:
            flash('Resume not found or you do not have permission to delete it!', 'error')
            
    except Exception as e:
        print(f"Error deleting resume: {str(e)}")
        flash('Error deleting resume!', 'error')
        
    return redirect(url_for('user.resume_certifications'))


@user_blueprint.route('/delete_certification/<uuid:certification_id>', methods=['POST'])
@no_cache
@login_required
def delete_certification(certification_id):
    # Check if user is logged in
    if 'username' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('auth.login'))
   
    try:
        username = session['username']
       
        # Get the login record first
        login = Login.query.filter_by(username=username).first()
        if not login:
            flash('Login not found!', 'error')
            return redirect(url_for('user.resume_certifications'))
       
        # Get the user record using the login_id
        user = User.query.filter_by(login_id=login.id).first()
        if not user:
            flash('User not found!', 'error')
            return redirect(url_for('user.resume_certifications'))
       
        # Find the certification for this specific user
        # Assuming Certification model has user_id field
        certification = Certification.query.filter_by(
            id=certification_id,
            user_id=user.id
        ).first()
       
        if certification:
            # Delete the certification record from database
            db.session.delete(certification)
            db.session.commit()
           
            flash('Skill/Certification deleted successfully!', 'success')
        else:
            flash('Skill/Certification not found or you do not have permission to delete it!', 'error')
           
    except Exception as e:
        print(f"Error deleting certification: {str(e)}")
        flash('Error deleting skill/certification!', 'error')
       
    return redirect(url_for('user.resume_certifications'))


# ==============================================================================
# JOB SEARCH
# ==============================================================================

# Assuming sanitize_text is already defined from previous helpers

# ============================================================================
# JOB SEARCH ROUTE WITH ENHANCED VALIDATION AND SANITIZATION
# ============================================================================
@user_blueprint.route('/job_search', methods=['GET', 'POST'])
@no_cache
@login_required
def job_search():
    # Dictionary to hold form values for template repopulation on error
    form_values = {}
    login_id = session.get('login_id')  # Use 'login_id' instead of 'user_id'
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    # Get the User object using login_id from the Login table
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        # Get raw inputs first for invalid char check and repopulation
        raw_keyword = request.form.get('keyword', '').strip()
        raw_location = request.form.get('location', '').strip()
        raw_job_type = request.form.get('job_type', '').strip()
        raw_years_of_exp = request.form.get('years_of_exp', '').strip()
        raw_skills = request.form.get('skills', '').strip()
        raw_certifications = request.form.get('certifications', '').strip()
        raw_deadline = request.form.get('deadline', '').strip()

        # Store raw values for repopulation
        form_values = {
            'keyword': raw_keyword,
            'location': raw_location,
            'job_type': raw_job_type,
            'years_of_exp': raw_years_of_exp,
            'skills': raw_skills,
            'certifications': raw_certifications,
            'deadline': raw_deadline
        }

        # Check for invalid characters (< or >) in all text fields
        text_fields_to_check = [
            ('Keyword', raw_keyword),
            ('Location', raw_location),
            ('Skills', raw_skills),
            ('Certifications', raw_certifications)
        ]
        for field_name, raw_value in text_fields_to_check:
            if '<' in raw_value or '>' in raw_value:
                flash(f"Invalid characters (< or >) not allowed in {field_name} field.", "error")
                return render_template('/user/jobsearch.html', form_values=form_values)

        # Sanitize inputs after invalid char check
        keyword = sanitize_text(raw_keyword)
        location = sanitize_text(raw_location)
        job_type = sanitize_text(raw_job_type)
        years_of_exp = sanitize_text(raw_years_of_exp)
        skills = sanitize_text(raw_skills)
        certifications = sanitize_text(raw_certifications)
        deadline_str = sanitize_text(raw_deadline)

        # Validate deadline if provided
        deadline = None
        if deadline_str:
            try:
                deadline = date.fromisoformat(deadline_str)
                if deadline < date.today():
                    flash("Deadline cannot be in the past.", "error")
                    return render_template('/user/jobsearch.html', form_values=form_values)
            except ValueError:
                flash("Please enter a valid deadline date.", "error")
                return render_template('/user/jobsearch.html', form_values=form_values)

        # Get pagination parameters
        page = request.form.get('page', 1, type=int)
        per_page = 6  # Jobs per page

        # Get current date for base deadline comparison (show jobs on or after today)
        current_date = date.today()

        # Build the query with deadline check (>= for on or after today)
        query = Job.query.join(Company, Job.created_by == Company.login_id).filter(
            Job.status != 'closed',
            Company.is_banned == False,
            Job.deadline >= current_date  # Show jobs with deadline on or after today
        )

        # Apply search filters
        if keyword:
            keyword_like = f'%{keyword}%'
            query = query.filter(
                or_(
                    Job.title.ilike(keyword_like),
                    Job.description.ilike(keyword_like),
                    Job.skills.ilike(keyword_like),
                    Job.certifications.ilike(keyword_like),
                    Company.company_name.ilike(keyword_like)
                )
            )

        if location:
            query = query.filter(Job.location.ilike(f'%{location}%'))

        if job_type:
            query = query.filter(Job.job_type.ilike(job_type))

        if years_of_exp:
            try:
                if years_of_exp == '6':
                    query = query.filter(Job.years_of_exp >= 6)
                else:
                    exp_val = int(years_of_exp)
                    query = query.filter(Job.years_of_exp == exp_val)
            except (ValueError, TypeError):
                pass

        # Apply deadline filter if provided (jobs expiring on or before specified date)
        if deadline:
            # Search for jobs expiring *on or before* the deadline date.
            # To include jobs expiring at any time on the deadline date (e.g. 11:59PM),
            # we check if job.deadline is LESS than the *next* day at 00:00:00.
            next_day = deadline + timedelta(days=1)
            query = query.filter(Job.deadline < next_day)

        if skills:
            skills_list = [skill.strip() for skill in skills.split(',') if skill.strip()]
            if skills_list:
                skills_filters = [Job.skills.ilike(f'%{skill}%') for skill in skills_list]
                query = query.filter(or_(*skills_filters))

        if certifications:
            cert_list = [cert.strip() for cert in certifications.split(',') if cert.strip()]
            if cert_list:
                cert_filters = [Job.certifications.ilike(f'%{cert}%') for cert in cert_list]
                query = query.filter(or_(*cert_filters))

        # Apply pagination
        jobs_pagination = query.order_by(Job.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        jobs = jobs_pagination.items

        # Get user's applied and saved jobs
        current_user_id = session.get('user_id')
        applied_applications = JobApplication.query.filter_by(user_id=current_user_id).all()
        applied_jobs = {app.job_id for app in applied_applications}
        saved_favorites = Favorite.query.filter_by(user_id=current_user_id).all()
        saved_jobs = {fav.job_id for fav in saved_favorites}

        # Pass search parameters to maintain state in results
        search_params = {
            'keyword': keyword,
            'location': location,
            'job_type': job_type,
            'years_of_exp': years_of_exp,
            'skills': skills,
            'certifications': certifications,
            'deadline': deadline_str if deadline_str else ''
        }

        # Passing current_date for calendar constraints
        return render_template('/user/jobresults.html',
                               user=user,
                               jobs=jobs,
                               applied_jobs=applied_jobs,
                               saved_jobs=saved_jobs,
                               pagination=jobs_pagination,
                               search_params=search_params,
                               current_date=current_date)
    else:
        # Passing current_date for calendar constraints
        return render_template('/user/jobsearch.html', user=user, form_values=form_values, current_date=date.today())


# Job Details Route - Add this new route
@user_blueprint.route('/job_details/<uuid:job_id>')
@no_cache
@login_required
def job_details(job_id):
    login_id = session.get('login_id')
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    
    # Get current date for deadline comparison
    current_date = datetime.utcnow().date()
    
    # Fetch the job with deadline check
    job = Job.query.join(Company, Job.created_by == Company.login_id).filter(
        Job.job_id == job_id,
        Job.status != 'closed',
        Company.is_banned == False,
        Job.deadline > current_date  # Only show if deadline hasn't passed
    ).first()
    
    if not job:
        flash("Job not found or no longer available", "error")
        return redirect(url_for('user.job_search'))
    
    # Get user's applied and saved jobs
    applied_jobs = {app.job_id for app in JobApplication.query.filter_by(user_id=user.id).all()}
    saved_jobs = {fav.job_id for fav in Favorite.query.filter_by(user_id=user.id).all()}
    
    return render_template('/user/jobresults.html',
                           user=user, 
                         job=job, 
                         applied_jobs=applied_jobs, 
                         saved_jobs=saved_jobs)


# ==============================================================================
# JOB APPLICATIONS
# ==============================================================================

@user_blueprint.route('/apply_for_job/<uuid:job_id>', methods=['POST'])
@no_cache
@login_required
def apply_for_job(job_id):
    user_id = session.get('user_id')
    user = User.query.get(user_id)  

    if not user:
        flash("User not found.", 'error')
        return redirect(url_for('user.user_dashboard'))

    # Fetch the job that the user is applying for
    job = Job.query.get(job_id)

    if not job:
        flash("Job not found.", 'error')
        return redirect(url_for('user.user_dashboard'))
    
    if job.status=='closed':
        flash("Applications have been closed for this job.", 'error')
        return redirect(url_for('user.user_dashboard'))

    # Fetch the user's resume from the ResumeCertification table
    resume_certification = ResumeCertification.query.filter_by(user_id=user.id).order_by(ResumeCertification.uploaded_at.desc()).first()
    
    if not resume_certification or not resume_certification.resume_path:
        flash("You must upload a resume to apply for a job.", 'error')
        return redirect(url_for('user.resume_certifications'))

    print("Debugging: Resume Path:", resume_certification.resume_path)  # Debugging Output

    # Check if the user has already applied for this job
    existing_application = JobApplication.query.filter_by(user_id=user.id, job_id=job_id).first()
    if existing_application:
        flash(f"You have already applied for the job {job.title}.", 'error')
        return redirect(url_for('user.user_dashboard'))

    # Ensure date_applied and status_updated_at are set properly
    new_application = JobApplication(
        user_id=user.id,
        job_id=job.job_id,
        status='Pending',  
        resume_path=resume_certification.resume_path,
        
    )

    # Send notification to company
    message = f"{user.name} has applied for the job: {job.title}"
    new_notification = Notification(
        user_id=user.login_id,
        company_id=job.created_by,
        message=message
    )

    # Add and commit changes to the database
    db.session.add(new_application)
    db.session.add(new_notification)
    db.session.commit()

    flash(f"Application for {job.title} submitted successfully!", 'success')
    return redirect(request.referrer or url_for('user.user_dashboard'))



# Updated Apply for Job Route
@user_blueprint.route('/apply1_for_job/<uuid:job_id>', methods=['POST'])
@no_cache
@login_required
def apply1_for_job(job_id):
    user_id = session.get('user_id')
    user = User.query.get(user_id)  
    if not user:
        flash("User not found.", 'error')
        return redirect(url_for('user.user_dashboard'))
    
    # Get the source page to determine redirect behavior
    source_page = request.form.get('source_page', 'job_search')
    
    # Fetch the job that the user is applying for
    job = Job.query.get(job_id)
    if not job:
        flash("Job not found.", 'error')
        return redirect(request.referrer or url_for('user.job_search'))
   
    # Fetch the user's resume from the ResumeCertification table
    resume_certification = ResumeCertification.query.filter_by(user_id=user.id).order_by(ResumeCertification.uploaded_at.desc()).first()
   
    if not resume_certification or not resume_certification.resume_path:
        flash("You must upload a resume to apply for a job.", 'error')
        return redirect(url_for('user.resume_certifications'))
    
    print("Debugging: Resume Path:", resume_certification.resume_path)  # Debugging Output
    
    # Check if the user has already applied for this job
    existing_application = JobApplication.query.filter_by(user_id=user.id, job_id=job_id).first()
    if existing_application:
        flash(f"You have already applied for the job {job.title}.", 'danger')
        return redirect(request.referrer or url_for('user.job_search'))
    
    # Ensure date_applied and status_updated_at are set properly
    new_application = JobApplication(
        user_id=user.id,
        job_id=job.job_id,
        status='Pending',  
        resume_path=resume_certification.resume_path,
    )
    
    # Send notification to company
    message = f"{user.name} has applied for the job: {job.title}"
    new_notification = Notification(
        user_id=user.login_id,
        company_id=job.created_by,
        message=message
    )
    
    # Add and commit changes to the database
    db.session.add(new_application)
    db.session.add(new_notification)
    db.session.commit()
    
    flash(f"Application for {job.title} submitted successfully!", 'success')
    return redirect(request.referrer or url_for('user.job_search'))


# Don't forget to ensure 'from sqlalchemy import or_' and 'from models import Job' are at the top!

@user_blueprint.route('/application_history', methods=['GET'])
@no_cache
@login_required
def application_history():
    login_id = session.get('login_id')  # Use 'login_id' instead of 'user_id'
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    # Get the User object using login_id from the Login table
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    user_id = session.get('user_id')
   
    if not user_id:
        flash("User is not logged in.", "error")
        return redirect(url_for('auth.login'))
    
    #pagination info filter and search
    page = request.args.get('page', 1, type=int)
    per_page = 5
    
    search_query = request.args.get('search_query', '').strip()
    selected_status = request.args.getlist('status')
    
    # Base query: Join with Job table so we can search by job title
    query = JobApplication.query.join(Job).filter(JobApplication.user_id == user_id)
    
    # Apply status filters if any are checked
    if selected_status:
        query = query.filter(JobApplication.status.in_(selected_status))
        
    # Apply search query across job title and application status
    if search_query:
        query = query.filter(
            or_(
                Job.title.ilike(f'%{search_query}%'),
                JobApplication.status.ilike(f'%{search_query}%')
            )
        )
        
    # Order and paginate the final filtered results
    pagination = query.order_by(JobApplication.date_applied.desc()).paginate(page=page, per_page=per_page, error_out=False)
    applications = pagination.items
    
    # Retrieve chart data, recent activities, and live feed using the common helper function
    user_success_rate, applications_overview, recent_activities, live_feed = get_chart_data_for_user(user_id)
    
    # Render the template with the application data, chart data, recent activities, and live feed
    return render_template('/user/applicationhistory.html',
        user=user,
        applications=applications,
        user_success_rate=user_success_rate,
        applications_overview=applications_overview,
        recent_activities=recent_activities,
        live_feed=live_feed,
        pagination=pagination,
        page=page,
        search_query=search_query,
        selected_status=selected_status
    )


@user_blueprint.route('/api/application_v2/<uuid:application_id>', methods=['GET'])
@no_cache
@login_required
def get_application_details_api(application_id):
    """API endpoint to get fresh application details"""
    try:
        # Force a session refresh to ensure we get the latest data from DB
        # This handles cases where the status was updated by another user (Company)
        db.session.commit()
        db.session.expire_all()
        
        user_pk = session.get('user_id')
        if not user_pk:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch the application making sure it belongs to the logged-in user
        application = JobApplication.query.filter_by(id=application_id, user_id=user_pk).first()
        
        if not application:
            return jsonify({'error': 'Application not found'}), 404
            
        # Get related data
        job = Job.query.get(application.job_id)
        # Using the same join logic as used elsewhere to get company name
        # Job -> Login (created_by) -> Company
        company_name = "Unknown Company"
        if job:
            creator = Login.query.get(job.created_by)
            if creator:
                company_record = Company.query.filter_by(login_id=creator.id).first()
                if company_record:
                    company_name = company_record.company_name

        return jsonify({
            'id': application.id,
            'job_title': job.title if job else "Unknown Job",
            'company_name': company_name,
            'status': application.status,
            'date_applied': application.date_applied.isoformat() if application.date_applied else None,
            'status_updated_at': application.status_updated_at.isoformat() if application.status_updated_at else None
        })
    except Exception as e:
        print(f"Error fetching application details: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ==============================================================================
# SAVED JOBS / FAVORITES
# ==============================================================================
@user_blueprint.route('/save_job/<uuid:job_id>', methods=['POST'])
@no_cache
@login_required
def save_job(job_id):
    login_id = session.get('login_id')
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    
    # Check if job is already saved
    existing_favorite = Favorite.query.filter_by(user_id=user.id, job_id=job_id).first()
    if existing_favorite:
        flash("Job already saved", "info")
        return redirect(request.referrer or url_for('user.user_dashboard'))
    
    # Create new favorite entry
    new_favorite = Favorite(user_id=user.id, job_id=job_id)
    db.session.add(new_favorite)
    db.session.commit()
    
    flash("Job saved to favorites", "success")
    return redirect(request.referrer or url_for('user.user_dashboard'))

# Updated Save Job Route
@user_blueprint.route('/save_job1/<uuid:job_id>', methods=['POST'])
@no_cache
@login_required
def save_job1(job_id):
    login_id = session.get('login_id')
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
   
    # Get the source page to determine redirect behavior
    source_page = request.form.get('source_page', 'job_search')
    
    # Check if job is already saved
    existing_favorite = Favorite.query.filter_by(user_id=user.id, job_id=job_id).first()
    if existing_favorite:
        flash("Job already saved", "info")
        return redirect(request.referrer or url_for('user.job_search'))
   
    # Create new favorite entry
    new_favorite = Favorite(user_id=user.id, job_id=job_id)
    db.session.add(new_favorite)
    db.session.commit()
   
    flash("Job saved to favorites", "success")
    return redirect(request.referrer or url_for('user.job_search'))


@user_blueprint.route('/favorites')
@no_cache
@login_required
def favorites():
    login_id = session.get('login_id')
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
   
    # Ensure that only regular users access this page
    if session.get('role') != 'user':
        return redirect(url_for('auth.login'))
   
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
   
    # Get pagination and search parameters
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '', type=str).strip()
    per_page = 5  # Number of favorites per page, adjust as needed
   
    # Base query - Join Favorite with Job and include company information
    favorites_query = (
        db.session.query(Job)
        .join(Favorite, Job.job_id == Favorite.job_id)
        .join(Login, Job.created_by == Login.id)
        .join(Company, Login.id == Company.login_id)
        .filter(
            Favorite.user_id == user.id,
            Job.filled_vacancy < Job.total_vacancy,  # Not fully filled
            Company.is_banned == False,  # Company not banned
            Job.status == 'open'  # Job is active
        )
    )
    
    # Apply search filter if search query exists
    if search_query:
        favorites_query = favorites_query.filter(
            or_(
                Job.title.ilike(f'%{search_query}%'),
                Job.description.ilike(f'%{search_query}%'),
                Job.skills.ilike(f'%{search_query}%'),
                Job.location.ilike(f'%{search_query}%'),
                Job.job_type.ilike(f'%{search_query}%'),
                Job.certifications.ilike(f'%{search_query}%'),
                Company.company_name.ilike(f'%{search_query}%')
            )
        )
    
    # Order by saved date
    favorites_query = favorites_query.order_by(Favorite.saved_at.desc())
   
    # Apply pagination
    favorites_pagination = favorites_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
   
    # Get the Job objects
    favorites = favorites_pagination.items
   
    # Get list of job IDs that the user has already applied to
    applied_job_ids = set()
    if favorites:
        job_ids = [job.job_id for job in favorites]
        applied_jobs = (
            db.session.query(JobApplication.job_id)
            .filter(
                JobApplication.user_id == user.id,
                JobApplication.job_id.in_(job_ids)
            )
            .all()
        )
        applied_job_ids = {job_id for (job_id,) in applied_jobs}
   
    return render_template(
        '/user/favorites.html',
        user=user,
        favorites=favorites,
        page=favorites_pagination.page,
        total_pages=favorites_pagination.pages,
        has_prev=favorites_pagination.has_prev,
        has_next=favorites_pagination.has_next,
        prev_num=favorites_pagination.prev_num,
        next_num=favorites_pagination.next_num,
        applied_job_ids=applied_job_ids,
        search_query=search_query  # Pass search query to template
    )

@user_blueprint.route('/remove_favorite/<uuid:job_id>', methods=['POST'])
@no_cache
@login_required
def remove_favorite(job_id):
    login_id = session.get('login_id')
    if not login_id:
        flash("User not logged in", "error")
        return redirect(url_for('auth.login'))
    
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('auth.login'))
    
    # Look for the favorite entry matching the user and job
    favorite = Favorite.query.filter_by(user_id=user.id, job_id=job_id).first()
    if not favorite:
        flash("Favorite not found", "error")
        return redirect(url_for('user.favorites'))
    
    db.session.delete(favorite)
    db.session.commit()
    
    flash("Job removed from favorites", "success")
    return redirect(url_for('user.favorites'))


#Notifications
@user_blueprint.route('/notifications', methods=['GET', 'POST'])
@no_cache
@login_required
def notifications():
    login_id = session.get('login_id')

    if not login_id or session.get('role') != 'user':
        flash("Unauthorized access. Please log in as a user.", "error")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        notification_id = request.form.get('notification_id')
        action = request.form.get('action')
        
        page = request.args.get('page', 1, type=int)
        current_filter = request.args.get('filter', 'all')

        if notification_id and action:
            notification = Communication.query.filter_by(
                id=notification_id, 
                user_id=login_id, 
                hidden=False
            ).first()

            if notification:
                if action == 'mark_read':
                    notification.read_status = True
                    db.session.commit()
                    flash("Notification marked as read.", "success")
                elif action == 'delete':
                    notification.hidden = True  # Soft-delete
                    db.session.commit()
                    flash("Notification removed.", "success")
            else:
                flash("Notification not found.", "danger")

        return redirect(request.referrer or url_for('user.notifications', page=page))
    
    user = User.query.filter_by(login_id=login_id).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('auth.login'))

    # Pagination setup
    page = request.args.get('page', 1, type=int)
    per_page = 5 

    current_filter = request.args.get('filter', 'all')
    
    search_query = request.args.get('search_query', '').strip()

    notifications_query = Communication.query.outerjoin(
        Company, Communication.company_id == Company.login_id
    ).filter(
        Communication.user_id == login_id, 
        Communication.hidden == False
    )
    
    if current_filter == 'unread':
        notifications_query = notifications_query.filter(Communication.read_status == False)
    elif current_filter == 'read':
        notifications_query = notifications_query.filter(Communication.read_status == True)
        
    if search_query:
        notifications_query = notifications_query.filter(
            or_(
                Communication.message.ilike(f'%{search_query}%'),
                Company.company_name.ilike(f'%{search_query}%')
            )
        )
    
    notifications_query = notifications_query.order_by(Communication.timestamp.desc())
    notifications_pagination = notifications_query.paginate(page=page, per_page=per_page, error_out=False)
    
    unread_count = Communication.query.filter_by(user_id=login_id, read_status=False, hidden=False).count()

    return render_template(
        '/user/notification.html',
        user=user,
        notifications=notifications_pagination.items,
        unread_count=unread_count,
        page=page,
        total_pages=notifications_pagination.pages,
        current_filter=current_filter,
        search_query=search_query
    )

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

# ============================================================================
# HELPER FUNCTIONS FOR USER MODULE
# ============================================================================
def sanitize_text(value: str) -> str:
    """ Sanitize text input to prevent XSS attacks. Removes script tags, javascript: URLs, data: URLs, and event handlers. """
    if not value:
        return ''
    # Remove <script>...</script>
    value = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', value, flags=re.IGNORECASE | re.DOTALL)
    # Remove javascript: or data: URLs inside attributes or text
    value = re.sub(r'javascript\s*:', '', value, flags=re.IGNORECASE)
    value = re.sub(r'data\s*:[^ \t\r\n]*', '', value, flags=re.IGNORECASE)
    # Remove on* event handlers
    value = re.sub(r'on\w+\s*=\s*"[^\"]*"', '', value, flags=re.IGNORECASE)
    value = re.sub(r'on\w+\s*=\s*\'[^\']*\'', '', value, flags=re.IGNORECASE)
    # Remove < and > characters
    value = value.replace('<', '').replace('>', '')
    return value.strip()


def is_valid_url(url: str) -> bool:
    """ Validate if a string is a properly formatted URL. """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def is_valid_email(email: str) -> bool:
    """ Validate email format using regex. """
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_regex, email) is not None


def count_words(text: str) -> int:
    """ Count words in a text string. """
    if not text:
        return 0
    return len(text.strip().split())


