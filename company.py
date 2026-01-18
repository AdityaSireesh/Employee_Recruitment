from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, make_response
from functools import wraps
import os
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db  # Ensure 'db' is the instance of SQLAlchemy, assuming your model is in 'models.py'
from config import Config
from utils import allowed_file  # Assuming your config file is named config.py
from models import Job, Company, Login, JobApplication, User, Communication, Notification, College, Certification, ResumeCertification
import re, uuid
from utils_url import url_seems_reachable


company_blueprint = Blueprint('company', __name__)

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


# Display the user dashboard
@company_blueprint.route('/company_dashboard')
@no_cache
@login_required
def company_dashboard():
    user_id = session.get('login_id')

    # Ensure the user_id is in session
    if not user_id or session.get('role') != 'company':
        flash("User is not logged in.", "error")
        return redirect(url_for('auth.login'))

    # Get the selected year from query parameters or use current year as default
    selected_year = request.args.get('year', datetime.now().year)
    try:
        selected_year = int(selected_year)
    except ValueError:
        selected_year = datetime.now().year
    
    # Query to fetch all jobs posted by the user
    jobs = Job.query.filter_by(created_by=user_id).all()
    profile = Company.query.filter_by(login_id=user_id).first()
    
    # Get all applications for jobs created by this company
    applications = db.session.query(JobApplication)\
        .join(Job, JobApplication.job_id == Job.job_id)\
        .filter(Job.created_by == user_id).all()
    
    # Get years with applications for the year selector
    application_years = db.session.query(
        db.func.extract('year', JobApplication.date_applied).label('year')
    ).join(Job, JobApplication.job_id == Job.job_id)\
        .filter(Job.created_by == user_id)\
        .group_by('year')\
        .order_by('year')\
        .all()
    
    available_years = [int(year.year) for year in application_years]
    
    # If no applications found, include current year
    if not available_years:
        available_years = [datetime.now().year]
    
    # If selected year is not in available years, use the most recent available year
    if selected_year not in available_years:
        selected_year = available_years[-1]
    
    # Calculate monthly application rates for the selected year
    monthly_application_rates = [0] * 12  # Initialize with 0 for all 12 months
    
    # Process monthly data
    for month in range(1, 13):
        # Total applications in this month of the selected year
        total_applications = db.session.query(db.func.count(JobApplication.id))\
            .join(Job, JobApplication.job_id == Job.job_id)\
            .filter(
                Job.created_by == user_id,
                db.func.extract('year', JobApplication.date_applied) == selected_year,
                db.func.extract('month', JobApplication.date_applied) == month
            ).scalar() or 0
        
        # Hired applications in this month of the selected year
        hired_applications = db.session.query(db.func.count(JobApplication.id))\
            .join(Job, JobApplication.job_id == Job.job_id)\
            .filter(
                Job.created_by == user_id,
                db.func.extract('year', JobApplication.date_applied) == selected_year,
                db.func.extract('month', JobApplication.date_applied) == month,
                JobApplication.status == 'Hired'
            ).scalar() or 0
        
        # Calculate the application rate (percentage) for this month
        if total_applications > 0:
            monthly_application_rates[month-1] = (hired_applications / total_applications) * 100
    
    # Calculate overall metrics
    total_applications_count = len(applications)
    total_successful = db.session.query(db.func.count(JobApplication.id))\
        .join(Job, JobApplication.job_id == Job.job_id)\
        .filter(Job.created_by == user_id, JobApplication.status == 'Hired')\
        .scalar() or 0
    
    total_unsuccessful = total_applications_count - total_successful
    
    # Calculate overall hiring rate
    overall_hiring_rate = 0
    if total_applications_count > 0:
        overall_hiring_rate = round((total_successful / total_applications_count) * 100, 1)
    
    return render_template('/company/dashboard.html', 
        jobs=jobs, 
        profile=profile,
        monthly_application_rates=monthly_application_rates,
        total_successful=total_successful, 
        total_unsuccessful=total_unsuccessful,
        overall_hiring_rate=overall_hiring_rate,
        available_years=available_years,
        selected_year=selected_year)

# Job Posting
@company_blueprint.route('/company_jobposting')
@no_cache
@login_required
def company_jobposting():
    from app import db
    user_id = session.get('login_id')
    
    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only companies can access
    
    # Retrieve all jobs ordered by most recent
    jobs = Job.query.filter_by(created_by=user_id).order_by(Job.created_at.desc()).all()
    profile = Company.query.filter_by(login_id=user_id).first()

    return render_template('/company/job_posting.html', jobs=jobs, profile=profile,)

# Post New Job
@company_blueprint.route('/company_post_new_job', methods=['GET', 'POST'])
@no_cache
@login_required
def company_post_new_job():
    from app import db
    from datetime import datetime, date

    user_id = session.get('login_id')

    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only companies can access

    message = None
    message_type = None
    form_data = {}  # Initialize form_data dictionary
    form_url = ''
    
    # Check if we're editing an existing job
    job = None
    job_id = request.args.get('job_id')

    if request.method == 'POST':
        # Get form data
        job_id = request.form.get('jobId')

        if job_id:
            job_to_check = Job.query.get(job_id)
            if job_to_check and job_to_check.status == 'closed':
                flash("This job is closed and cannot be edited.", "error")
                return redirect(url_for('company.company_jobposting'))

        raw_title = request.form.get('job-title', '').strip()
        raw_description = request.form.get('description', '').strip()
        raw_skills = request.form.get('skill-sets', '').strip()
        exp_str = request.form.get('exp', '').strip()
        raw_certifications = request.form.get('certifications', '').strip()
        job_type = request.form.get('job-type', '').strip()
        raw_locations = request.form.get('locations', '').strip()
        raw_salary = request.form.get('salary', '').strip()
        vacancy_str = request.form.get('vacancy', '').strip()
        form_url = request.form.get('form-url', '').strip()
        deadline_str = request.form.get('deadline', '').strip()

        title = sanitize_text(raw_title)
        description = sanitize_text(raw_description)
        skills = sanitize_text(raw_skills)
        certifications = sanitize_text(raw_certifications)
        locations = sanitize_text(raw_locations)
        salary_str = sanitize_text(raw_salary)

        created_by = session['login_id']

        # Store form data to preserve it in case of validation errors
        form_data = {
            'title': title,
            'description': description,
            'skills': skills,
            'exp': exp_str,
            'certifications': certifications,
            'job_type': job_type,
            'locations': locations,
            'salary': salary_str,
            'vacancy': vacancy_str,
            'form_url': form_url,
            'deadline': deadline_str
        }

        # Check for duplicate job title on the same day (only for new jobs, not edits)
        if not job_id:
            today = date.today()
            existing_job = Job.query.filter(
                Job.created_by == user_id,
                Job.title.ilike(title),  # Case-insensitive comparison
                db.func.date(Job.created_at) == today
            ).first()
            
            if existing_job:
                message = f"A job with the title '{title}' has already been posted today. Please use a different title or wait until tomorrow."
                message_type = "error"
            
        # Continue with existing validations only if no duplicate found
        if not message:
            dangerous_fields = [title, description, skills, certifications, locations, salary_str]
            if any(
                re.search(r'<\s*script[\s\S]*?>[\s\S]*?<\s*/\s*script\s*>', f, re.IGNORECASE) or
                re.search(r'(javascript\s*:|data\s*:)', f, re.IGNORECASE)
                for f in dangerous_fields if f
            ):
                message = "Dangerous content is not allowed in text fields."
                message_type = "error"
            # Validate inputs
            if not message:
                if not (3 <= len(title) <= 250):
                    message = "Job Title must be between 3-250 characters!"
                    message_type = "error"
                elif not (10 <= len(description) <= 2000):
                    message = "Job Description must be between 10-2000 characters!"
                    message_type = "error"
                elif len(skills) > 1000:
                    message = "Skills must not exceed 1000 characters!"
                    message_type = "error"
                elif not exp_str or not exp_str.isdigit():
                    message = "Years of Experience must be a valid number!"
                    message_type = "error"
                elif len(certifications) > 1000:
                    message = "Certifications must not exceed 1000 characters!"
                    message_type = "error"
                elif len(salary_str) > 50:
                    message = "Salary must not exceed 50 characters!"
                    message_type = "error"
                elif len(locations) > 1000:
                    message = "Locations must not exceed 1000 characters!"
                    message_type = "error"
                elif not vacancy_str or not vacancy_str.isdigit():
                    message = "Vacancy must be a valid number!"
                    message_type = "error"
                elif not deadline_str:
                    message = "Application deadline is required!"
                    message_type = "error"
                elif form_url:
                    # ---- Questionnaire URL rules (mirror profile website/logo) ----
                    # 1) Single URL only (no whitespace)
                    if re.search(r"\s", form_url):
                        message = "Please enter only one questionnaire form URL."
                        message_type = "error"

                    # 2) Must start with http/https
                    elif not re.match(r"^https?", form_url, re.IGNORECASE):
                        message = "Questionnaire URL must start with http or https."
                        message_type = "error"

                    # 3) Block dangerous schemes
                    elif re.match(r"^(javascript|data)", form_url, re.IGNORECASE):
                        message = "Questionnaire URL scheme is not allowed."
                        message_type = "error"

                    # 4) Optional ping check (same as profile)
                    elif form_url and not url_seems_reachable(form_url):
                        message = "Questionnaire URL could not be reached. Please check the link."
                        message_type = "error"
                # elif form_url and not is_valid_url(form_url):
                #     message = "Please enter a valid URL for the questionnaire form!"
                #     message_type = "error"

            if not message:
                try:
                    # Convert string values to appropriate types
                    exp = int(exp_str)
                    total_vacancy = int(vacancy_str)
                    # salary = int(salary_str) if salary_str else None
                    salary = salary_str
                    
                    # Additional validations
                    if exp < 0 or exp > 50:
                        message = "Years of Experience must be between 0-50!"
                        message_type = "error"
                    elif total_vacancy < 1 or total_vacancy > 1000:
                        message = "Vacancy must be between 1-1000!"
                        message_type = "error"
                    else:
                        # Convert the deadline string to a Python date object
                        try:
                            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date()
                            current_date = date.today()
                            
                            if deadline < current_date:
                                message = "Deadline cannot be in the past!"
                                message_type = "error"
                            else:
                                filled_vacancy = 0
                                status = "open" if total_vacancy > filled_vacancy else "closed"
                                
                                if job_id:  # Update the job
                                    job = Job.query.get(job_id)
                                    if job and job.created_by == user_id:  # Security check
                                        # Save current filled_vacancy
                                        filled_vacancy = job.filled_vacancy
                                        
                                        job.title = title
                                        job.description = description
                                        job.job_type = job_type
                                        job.skills = skills
                                        job.years_of_exp = exp
                                        job.certifications = certifications
                                        job.location = locations
                                        job.salary = salary
                                        job.total_vacancy = total_vacancy
                                        job.deadline = deadline
                                        job.form_url = form_url
                                        
                                        # Update status based on vacancies
                                        job.status = "open" if total_vacancy > filled_vacancy else "closed"
                                        
                                        db.session.commit()
                                        message = "Job updated successfully!"
                                        message_type = "success"
                                    else:
                                        message = "Job not found or you don't have permission to edit it."
                                        message_type = "error"
                                else:  # Add a new job
                                    new_job = Job(
                                        title=title,
                                        description=description,
                                        job_type=job_type,
                                        skills=skills,
                                        years_of_exp=exp,
                                        certifications=certifications,
                                        location=locations,
                                        salary=salary,
                                        total_vacancy=total_vacancy,
                                        filled_vacancy=filled_vacancy,
                                        status=status,
                                        form_url=form_url,
                                        deadline=deadline,
                                        created_by=created_by
                                    )
                                    db.session.add(new_job)
                                    db.session.commit()
                                    message = "Job added successfully!"
                                    message_type = "success"
                                
                                if message_type == "success":
                                    return redirect(url_for('company.company_jobposting'))
                        except ValueError:
                            message = "Invalid date format for the deadline. Please use YYYY-MM-DD."
                            message_type = "error"
                except ValueError:
                    message = "Please ensure all numeric fields contain valid numbers!"
                    message_type = "error"
    else:  # GET request
        if job_id:
            job = Job.query.get(job_id)
            if job and job.created_by == user_id:  # Security check
                # Prefill form_data from existing job
                form_data = {
                    'title': job.title,
                    'description': job.description,
                    'skills': job.skills,
                    'exp': job.years_of_exp,
                    'certifications': job.certifications,
                    'job_type': job.job_type,
                    'locations': job.location,
                    'salary': job.salary if job.salary else '',
                    'vacancy': job.total_vacancy,
                    'form_url': job.form_url if job.form_url else '',
                    'deadline': job.deadline.strftime('%Y-%m-%d') if job.deadline else ''
                }
            else:
                return redirect(url_for('company.company_jobposting'))

    # Get jobs and application statistics
    jobs = Job.query.filter_by(created_by=user_id).all()

    # Calculate statistics for the dashboard/sidebar
    total_successful = db.session.query(db.func.count(JobApplication.id)).filter(
        JobApplication.job_id.in_([j.job_id for j in jobs]) if jobs else False, 
        JobApplication.status == 'Hired'
    ).scalar() or 0

    total_unsuccessful = db.session.query(db.func.count(JobApplication.id)).filter(
        JobApplication.job_id.in_([j.job_id for j in jobs]) if jobs else False, 
        JobApplication.status == 'Rejected'
    ).scalar() or 0

    # Get today's date in 'YYYY-MM-DD' format
    current_date = date.today().strftime('%Y-%m-%d')
    profile = Company.query.filter_by(login_id=user_id).first()
    
    # Check if job is closed for template rendering
    is_closed = False
    if job_id:
        job_to_check = Job.query.get(job_id)
        if job_to_check and job_to_check.status == 'closed':
            is_closed = True
    
    return render_template('/company/post_new_job.html', 
                           current_date=current_date, 
                           profile=profile,
                           job_id=job_id,
                           form_data=form_data,  # Pass form data for populating fields
                           is_closed=is_closed,
                           total_successful=total_successful, 
                           total_unsuccessful=total_unsuccessful,
                           message=message,
                           message_type=message_type)

# Helper function to validate URLs
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

# Application Review
@company_blueprint.route('/company_application_review', methods=['GET', 'POST'])
@no_cache
@login_required
def company_application_review():
    user_id = session.get('login_id')
    
    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only company can access
    
    if request.method == 'POST':
        # Handle the status update
        application_id = request.form.get('application_id')
        new_status = request.form.get('status')
 
        application = JobApplication.query.get(application_id)

        if application:
            previous_status = application.status

            if new_status != 'Hired' and previous_status == 'Hired':
                job = application.job
                if job.filled_vacancy > 0:
                    job.filled_vacancy -= 1
                    job.status = 'open'
                db.session.commit()

            application.status = new_status
            db.session.commit()
            flash('Application status updated successfully!', 'success')

            # If the application is hired, increment the filled_vacancy in Job table
            if new_status == 'Hired' and previous_status != 'Hired':
                job = application.job  # Get the related job
                if job.filled_vacancy < job.total_vacancy: # Ensure filled_vacancy does not exceed total_vacancy
                    job.filled_vacancy += 1
                    db.session.commit()
                if job.filled_vacancy == job.total_vacancy:
                    job.status = 'closed'
                    db.session.commit()
        else:
            flash('Application not found!', 'danger')

    # Get filter parameters from request
    # For the filter dropdown
    selected_status = request.args.getlist('status')  # Get selected status filters
    selected_jobs = request.args.getlist('job_post')  # Get selected job filters
    
    # For the search functionality
    search_query = request.args.get('search_query', '').strip()

    # Get all jobs created by the company
    jobs = Job.query.filter_by(created_by=user_id).all()
    
    # Query all job applications for the company's jobs
    query = JobApplication.query.join(Job).filter(Job.created_by == user_id)

    # Apply filters based on dropdown selections
    if selected_status:
        query = query.filter(JobApplication.status.in_(selected_status))
    if selected_jobs:
        query = query.filter(Job.title.in_(selected_jobs))

    # Apply search filter - search across candidate name, job title, and status
    if search_query:
        query = query.join(User).filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                Job.title.ilike(f'%{search_query}%'),
                JobApplication.status.ilike(f'%{search_query}%')
            )
        )

    # Get all filtered job applications
    job_applications = query.all()
    
    # Create a list of applications with details for rendering
    applications_data = []
    for application in job_applications:
        # Fetch the latest resume for this user from ResumeCertification
        resume = ResumeCertification.query.filter_by(user_id=application.user_id).order_by(ResumeCertification.id.desc()).first()
        resume_path = resume.resume_path if resume else None
        
        applications_data.append({
            'candidate_name': application.user.name,
            'job_post': application.job.title,
            'status': application.status,
            'application_id': application.id,
            'resume_path': resume_path,
            'user_id': str(application.user_id),  # Convert UUID to string
            'is_banned': application.user.is_banned
        })
    
    # Fetch certifications for each candidate
    user_certifications = {}
    user_ids = [app['user_id'] for app in applications_data]
    
    # Using a single query to get all certifications for all relevant users
    all_certifications = Certification.query.filter(Certification.user_id.in_([uuid.UUID(uid) for uid in user_ids])).all()
    
    # Organize certifications by user_id
    for cert in all_certifications:
        user_id_str = str(cert.user_id)  # Convert UUID to string
        if user_id_str not in user_certifications:
            user_certifications[user_id_str] = []
        
        user_certifications[user_id_str].append({
            'certification_name': cert.certification_name,
            'verified': cert.verification_status
        })

    profile = Company.query.filter_by(login_id=user_id).first()
    
    return render_template(
        '/company/application_review.html',
        applications=applications_data,
        profile=profile,
        selected_status=selected_status,
        jobs=jobs,
        selected_jobs=selected_jobs,
        user_certifications=user_certifications
    )

# Hiring Communication
from flask_mail import Message
from flask import current_app
@company_blueprint.route('/company_hiring_communication', methods=['GET', 'POST'])
@no_cache
@login_required
def company_hiring_communication():
    mail = current_app.extensions['mail']
    user_id = session.get('login_id')
    
    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only company can access

    # For the filter dropdown
    selected_status = request.args.getlist('status')  # Get selected status filters
    selected_jobs = request.args.getlist('job_post')  # Get selected job filters
    
    # For the search functionality
    search_query = request.args.get('search_query', '').strip()

    # Get all jobs created by the company
    jobs = Job.query.filter_by(created_by=user_id).all()

    # Fetch all users who applied for the company's jobs
    applied_users = (
        db.session.query(
            User.id, 
            User.name,
            User.login_id,
            User.is_banned,
            Job.title.label('job_title'), 
            JobApplication.status
        )
        .join(JobApplication, JobApplication.user_id == User.id)
        .join(Job, JobApplication.job_id == Job.job_id)
        .filter(Job.created_by == user_id)
        .order_by(User.id, JobApplication.id.desc())
        .all()
    )
    
    if selected_status or selected_jobs or search_query:
        filtered_query = (
            db.session.query(User.id, User.name, User.login_id, User.is_banned, Job.title.label('job_title'), JobApplication.status)
            .join(JobApplication, JobApplication.user_id == User.id)
            .join(Job, JobApplication.job_id == Job.job_id)
            .filter(Job.created_by == user_id)
        )
        
        if selected_status:
            filtered_query = filtered_query.filter(JobApplication.status.in_(selected_status))
        if selected_jobs:
            filtered_query = filtered_query.filter(Job.title.in_(selected_jobs))
        if search_query:
            filtered_query = filtered_query.filter(
                or_(
                    User.name.ilike(f'%{search_query}%'),
                    Job.title.ilike(f'%{search_query}%'),
                    JobApplication.status.ilike(f'%{search_query}%')
                )
            )

        applied_users = filtered_query.all()

    # Fetch communication history with structured data for JavaScript
    messages_query = (
        db.session.query(
            Communication, 
            db.case(
                (Communication.user_id.isnot(None), User.name),
                else_=College.college_name
            ).label("recipient_name"),
            db.case(
                (Communication.user_id.isnot(None), 'candidate'),
                else_='college'
            ).label("recipient_type"),
            db.case(
                (Communication.user_id.isnot(None), Communication.user_id),  # Change from User.login_id
                else_=Communication.college_id  # Change from College.login_id
            ).label("recipient_id")
        )
        .outerjoin(User, Communication.user_id == User.login_id)
        .outerjoin(College, Communication.college_id == College.login_id)
        .filter(Communication.company_id == user_id)
        .order_by(Communication.timestamp.desc())
    )
    
    messages = messages_query.all()

    colleges = College.query.all()

    # Message sending logic
    if request.method == 'POST':
        # Get data from form
        message_content = request.form.get('message')
        recipient_type = request.form.get('recipient_type')
        recipient_id = request.form.get('recipient_id')
        
        # Determine which ID to use based on recipient type
        if recipient_type == 'candidate':
            selected_user_id = recipient_id  # This is already the login_id
            selected_college_id = None
            
            # Get email directly using login_id
            recipient_email = db.session.query(User.email).filter_by(login_id=selected_user_id).scalar()
            new_user_id = selected_user_id  # Use login_id directly
            new_college_id = None
        else:
            selected_college_id = recipient_id
            selected_user_id = None
            
            # Get college email using login_id
            recipient_email = db.session.query(College.email).filter_by(login_id=selected_college_id).scalar()
            new_college_id = selected_college_id
            new_user_id = None
        
            
        sender_email = db.session.query(Company.email).filter_by(login_id=user_id).scalar()

        # Add message to the database
        if message_content:
            new_message = Communication(company_id=user_id, user_id=new_user_id, college_id=new_college_id, message=message_content)
            db.session.add(new_message)
            db.session.commit()

            # Send email notification
            try:
                subject = "New Message from Company"
                body = f"Dear Recipient,\n\nYou have received a new message from {sender_email}:\n\n{message_content}\n\nBest regards,\nYour Job Portal"
                msg = Message(subject=subject, recipients=[recipient_email])
                msg.body = body
                mail.send(msg)
            except Exception as e:
                print(f"Failed to send email: {e}")

            flash('Message sent successfully!', 'success')

        return redirect(url_for('company.company_hiring_communication'))
    
    message_history = {"candidates": {}}
    for msg, recipient_name, recipient_type, recipient_id in messages:
        if recipient_type == 'candidate':
            recipient_id_str = str(recipient_id)  # Convert UUID to string
            if recipient_id_str not in message_history["candidates"]:
                message_history["candidates"][recipient_id_str] = []
            
            # Format the message with necessary details
            message_entry = {
                "name": "Company" if msg.company_id == user_id else recipient_name,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat()
            }
            message_history["candidates"][recipient_id_str].append(message_entry)


    profile = Company.query.filter_by(login_id=user_id).first()

    return render_template('/company/hiring_message.html', 
        applied_users=applied_users, 
        messages=messages, 
        profile=profile, 
        colleges=colleges,
        jobs=jobs,
        selected_status=selected_status,
        selected_jobs=selected_jobs,
        message_history=message_history
    )

# Notifications
@company_blueprint.route('/company_notification', methods=['GET', 'POST'])
@no_cache
@login_required
def company_notification():
    user_id = session.get('login_id')

    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only companies can access

    if request.method == 'POST':
        notification_id = request.form.get('notification_id')
        action = request.form.get('action')

        if notification_id and action:
            notification = Notification.query.filter_by(id=notification_id, company_id=user_id).first()
            if notification:
                if action == 'mark_read':
                    notification.read_status = True
                    db.session.commit()
                    flash('Notification marked as read.', 'success')
                elif action == 'delete':
                    notification.hidden = True  # Soft delete
                    db.session.commit()
                    flash('Notification hidden successfully.', 'success')
        # Redirect back to the same page to show the changes
        page = request.args.get('page', 1, type=int)
        return redirect(url_for('company.company_notification', page=page))

    # Get the page number from the URL, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 2  # Number of notifications per page
    # Fetch a paginated list of notifications for the company
    notifications_pagination = Notification.query.filter_by(company_id=user_id, hidden=False)\
                                    .order_by(Notification.timestamp.desc())\
                                    .paginate(page=page, per_page=per_page, error_out=False)
    

    # Fetch the company profile to display in the form
    companies = Company.query.filter_by(login_id=user_id).first()
    profile = Company.query.filter_by(login_id=user_id).first()

    return render_template('/company/notification.html', 
        notifications=notifications_pagination, 
        profile=profile,
    )

# Profile
@company_blueprint.route('/company_profile', methods=['GET', 'POST'])
@no_cache
@login_required
def company_profile():
    user_id = session.get('login_id')

    if 'login_id' not in session or session.get('role') != 'company':
        return redirect(url_for('auth.login'))  # Ensure only companies can access

    companies = Company.query.filter_by(login_id=user_id).first()

    message = None
    message_type = None

    if request.method == 'POST' and companies:
        # Get form data
        company_id = request.form.get('logId')  # Hidden input for company ID
        raw_company_name = request.form['company-name']
        raw_email = request.form['contact-email']
        raw_description = request.form.get('company-description', '')
        raw_address = request.form.get('company-address', '')
        raw_website = request.form.get('company-website', '')
        raw_logo = request.form.get('company-logo', '')
        raw_industry = request.form['industries']

        # Normalised values used for comparison & storage
        company_name = sanitize_text(raw_company_name.strip())
        email = raw_email.strip()
        description = sanitize_text(raw_description.strip())
        address = sanitize_text(raw_address.strip())
        website = raw_website.strip()
        logo = raw_logo.strip()
        industry = raw_industry.strip() if raw_industry else ''

        # Check if any change is made
        if (
            company_name == companies.company_name and
            email == companies.email and
            description == companies.description and
            address == companies.address and
            website == companies.website and
            logo == companies.logo and
            industry == companies.industry
        ):
            # return redirect(url_for('company.company_profile'))  # No changes, just reload page silently
            message = "No changes detected."
            message_type = "info"
        else:
        # Validate Data
            if len(company_name) < 3 or len(company_name) > 100:
                message = "Company Name must be between 3-100 characters!"
                message_type = "error"
            elif not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
                message = "Invalid email format!"
                message_type = "error"

            elif len(description) > 1000:
                message = "Description must be under 1000 characters!"
                message_type = "error"

            elif len(address) > 500:
                message = "Address must be under 500 characters!"
                message_type = "error"

            elif website:
                # Disallow any whitespace → prevents entering multiple URLs
                if re.search(r"\s", website):
                    message = "Please enter only one website URL."
                    message_type = "error"
                # Reject dangerous schemes
                elif not re.match(r"^https?://", website, re.IGNORECASE):
                    message = "Website URL must start with http:// or https://."
                    message_type = "error"
                elif re.match(r"^(javascript:|data:)", website, re.IGNORECASE):
                    message = "Website URL scheme is not allowed."
                    message_type = "error"
                elif website and not url_seems_reachable(website):
                    message = "Website URL could not be reached. Please check the link."
                    message_type = "error"

            if not message and logo:
                if re.search(r"\s", logo):
                    message = "Please enter only one logo URL."
                    message_type = "error"
                elif not re.match(r"^https?://", logo, re.IGNORECASE):
                    message = "Logo URL must start with http:// or https://."
                    message_type = "error"
                elif re.match(r"^(javascript:|data:)", logo, re.IGNORECASE): # Can remove data check to allow data URLs for logos ->r"^(javascript:)"
                    message = "Logo URL scheme is not allowed."
                    message_type = "error"
                elif logo and not url_seems_reachable(logo):
                    message = "Logo URL could not be reached. Please check the link."
                    message_type = "error"
                else:
                    # Basic host + TLD check (rejects http://test, allows http://test.com)
                    if not re.match(
                        r"^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/.*)?$",
                        logo,
                        re.IGNORECASE,
                    ):
                        message = "Logo URL must contain a valid domain (e.g., http://example.com)."
                        message_type = "error"

                    elif re.search(r"\.(html|htm|php|asp|jsp)(\?.*)?$", logo, re.IGNORECASE):
                        message = "The URL looks like a webpage. Please provide an image address."
                        message_type = "error"
            
            if not message:
                companies.company_name = company_name
                companies.description = description
                companies.email = email
                companies.address = address
                companies.website = website
                companies.logo = logo
                companies.industry = industry
                db.session.commit()
                message = "Profile updated successfully!"
                message_type = "success"

    pending_applications_count = db.session.query(db.func.count(JobApplication.id)) \
        .join(Job, JobApplication.job_id == Job.job_id) \
        .filter(Job.created_by == user_id, JobApplication.status == 'Pending') \
        .scalar()
    interviewed_applications_count = db.session.query(db.func.count(JobApplication.id)) \
        .join(Job, JobApplication.job_id == Job.job_id) \
        .filter(Job.created_by == user_id, JobApplication.status == 'Interviewed') \
        .scalar()

    jobs = Job.query.filter_by(created_by=user_id).all()

    applications = db.session.query(
        Job.title,
        db.func.count(JobApplication.id).label('total_applications'),
        db.func.sum(db.case(
            (JobApplication.status == 'Hired', 1),
            else_=0
        )).label('shortlisted_applications')
    ).join(JobApplication, Job.job_id == JobApplication.job_id).filter(Job.created_by == user_id).group_by(Job.title).all()

    total_successful = sum(app.shortlisted_applications for app in applications)
    total_unsuccessful = sum(app.total_applications - app.shortlisted_applications for app in applications)

    industries = [
        "Agriculture, Forestry, and Fishing",
        "Mining and Quarrying",
        "Manufacturing",
        "Electricity, Gas, Steam, and Air Conditioning Supply",
        "Water Supply; Sewerage, Waste Management, and Remediation Activities",
        "Construction",
        "Wholesale and Retail Trade; Repair of Motor Vehicles and Motorcycles",
        "Transportation and Storage",
        "Accommodation and Food Service Activities",
        "Information and Communication",
        "Financial and Insurance Activities",
        "Real Estate Activities",
        "Professional, Scientific, and Technical Activities",
        "Administrative and Support Service Activities",
        "Public Administration and Defence; Compulsory Social Security",
        "Education",
        "Human Health and Social Work Activities",
        "Arts, Entertainment, and Recreation",
        "Other Service Activities",
        "Activities of Households as Employers",
        "Activities of Extraterritorial Organizations and Bodies"
    ]

    return render_template(
        'company/profile.html',
        companies=companies,
        profile=companies,
        loginid=user_id,
        pending_applications_count=pending_applications_count,
        total_successful=total_successful,
        total_unsuccessful=total_unsuccessful,
        interviewed_applications_count=interviewed_applications_count,
        industries=industries,
        message=message,
        message_type=message_type,
    )

def sanitize_text(value: str) -> str:
    if not value:
        return ''
    # Remove <script>...</script>
    value = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', value,
                   flags=re.IGNORECASE | re.DOTALL)
    # Remove javascript: or data: URLs inside attributes or text
    value = re.sub(r'javascript\s*:', '', value, flags=re.IGNORECASE)
    value = re.sub(r'data\s*:[^ \t\r\n]*', '', value, flags=re.IGNORECASE)
    # Remove on* event handlers
    value = re.sub(r'on\w+\s*=\s*"[^\"]*"', '', value, flags=re.IGNORECASE)
    value = re.sub(r'on\w+\s*=\s*\'[^\']*\'', '', value, flags=re.IGNORECASE)
    value = value.replace('<', '').replace('>', '')
    return value.strip()