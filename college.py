from datetime import datetime, date
import random
import re
import string
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, make_response, current_app
from functools import wraps
import os, uuid
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from models import Certification, Company, Coupon, Couponuser, Job
from models import College, Login, JobApplication, ResumeCertification, User, db  # Ensure 'db' is the instance of SQLAlchemy
from config import Config
from utils import allowed_file  # Assuming your config file is named config.py
from sqlalchemy.sql import func
from sqlalchemy import distinct
from auth import secure_route
from utils_url import url_seems_reachable
from sqlalchemy import or_

college_blueprint = Blueprint('college', __name__)

# Display the user dashboard
@college_blueprint.route('/college_dashboard')
@secure_route
def college_dashboard():
    college_id = session.get('login_id')
    
    # Ensure the user is logged in as a college
    if not college_id or session.get('role') != 'college':
        flash("College is not logged in.", "error")
        return redirect(url_for('auth.login'))
    
    # Get college profile
    college_profile = College.query.filter_by(login_id=college_id).first()
    
    # Get the selected year from query parameters or use current year as default
    selected_year = request.args.get('year', datetime.now().year)
    try:
        selected_year = int(selected_year)
    except ValueError:
        selected_year = datetime.now().year
    
    # Get years with user registrations (coupon usage) for the year selector
    registration_years = db.session.query(
        db.func.extract('year', Couponuser.created_at).label('year')
    ).join(Coupon, Couponuser.coupon_id == Coupon.id)\
      .filter(
          Coupon.college_id == college_profile.id,
          Couponuser.created_at.isnot(None)
      )\
      .group_by(db.func.extract('year', Couponuser.created_at))\
      .order_by(db.func.extract('year', Couponuser.created_at))\
      .all()
    
    available_years = [int(year.year) for year in registration_years if year.year is not None]
    
    # If no registrations found, include current year
    if not available_years:
        available_years = [datetime.now().year]
    
    # If selected year is not in available years, use the most recent available year
    if selected_year not in available_years:
        selected_year = available_years[-1]
    
    # Get users from this college (only distinct users)
    college_users = db.session.query(User.id).join(
        Couponuser, User.id == Couponuser.user_id
    ).join(
        Coupon, Couponuser.coupon_id == Coupon.id
    ).filter(
        Coupon.college_id == college_profile.id
    ).distinct().subquery()
    
    # 1. Count total distinct registered students
    registered_students_count = db.session.query(db.func.count()).select_from(college_users).scalar() or 0
    
    # 2. Count total applications submitted by students from this college
    total_applications = db.session.query(JobApplication)\
        .filter(JobApplication.user_id.in_(db.session.query(college_users.c.id)))\
        .count()
    
    # 3. Calculate monthly distinct student registrations for the selected year
    monthly_registrations = [0] * 12  # Initialize with 0 for all 12 months
    
    for month in range(1, 13):
        # Get distinct students who registered in this month of the selected year
        monthly_distinct_students = db.session.query(db.func.count(db.func.distinct(Couponuser.user_id)))\
            .join(Coupon, Couponuser.coupon_id == Coupon.id)\
            .filter(
                Coupon.college_id == college_profile.id,
                db.func.extract('year', Couponuser.created_at) == selected_year,
                db.func.extract('month', Couponuser.created_at) == month
            ).scalar() or 0
        
        monthly_registrations[month-1] = monthly_distinct_students
    
    # 4. Create data for hired students graph, counting each student only in their most recent hiring year
    # First, create a subquery to get the most recent hiring year for each student
    student_latest_hire = db.session.query(
        JobApplication.user_id,
        db.func.max(db.func.extract('year', JobApplication.status_updated_at)).label('latest_year')
    ).filter(
        JobApplication.user_id.in_(db.session.query(college_users.c.id)),
        JobApplication.status == 'Hired',
        JobApplication.status_updated_at.isnot(None)
    ).group_by(JobApplication.user_id).subquery()
    
    # Get min and max years from the latest hire years
    min_max_years = db.session.query(
        db.func.min(student_latest_hire.c.latest_year),
        db.func.max(student_latest_hire.c.latest_year)
    ).first()
    
    current_year = datetime.now().year
    db_min_year = int(min_max_years[0]) if min_max_years[0] else current_year
    db_max_year = int(min_max_years[1]) if min_max_years[1] else current_year
    
    max_year = max(db_max_year + 2, current_year)
    min_year = min(db_min_year - 2, max_year)
    
    # Create data for each year
    years_list = list(range(min_year, max_year + 1))

    yearly_hired_students = []
    
    for year in years_list:
        # Count students whose latest hiring was in this year
        hired_count = db.session.query(db.func.count())\
            .select_from(student_latest_hire)\
            .filter(student_latest_hire.c.latest_year == year)\
            .scalar() or 0
        
        yearly_hired_students.append({
            'year': year,
            'count': hired_count
        })
    
    return render_template('/college/dashboard.html', 
        registered_students_count=registered_students_count,
        monthly_registrations=monthly_registrations,
        yearly_hired_students=yearly_hired_students,
        total_applications=total_applications,
        years_list=years_list,
        available_years=available_years,
        selected_year=selected_year,
        college_profile=college_profile)

EMAIL_REGEX = re.compile(r"^(?!.*\.\.)(?!.*\.$)[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

URL_REGEX = re.compile(r"^(https?:\/\/)([A-Za-z0-9-]+\.)+[A-Za-z]{2,}(\/\S*)?$")

def contains_script(text):
    return "<script" in text.lower() or "javascript:" in text.lower() or "data:" in text.lower()

import re

# ----------------- SAME AS COMPANY PROFILE -----------------
def sanitize_text(value: str) -> str:
    if not value:
        return ''
    value = re.sub(r'<\s*script[^>]*>.*?<\s*/\s*script\s*>', '', value,
                   flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r'javascript\s*:', '', value, flags=re.IGNORECASE)
    value = re.sub(r'data\s*:[^ \t\r\n]*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'on\w+\s*=\s*"[^"]*"', '', value, flags=re.IGNORECASE)
    value = re.sub(r'on\w+\s*=\s*\'[^\']*\'', '', value, flags=re.IGNORECASE)
    value = value.replace('<', '').replace('>', '')
    return value.strip()

@college_blueprint.route('/college_profile', methods=['GET', 'POST'])
@secure_route
def college_profile():
    user_id = session.get('login_id')

    if 'login_id' not in session or session.get('role') != 'college':
        return redirect(url_for('auth.login'))

    colleges = College.query.filter_by(login_id=user_id).first()

    message = None
    message_type = None

    if request.method == 'POST' and colleges:

        # SANITIZE FIRST
        raw_college_name = request.form['college-name']
        raw_email = request.form['contact-email']
        raw_description = request.form['college-description']
        raw_address = request.form['college-address']
        raw_website = request.form['college-website']
        
        college_name = sanitize_text(raw_college_name.strip())
        email = raw_email.strip()
        description = sanitize_text(raw_description.strip())
        address = sanitize_text(raw_address.strip())
        website = raw_website.strip()
        
        # ------------------------- NO CHANGE -------------------------
        if (
            college_name == colleges.college_name and
            email == colleges.email and
            description == colleges.description and
            address == colleges.address and
            website == colleges.website
        ):
            message = "No changes detected."
            message_type = "info"

        # ------------------------- VALIDATION -------------------------

        # 1) Name
        if not (3 <= len(college_name) <= 100):
            message = "College Name must be between 3–100 characters!"
            message_type = "error"

        elif contains_script(raw_college_name):
            message = "College Name contains unsafe characters!"
            message_type = "error"

        # 2) Email
        elif not EMAIL_REGEX.match(email):
            message = "Invalid email format!"
            message_type = "error"

        elif contains_script(raw_email):
            message = "Email contains unsafe characters!"
            message_type = "error"

        # 3) Website
        elif website:
            if contains_script(website):
                message = "Website contains unsafe content!"
                message_type = "error"

            elif re.search(r"\s", website):
                message = "Please enter only one website URL."
                message_type = "error"

            elif not re.match(r"^https?", website, re.IGNORECASE):
                message = "Website URL must start with http or https."
                message_type = "error"

            elif re.match(r"^(javascript|data)", website, re.IGNORECASE):
                message = "Website URL scheme is not allowed."
                message_type = "error"

            elif website and not url_seems_reachable(website):
                message = "Website URL could not be reached. Please check the link."
                message_type = "error"

        # 4) Description
        elif len(description) > 1000:
            message = "Description must be under 1000 characters!"
            message_type = "error"

        elif contains_script(raw_description):
            message = "Description contains unsafe content!"
            message_type = "error"

        # 5) Address
        elif len(address) > 500:
            message = "Address must be under 500 characters!"
            message_type = "error"

        elif contains_script(raw_address):
            message = "Address contains unsafe content!"
            message_type = "error"

        # ------------------------- SAVE -------------------------
        if not message:
            old_name = colleges.college_name
            name_changed = (old_name != college_name)

            colleges.college_name = college_name
            colleges.description = description
            colleges.email = email
            colleges.address = address
            colleges.website = website

            if name_changed:
                try:
                    User.query.filter(User.college_name == old_name).update(
                        {User.college_name: college_name}, 
                        synchronize_session=False
                    )
                except Exception as e:
                    db.session.rollback()
                    print(f"Error updating linked users: {e}")
                    message = "Profile updated, but failed to update student records."
                    message_type = "warning"

            if not message or message_type != "warning":
                db.session.commit()
                message = "Profile updated successfully!"
                message_type = "success"

    student_count = db.session.query(db.func.count(User.id)) \
        .filter(User.college_name == colleges.college_name if colleges else '') \
        .scalar()

    coupon_count = db.session.query(db.func.count(Coupon.id)) \
        .filter(Coupon.college_id == colleges.id if colleges else 0) \
        .scalar()

    # print("DEBUG college_profile:", "msg=", message, "type=", message_type, "method=", request.method)

    return render_template(
        '/college/profile.html',
        colleges=colleges,
        profile=colleges,
        login_id=user_id,
        student_count=student_count,
        coupon_count=coupon_count,
        message=message,
        message_type=message_type
    )

from flask import current_app
import os, uuid

@college_blueprint.route('/upload_college_logo', methods=['POST'])
@secure_route
def upload_college_logo():
    login_id = session.get('login_id')
    college = College.query.filter_by(login_id=login_id).first()
    
    if not college:
        flash('College not found.', 'error')
        return redirect(url_for('auth.login'))

    if 'college_logo' in request.files:
        file = request.files['college_logo']
        
        if file and file.filename != '':
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            def allowed_file(filename):
                return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
            
            if allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"logo_{college.id}_{uuid.uuid4().hex[:8]}.{ext}"
                
                logos_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'college_logos')
                if not os.path.exists(logos_dir):
                    os.makedirs(logos_dir)
                    
                file_path = os.path.join(logos_dir, unique_filename)
                file.save(file_path)
                
                # Update database
                college.logo = f"/static/uploads/college_logos/{unique_filename}"
                db.session.commit()
                flash('College logo updated successfully!', 'success')
            else:
                flash('Invalid image format. Only JPG, PNG, and GIF are allowed.', 'danger')
        else:
            flash('No file selected.', 'danger')
            
    return redirect(url_for('college.college_profile'))

@college_blueprint.route('/college_studenttracking')
@secure_route
def college_studenttracking():
    login_id = session.get('login_id')
    
    if not login_id or session.get('role') != 'college':
        flash("College is not logged in.", "error")
        return redirect(url_for('auth.login'))

    # Get college profile
    college_profile = College.query.filter_by(login_id=login_id).first()
    
    page = request.args.get('page', 1, type=int)
    per_page = 5
    
    search_query = request.args.get('search_query', '').strip()
    selected_status = request.args.getlist('status')
    
    # Query to join the tables and filter by the logged-in college's login_id
    query = db.session.query(
        User.id.label('user_id'),          # <--- ADDED THIS LINE!
        User.name.label('student_name'),
        User.is_banned,
        Company.company_name.label('company_name'),
        Job.title.label('job_title'),  
        JobApplication.status.label('job_application_status')
    ).join(Couponuser, Couponuser.user_id == User.id)\
     .join(Coupon, Coupon.id == Couponuser.coupon_id)\
     .join(JobApplication, JobApplication.user_id == User.id)\
     .join(Job, Job.job_id == JobApplication.job_id)\
     .join(Company, Company.login_id == Job.created_by)\
     .filter(Coupon.college_id == college_profile.id)

    # Apply Status Filters
    if selected_status:
        query = query.filter(JobApplication.status.in_(selected_status))
        
    # Apply Search Filters across multiple columns
    if search_query:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                Company.company_name.ilike(f'%{search_query}%'),
                Job.title.ilike(f'%{search_query}%')
            )
        )
        
    # Order and paginate the final results
    pagination = query.order_by(JobApplication.date_applied.desc()).paginate(page=page, per_page=per_page, error_out=False)
    student_activity = pagination.items

    # Fixed the return statement by removing the incomplete "user_id=" 
    return render_template('/college/student_tracking.html',
        student_activity=student_activity,
        college_profile=college_profile,
        pagination=pagination,
        page=page,
        search_query=search_query,
        selected_status=selected_status)

@college_blueprint.route('/api/student_profile/<uuid:user_id>', methods=['GET'])
@secure_route
def api_student_profile(user_id):
    if session.get('role') != 'college':
        return jsonify({"error": "Unauthorized"}), 403
        
    user = User.query.get_or_404(user_id)
    certifications = Certification.query.filter_by(user_id=user_id).all()
    resume = ResumeCertification.query.filter_by(user_id=user_id).order_by(ResumeCertification.uploaded_at.desc()).first()
    
    profile_data = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone if user.phone else "Not provided",
        "age": user.age if user.age else "Not provided",
        "about_me": user.about_me if user.about_me else "No description provided.",
        "profile_picture": user.profile_picture if user.profile_picture else "/static/default_avatar.png",
        "resume_url": resume.resume_path if resume else None,
        "skills": [
            {
                "id": str(cert.id),
                "name": cert.certification_name,
                "is_verified": cert.verification_status
            } for cert in certifications
        ]
    }
    return jsonify(profile_data)

@college_blueprint.route('/college_referall')
@secure_route
def college_referall():
    return render_template('/college/referall.html')

@college_blueprint.route('/college_collab')
@secure_route
def college_collab():
    login_id = session.get('login_id')
    
    if not login_id or session.get('role') != 'college':
        flash("College is not logged in.", "error")
        return redirect(url_for('auth.login'))

    # Get college profile
    college_profile = College.query.filter_by(login_id=login_id).first()
    
    if not college_profile:
        flash("College profile not found.", "error")
        return redirect(url_for('auth.login'))
        
    college_id = college_profile.id  # Get college_id from the profile for related queries
    
    # UPDATED: Get total distinct students who have APPLIED to at least one job
    total_students = db.session.query(func.count(distinct(User.id)))\
        .join(JobApplication, JobApplication.user_id == User.id)\
        .join(Couponuser, Couponuser.user_id == User.id)\
        .join(Coupon, Coupon.id == Couponuser.coupon_id)\
        .filter(Coupon.college_id == college_id)\
        .scalar() or 0

    partnered_companies = []

    # Count distinct placed students from this college
    placed_students = db.session.query(func.count(distinct(User.id)))\
        .join(JobApplication, JobApplication.user_id == User.id)\
        .join(Couponuser, Couponuser.user_id == User.id)\
        .join(Coupon, Coupon.id == Couponuser.coupon_id)\
        .filter(
            Coupon.college_id == college_id,
            JobApplication.status == 'Hired'
        ).scalar() or 0

    # Calculate placement percentage based on APPLIED students
    placed_percentage = 0
    if total_students > 0:
        placed_percentage = round((placed_students / total_students) * 100, 2)

    return render_template('/college/collab.html',
        partnered_companies=partnered_companies,
        total_students=total_students,
        placed_percentage=placed_percentage,
        college_profile=college_profile)

def generate_coupon_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

@college_blueprint.route('/generate_coupon', methods=['GET', 'POST'])
@secure_route
def generate_coupon():
    login_id = session.get('login_id')
   
    if not login_id or session.get('role') != 'college':
        flash("College is not logged in.", "error")
        return redirect(url_for('auth.login'))
   
    # Get college profile using login_id instead of college_id
    college_profile = College.query.filter_by(login_id=login_id).first()
    # Fetch all active coupons from the database using the college profile
    coupons = Coupon.query.filter_by(college_id=college_profile.id).order_by(Coupon.created_at.desc()).all()
    
    if request.method == 'POST':
        faculty_id = request.form['faculty_id']
        year = request.form['year']
       
        # Validate year - must be exactly 4 digits (YYYY format)
        if not re.match(r'^\d{4}$', year):
            flash("Year must be a 4-digit number (YYYY format)!", "error")
            return redirect(url_for('college.generate_coupon'))
        
        # Additional validation to ensure it's a reasonable year
        year_num = int(year)
        current_year = datetime.now().year
        if year_num < 1900 or year_num > current_year:
            flash(f"Please enter a valid year between 1900 and {current_year}!", "error")
            return redirect(url_for('college.generate_coupon'))
           
        # Validate Faculty ID - letters, numbers, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9\-_]{1,20}$', faculty_id):
            flash("Faculty ID can only contain letters and numbers!", "error")
            return redirect(url_for('college.generate_coupon'))
        
        # Check if a coupon already exists for this year, previous year, or next year
        existing_coupon_same_year = Coupon.query.filter_by(
            college_id=college_profile.id, 
            year=str(year_num)
        ).first()
        
        existing_coupon_prev_year = Coupon.query.filter_by(
            college_id=college_profile.id, 
            year=str(year_num - 1)
        ).first()
        
        existing_coupon_next_year = Coupon.query.filter_by(
            college_id=college_profile.id, 
            year=str(year_num + 1)
        ).first()
        
        if existing_coupon_same_year:
            flash(f"Coupon for year {year} already exists!", "error")
            return redirect(url_for('college.generate_coupon'))
        elif existing_coupon_prev_year:
            flash(f"Cannot create coupon for {year} as coupon for consecutive year {year_num - 1} already exists!", "error")
            return redirect(url_for('college.generate_coupon'))
        elif existing_coupon_next_year:
            flash(f"Cannot create coupon for {year} as coupon for consecutive year {year_num + 1} already exists!", "error")
            return redirect(url_for('college.generate_coupon'))
       
        # Generate a unique coupon code
        coupon_code = generate_coupon_code()
        while Coupon.query.filter_by(code=coupon_code).first():
            coupon_code = generate_coupon_code()
       
        # Add the coupon to the database
        new_coupon = Coupon(code=coupon_code, faculty_id=faculty_id, year=year, college_id=college_profile.id)
        db.session.add(new_coupon)
        db.session.commit()
       
        flash(f'Coupon "{coupon_code}" generated successfully and is valid for 2 years!', 'success')
        return redirect(url_for('college.generate_coupon'))
   
    # Set message to pass to template for both GET and POST requests
    message = None
    message_type = None
   
    if 'message' in session:
        message = session.pop('message')
        message_type = session.pop('message_type', 'success')
   
    # Render the template with data
    return render_template('college/coupon.html',
        coupons=coupons,
        college_profile=college_profile,
        message=message,
        message_type=message_type)

@college_blueprint.route('/college_endorsement')
@secure_route
def college_endorsement():
    login_id = session.get('login_id')
    
    if not login_id or session.get('role') != 'college':
        flash("College is not logged in.", "error")
        return redirect(url_for('auth.login'))
    
    # Get college profile using login_id instead of college_id
    college_profile = College.query.filter_by(login_id=login_id).first()
    
    if not college_profile:
        flash("College profile not found.", "error")
        return redirect(url_for('auth.login'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 5

    search_query = request.args.get('search_query', '').strip()

    # Fetch the necessary data from the database
    query = db.session.query(
        Coupon.code.label('coupon_code'),
        User.name.label('user_name'),
        User.is_banned,
        Coupon.faculty_id,
        Coupon.year,
        User.id.label('user_id'),
        Couponuser.created_at
    ).join(Couponuser, Couponuser.coupon_id == Coupon.id)\
    .join(User, Couponuser.user_id == User.id)\
    .filter(Coupon.college_id == college_profile.id)

    if search_query:
        query = query.filter(
            or_(
                User.name.ilike(f'%{search_query}%'),
                Coupon.year.ilike(f'%{search_query}%')
            )
        )

    pagination = query.order_by(Couponuser.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    coupon_users = pagination.items

    return render_template('/college/endorse.html', 
        coupon_users=coupon_users,
        college_profile=college_profile,
        pagination=pagination,
        page=page,
        search_query=search_query)

# API endpoint to get user details for the modal
@college_blueprint.route('/api/user_details/<user_id>')
@secure_route
def api_user_details(user_id):
    if session.get('role') != 'college':
        return jsonify({"error": "Unauthorized"}), 403
    
    # Convert string UUID to UUID object for querying
    try:
        import uuid
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Invalid user ID format"}), 400
    
    user = User.query.get_or_404(user_uuid)
    certifications = Certification.query.filter_by(user_id=user_uuid).all()
    
    # Format user data for JSON response
    user_data = {
        "name": user.name,
        "email": user.email,
        "phone": user.phone if hasattr(user, 'phone') else "Not provided",
        "age": user.age if hasattr(user, 'age') else "Not provided"
    }
    
    # Format certifications data for JSON response
    cert_data = []
    for cert in certifications:
        cert_data.append({
            "id": str(cert.id),  # Convert UUID to string for JSON
            "certification_name": cert.certification_name,
            "verification_status": cert.verification_status
        })
    
    return jsonify({
        "user": user_data,
        "certifications": cert_data
    })

# Endpoint to verify certification
@college_blueprint.route('/verify_certification/<cert_id>', methods=['POST'])
@secure_route
def verify_certification(cert_id):
    if session.get('role') != 'college':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    # Convert string UUID to UUID object for querying
    try:
        import uuid
        cert_uuid = uuid.UUID(cert_id)
    except ValueError:
        return jsonify({"success": False, "message": "Invalid certification ID format"}), 400
    
    certification = Certification.query.get_or_404(cert_uuid)
    
    try:
        certification.verification_status = True
        db.session.commit()
        return jsonify({"success": True, "message": "Certification verified successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    
# Endpoint to un-verify certification
@college_blueprint.route('/unverify_certification/<cert_id>', methods=['POST'])
@secure_route
def unverify_certification(cert_id):
    if session.get('role') != 'college':
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    try:
        import uuid
        cert_uuid = uuid.UUID(cert_id)
    except ValueError:
        return jsonify({"success": False, "message": "Invalid certification ID format"}), 400
    
    certification = Certification.query.get_or_404(cert_uuid)
    
    try:
        # Change status back to False
        certification.verification_status = False
        db.session.commit()
        return jsonify({"success": True, "message": "Skill un-endorsed successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
