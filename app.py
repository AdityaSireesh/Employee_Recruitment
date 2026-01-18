from flask import Flask, render_template, g, session, redirect, flash
from flask import jsonify, request, make_response, url_for
from datetime import datetime, timedelta
import sqlite3
from flask_cors import CORS
from flask_login import LoginManager
from config import Config
from models import db, User, Job, Company, JobApplication, Login, Favorite, Communication, Notification, Couponuser, ResumeCertification, Certification
from auth import auth_blueprint
from user import user_blueprint
from company import company_blueprint
from college import college_blueprint
from admin import admin_blueprint
from flask_migrate import Migrate
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import os
import uuid
from sqlalchemy import or_
from datetime import datetime
import pytz
import re
import calendar

app = Flask(__name__)

# SECRET KEY - Set first
app.secret_key = 'your_secret_key'  # Change to secure random key in production

# SESSION CONFIGURATION - Minimal required settings
app.config['SESSION_COOKIE_NAME'] = 'admin_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set True in production with HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = '127.0.0.1'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# CORS CONFIGURATION - Minimal required settings
# Place after app initialization and before blueprint registration
CORS(app, 
     origins=["http://127.0.0.1:3000"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "X-Requested-With", "Authorization"],
     expose_headers=["Content-Range", "X-Content-Range"],
     supports_credentials=True)


# Ensure upload folder exists
if not os.path.exists(Config.UPLOAD_FOLDER):
    os.makedirs(Config.UPLOAD_FOLDER)

# Load configuration from Config object          
app.config.from_object(Config)

# Set the session lifetime to 1 hour (3600 seconds) for inactivity logout
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use your mail server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'employeerecruitment123@gmail.com'  # Sender email address
app.config['MAIL_PASSWORD'] = 'gbpanjpyqscfqykr'  # Sender email password
app.config['MAIL_DEFAULT_SENDER'] = 'employeerecruitment123@gmail.com'

# Initialize Flask-Mail
mail = Mail(app)

# Register blueprints with URL prefixes
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(user_blueprint, url_prefix='/user')
app.register_blueprint(company_blueprint, url_prefix='/company')
app.register_blueprint(admin_blueprint, url_prefix='/admin')
app.register_blueprint(college_blueprint, url_prefix='/college')

db.init_app(app)
migrate = Migrate(app, db)

# This function runs before each request to handle session timeout AND ban checks
@app.before_request
def before_request_handler():
    session.permanent = True
    if 'login_id' in session:
        # Exclude static files from these checks for efficiency
        if request.endpoint and 'static' in request.endpoint:
            return
        
        # Helper function to correctly log out while preserving the flash message
        def logout_and_flash(message, category):
            flash(message, category)
            # Manually remove only the keys related to authentication.
            session.pop('login_id', None)
            session.pop('username', None)
            session.pop('role', None)
            session.pop('user_id', None)
            session.pop('company_id', None)
            session.pop('college_id', None)
            session.pop('last_activity', None)
            session.pop('session_token', None) # Also remove the token
            return redirect(url_for('auth.login'))

        # 0. Check for session validity by comparing tokens
        login_entry = Login.query.filter_by(id=session['login_id']).first() # Use get_or_404 for simplicity
        
        if not login_entry:
            # Session record not found
            session.clear()
            return redirect(url_for('auth.login'))
        
        # If the token in the user's cookie doesn't match the one in the DB, log them out.
        if login_entry.session_token != session.get('session_token'):
            return logout_and_flash('Your session has expired because your password was changed. Please log in again.', 'info')

        now = datetime.utcnow()
        
        # 1. Check for session inactivity
        if 'last_activity' in session:
            last_activity = session['last_activity']
            if last_activity.tzinfo is not None:
                last_activity = last_activity.replace(tzinfo=None)
            if now - last_activity > app.config['PERMANENT_SESSION_LIFETIME']:
                flash('You have been logged out due to inactivity.', 'info')
                # session.clear()
                return redirect(url_for('auth.login'))

        # 2. Check for banned status on every request
        role = session.get('role')
        login_id = session.get('login_id')
        is_banned = False

        if role == 'user':
            user = User.query.filter_by(login_id=login_id).first()
            if user and user.is_banned:
                is_banned = True
        elif role == 'company':
            company = Company.query.filter_by(login_id=login_id).first()
            if company and company.is_banned:
                is_banned = True
        
        if is_banned:
            session.clear()
            flash('Your account has been suspended. Please contact support.', 'danger')
            return redirect(url_for('auth.login'))

        # If all checks pass, update the last activity time
        session['last_activity'] = now

# Initialize Flask-Home
@app.route('/')
def index():
    return render_template('home.html')


# ========== USERS API ==========


@app.route('/users/<uuid:id>', methods=['GET'])
def get_user_details(id):
    user = User.query.get_or_404(id)
    user_data = {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phone': user.phone,
        'age': user.age,
        'about_me': user.about_me,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'college_name': user.college_name,
        'is_banned': user.is_banned
    }
    return jsonify(user_data)

# == CORRECTED USERS GET ROUTE WITH SORTING ==
@app.route('/users', methods=['GET'])
def get_users():
    query = User.query
    
    if 'q' in request.args and request.args['q']:
        search_term = request.args['q']
        
        if "name:" in search_term:
            name_term = search_term.split("name:")[1].strip()
            query = query.filter(User.name.ilike(f"%{name_term}%"))
        elif "email:" in search_term:
            email_term = search_term.split("email:")[1].strip()
            query = query.filter(User.email.ilike(f"%{email_term}%"))
        else:
            search_term = f"%{search_term}%"
            query = query.filter(or_(
            User.name.ilike(search_term),
            User.email.ilike(search_term)
        ))
    
    # --- SORTING LOGIC ADDED ---
    sort_by = request.args.get('sort')
    order = request.args.get('order')

    if sort_by == 'name':
        if order == 'desc':
            query = query.order_by(User.name.desc())
        else:
            query = query.order_by(User.name.asc())
    elif sort_by == 'created_at':
        if order == 'desc':
            query = query.order_by(User.created_at.desc())
        else:
            query = query.order_by(User.created_at.asc())
    else:
        # Default sort order if no valid sort parameter is provided
        query = query.order_by(User.updated_at.desc())

    users = query.all()
    # --- END OF SORTING LOGIC ---

    users_data = [
        {
            'id': user.id, 
            'name': user.name, 
            'email': user.email,
            'college_name': user.college_name,
            'is_banned': user.is_banned 
        } 
        for user in users
    ]
    
    response = make_response(jsonify(users_data))
    response.headers['Content-Range'] = f'users 0-{len(users_data)-1}/{len(users_data)}'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Range'
    return response

@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    new_user = User(
        name=data['name'],
        email=data['email'],
        # Add other user fields as needed
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created successfully!", "id": new_user.id}), 201

@app.route('/users/<uuid:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    data = request.json
    for key, value in data.items():
        setattr(user, key, value)
    
    db.session.commit()
    return jsonify({"message": "User updated successfully!"})

# == UPDATED USER DELETE ROUTE ==
@app.route('/users/<uuid:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404
    
    try:
        login_id_to_delete = user.login_id

        # Dependencies on User.id
        JobApplication.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        Favorite.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        Couponuser.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        ResumeCertification.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        Certification.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        
        # Dependencies on User.login_id
        if login_id_to_delete:
            Communication.query.filter_by(user_id=login_id_to_delete).delete(synchronize_session=False)
            Notification.query.filter_by(user_id=login_id_to_delete).delete(synchronize_session=False)
        
        # Now delete the user itself
        db.session.delete(user)
        
        # And finally, delete the associated login record if it exists
        if login_id_to_delete:
            Login.query.filter_by(id=login_id_to_delete).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({"message": "User and all related data deleted successfully!", "id": user_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error deleting user: {str(e)}"}), 500

# == UPDATED USER BULK DELETE ROUTE ==
@app.route('/users/bulk', methods=['DELETE'])
def delete_users_bulk():
    user_ids = request.json.get('ids', [])
    if not user_ids:
        return jsonify({"message": "No user IDs provided"}), 400
        
    try:
        # Fetch the users to get their corresponding login_ids
        users = User.query.filter(User.id.in_(user_ids)).all()
        login_ids = [user.login_id for user in users if user.login_id]

        # Bulk delete dependencies on User.id
        JobApplication.query.filter(JobApplication.user_id.in_(user_ids)).delete(synchronize_session=False)
        Favorite.query.filter(Favorite.user_id.in_(user_ids)).delete(synchronize_session=False)
        Couponuser.query.filter(Couponuser.user_id.in_(user_ids)).delete(synchronize_session=False)
        ResumeCertification.query.filter(ResumeCertification.user_id.in_(user_ids)).delete(synchronize_session=False)
        Certification.query.filter(Certification.user_id.in_(user_ids)).delete(synchronize_session=False)
        
        # Bulk delete dependencies on User.login_id
        if login_ids:
            Communication.query.filter(Communication.user_id.in_(login_ids)).delete(synchronize_session=False)
            Notification.query.filter(Notification.user_id.in_(login_ids)).delete(synchronize_session=False)
        
        # Bulk delete the users themselves.
        num_deleted = User.query.filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        
        # ## NEWLY ADDED LOGIC ##
        # Now, explicitly bulk delete the associated Login records, which the cascade bypasses.
        if login_ids:
            Login.query.filter(Login.id.in_(login_ids)).delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({"message": f"Deleted {num_deleted} users and their related data successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error during bulk user deletion: {str(e)}"}), 500


# ========== COMPANIES API ==========

@app.route('/companies/<uuid:id>', methods=['GET'])
def get_company_details(id):
    company = Company.query.get_or_404(id)
    company_data = {
        'id': company.id,
        'company_name': company.company_name,
        'email': company.email,
        'address': company.address,
        'website': company.website,
        'logo': company.logo,
        'description': company.description,
        'industry': company.industry,
        'created_at': company.created_at,
        'is_banned': company.is_banned
    }
    return jsonify(company_data)

# == CORRECTED COMPANIES GET ROUTE WITH SORTING ==
@app.route('/companies', methods=['GET'])
def get_companies():
    query = Company.query
    
    if 'q' in request.args and request.args['q']:
        search_term = request.args['q']
        
        if "company_name:" in search_term:
            name_term = search_term.split("company_name:")[1].strip()
            query = query.filter(Company.company_name.ilike(f"%{name_term}%"))
        elif "email:" in search_term:
            email_term = search_term.split("email:")[1].strip()
            query = query.filter(Company.email.ilike(f"%{email_term}%"))
        elif "industry:" in search_term:
            industry_term = search_term.split("industry:")[1].strip()
            query = query.filter(Company.industry.ilike(f"%{industry_term}%"))
        else:
            search_term = f"%{search_term}%"
            query = query.filter(or_(
            Company.company_name.ilike(search_term),
            Company.email.ilike(search_term),
            Company.industry.ilike(search_term)
        ))
    
    # --- SORTING LOGIC ADDED ---
    sort_by = request.args.get('sort')
    order = request.args.get('order')

    if sort_by == 'company_name':
        if order == 'desc':
            query = query.order_by(Company.company_name.desc())
        else:
            query = query.order_by(Company.company_name.asc())
    elif sort_by == 'created_at':
        if order == 'desc':
            query = query.order_by(Company.created_at.desc())
        else:
            query = query.order_by(Company.created_at.asc())
    else:
        # Default sort order
        query = query.order_by(Company.updated_at.desc())

    companies = query.all()
    # --- END OF SORTING LOGIC ---

    companies_data = [
        {
            'id': company.id,
            'company_name': company.company_name,
            'email': company.email,
            'industry': company.industry,
            'is_banned': company.is_banned
        } 
        for company in companies
    ]
    
    response = make_response(jsonify(companies_data))
    response.headers['Content-Range'] = f'companies 0-{len(companies_data)-1}/{len(companies_data)}'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Range'
    return response

'''# Updated route in app.py
@app.route('/companies', methods=['POST'])
def create_company():
    data = request.json
    
    try:
        # First, create the login entry
        new_login = Login(
            username=data['company_name'],  # Using company name as username
            role='company'
        )
        new_login.set_password(data['password'])  # This will hash the password
        
        # Add and flush to get the ID without committing
        db.session.add(new_login)
        db.session.flush()  # This assigns the ID to new_login without committing
        
        # Now create the company entry with the login_id
        new_company = Company(
            login_id=new_login.id,  # Reference the login ID
            company_name=data['company_name'],
            email=data['email'],
            address=data.get('address', ''),
            website=data.get('website', ''),
            logo=data.get('logo', ''),
            description=data.get('description', ''),
            industry=data.get('industry', ''),
            is_banned=data.get('is_banned', False)
        )
        
        db.session.add(new_company)
        db.session.commit()  # Commit both entries
        
        return jsonify({
            "message": "Company created successfully!", 
            "id": new_company.id,
            "login_id": new_login.id
        }), 201
        
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        return jsonify({"error": f"Error creating company: {str(e)}"}), 500
'''

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

import dns.resolver
from dns.exception import DNSException

def validate_email_domain(email):
    """
    Check if email domain has valid MX records (can receive email).
    Returns (is_valid: bool, error_message: str)
    """
    try:
        domain = email.split('@')[1].lower()
        
        """# Common typos in popular domains
        common_typos = {
            'gmial.com': 'gmail.com',
            'gmai.com': 'gmail.com',
            'gamil.com': 'gmail.com',
            'gmil.com': 'gmail.com',
            'yahooo.com': 'yahoo.com',
            'yaho.com': 'yahoo.com',
            'outlok.com': 'outlook.com',
            'outloo.com': 'outlook.com',
            'hotmial.com': 'hotmail.com',
            'hotmal.com': 'hotmail.com',
        }
        
        # Check for common typos
        if domain in common_typos:
            suggested = common_typos[domain]
            return False, f"Did you mean '{email.split('@')[0]}@{suggested}'? Please check your email address."
        """
        
        # Check for MX records (mail servers)
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            if mx_records:
                return True, None
        except dns.resolver.NoAnswer:
            # No MX records, try A record (some domains use A records for email)
            try:
                a_records = dns.resolver.resolve(domain, 'A')
                if a_records:
                    return True, None
            except dns.resolver.NXDOMAIN:
                return False, f"The email domain '{domain}' does not exist. Please check your email address."
            except:
                return False, f"Unable to verify the domain '{domain}'. Please check your email address."
        except dns.resolver.NXDOMAIN:
            return False, f"The email domain '{domain}' does not exist. Please check your email address."
        except dns.resolver.Timeout:
            # DNS lookup timed out - allow signup rather than blocking user
            print(f"DNS timeout for domain: {domain}")
            return True, None
        
        return False, f"The email domain '{domain}' cannot receive emails. Please use a valid email address."
        
    except IndexError:
        return False, "Invalid email format. Email must contain '@' symbol."
    except DNSException as e:
        print(f"DNS error for {email}: {e}")
        return False, "Unable to verify email domain. Please check your email address and try again."
    except Exception as e:
        # Unexpected error - allow signup gracefully
        print(f"Email validation error for {email}: {e}")
        return True, None  # Don't block users on unexpected errors

@app.route('/companies', methods=['POST'])
def create_company():
    data = request.json or {}

    try:
        raw_company_name = (data.get('company_name') or '').strip()
        raw_email = (data.get('email') or '').strip()
        raw_address = (data.get('address') or '').strip()
        raw_website = (data.get('website') or '').strip()
        raw_logo = (data.get('logo') or '').strip()
        raw_description = (data.get('description') or '').strip()
        industry = (data.get('industry') or '').strip()
        password = data.get('password') or ''
        is_banned = data.get('is_banned', False)

        # Always define website/logo to avoid UnboundLocalError
        website = raw_website.strip() if raw_website else ''
        logo = raw_logo.strip() if raw_logo else ''

        # ---- Reject raw dangerous content (like company_post_new_job) ----
        dangerous_raw_fields = [raw_company_name, raw_address, raw_description]
        if any(
            re.search(r'<\s*script[\s\S]*?>[\s\S]*?<\s*/\s*script\s*>', f, re.IGNORECASE) or
            re.search(r'(javascript\s*:|data\s*:)', f, re.IGNORECASE)
            for f in dangerous_raw_fields if f
        ):
            return jsonify({
                "message": "Dangerous content is not allowed in text fields."
            }), 400

        # ---- Sanitise text ----
        company_name = sanitize_text(raw_company_name)
        address = sanitize_text(raw_address)
        description = sanitize_text(raw_description)

        # ---- Basic required checks ----
        if not company_name:
            return jsonify({
                "message": "Company Name is required."
            }), 400

        if len(company_name) < 3 or len(company_name) > 100:
            return jsonify({"message": "Company Name must be between 3-100 characters!"}), 400

        if not raw_email:
            return jsonify({"message": "Email address is required."}), 400

        if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', raw_email):
            return jsonify({"message": "Invalid email format!"}), 400

        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.[a-zA-Z]{2,}$', raw_email):
            return jsonify({"message": "Invalid email format!"}), 400
        
        if '..' in raw_email or raw_email.startswith('.') or raw_email.endswith('.'):
            return jsonify({"message": "Email format is invalid."}), 400
        
        if len(raw_email) > 90:
            return jsonify({"message": "Email address is too long."}), 400
        
        # ✅ NEW: DNS MX Record Check
        is_valid_domain, domain_error = validate_email_domain(raw_email)
        if not is_valid_domain:
            return jsonify({"message": domain_error}), 400

        if not password:
            return jsonify({"message": "Password is required."}), 400

        if len(description) > 1000:
            return jsonify({"message": "Description must be under 1000 characters!"}), 400

        if len(address) > 500:
            return jsonify({"message": "Address must be under 500 characters!"}), 400

        # ---- Website URL checks (optional field) ----
        if website:
            if re.search(r'\s', website):
                return jsonify({"message": "Please enter only one website URL."}), 400

            # Must start with http/https
            if not re.match(r'^https?', website, re.IGNORECASE):
                return jsonify({"message": "Website URL must start with http or https."}), 400
            # Block javascript:/data:
            if re.match(r'^(javascript|data)', website, re.IGNORECASE):
                return jsonify({"message": "Website URL scheme is not allowed."}), 400
            # Optional ping
            if website and not url_seems_reachable(website):
                return jsonify({"message": "Website URL could not be reached. Please check the link."}), 400

        # ---- Logo URL checks (optional field) ----
        if logo:
            # Single URL only
            if re.search(r'\s', logo):
                return jsonify({"message": "Please enter only one logo URL."}), 400
            if not re.match(r'^https?', logo, re.IGNORECASE):
                return jsonify({"message": "Please provide a publicly accessible link."}), 400
            if re.match(r'^(javascript:|data:)', logo, re.IGNORECASE):
                return jsonify({"message": "Logo URL scheme is not allowed."}), 400
            if logo and not url_seems_reachable(logo):
                return jsonify({"message": "Logo URL could not be reached. Please check the link."}), 400

        # ---- Create Login entry ----
        new_login = Login(
            username=company_name,
            role='company'
        )
        new_login.set_password(password)
        db.session.add(new_login)
        db.session.flush()  # get new_login.id

        # --- create Company record with correct column names ---
        new_company = Company(
            login_id=new_login.id,
            company_name=company_name,
            email=raw_email,
            address=address,
            website=website,
            logo=logo,
            description=description,
            industry=industry,
            is_banned=is_banned,
        )

        db.session.add(new_company)
        db.session.commit()

        return jsonify({
            "message": "Company created successfully!",
            "id": str(new_company.id),
            "login_id": str(new_login.id),
        }), 201

    except Exception as e:
        db.session.rollback()
        # log for debugging
        print(f"ERROR /companies POST: {e}")
        return jsonify({"message": f"Error creating company"}), 500 # : {str(e)}

@app.route('/companies/<uuid:company_id>', methods=['PUT'])
def update_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    
    data = request.json
    for key, value in data.items():
        setattr(company, key, value)
    
    db.session.commit()
    return jsonify({"message": "Company updated successfully!"})


# == UPDATED COMPANY DELETE ROUTE ==
@app.route('/companies/<uuid:company_id>', methods=['DELETE'])
def delete_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"message": "Company not found"}), 404
    
    try:
        login_id = company.login_id

        # Find all jobs created by this company's login
        jobs_to_delete = Job.query.filter_by(created_by=login_id).all()
        job_ids = [job.job_id for job in jobs_to_delete]

        # If there are jobs, delete their dependent records first
        if job_ids:
            JobApplication.query.filter(JobApplication.job_id.in_(job_ids)).delete(synchronize_session=False)
            Favorite.query.filter(Favorite.job_id.in_(job_ids)).delete(synchronize_session=False)
            # Now delete the jobs themselves
            Job.query.filter(Job.job_id.in_(job_ids)).delete(synchronize_session=False)
        
        # Delete other dependencies linked to the company's login_id
        Notification.query.filter_by(company_id=login_id).delete(synchronize_session=False)
        Communication.query.filter_by(company_id=login_id).delete(synchronize_session=False)
        
        # Now delete the company, which will cascade to delete the login
        db.session.delete(company)
        
        db.session.commit()
        return jsonify({"id": company_id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error deleting company: {str(e)}"}), 500


# == UPDATED COMPANY BULK DELETE ROUTE ==
@app.route('/companies/bulk', methods=['DELETE'])
def delete_companies_bulk():
    company_ids_to_delete = request.json.get('ids', [])
    print(f"Company IDs to delete: {company_ids_to_delete}")

    if not company_ids_to_delete:
        return jsonify({"message": "No company IDs provided"}), 400
    
    try:
        # Fetch companies and their login_ids
        companies = Company.query.filter(Company.id.in_(company_ids_to_delete)).all()
        login_ids = [c.login_id for c in companies if c.login_id]
        
        if not login_ids:
            # If no companies found or they have no logins, just try deleting companies
            num_deleted = Company.query.filter(Company.id.in_(company_ids_to_delete)).delete(synchronize_session=False)
            db.session.commit()
            return jsonify({"message": f"Deleted {num_deleted} companies successfully"})

        # Find all jobs created by these companies
        jobs_to_delete = Job.query.filter(Job.created_by.in_(login_ids)).all()
        job_ids = [job.job_id for job in jobs_to_delete]

        # Bulk delete dependencies of jobs
        if job_ids:
            JobApplication.query.filter(JobApplication.job_id.in_(job_ids)).delete(synchronize_session=False)
            Favorite.query.filter(Favorite.job_id.in_(job_ids)).delete(synchronize_session=False)
            # Bulk delete jobs
            Job.query.filter(Job.job_id.in_(job_ids)).delete(synchronize_session=False)

        # Bulk delete other company dependencies
        Notification.query.filter(Notification.company_id.in_(login_ids)).delete(synchronize_session=False)
        Communication.query.filter(Communication.company_id.in_(login_ids)).delete(synchronize_session=False)

        # Now, it's safe to delete the companies and their associated logins
        num_deleted = Company.query.filter(Company.id.in_(company_ids_to_delete)).delete(synchronize_session=False)
        Login.query.filter(Login.id.in_(login_ids)).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({
            "message": f"Deleted {num_deleted} companies and their associated data successfully"
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error during bulk delete: {str(e)}")
        return jsonify({"message": f"Error deleting companies: {str(e)}"}), 500

# New route for company profile redirection
@app.route('/company/company_profile', methods=['GET'])
def company_profile_form():
    return jsonify({"message": "Company profile form page. This endpoint would normally serve HTML in a production app."}), 200

# New route for handling company profile submission
@app.route('/company/company_profile', methods=['POST'])
def submit_company_profile():
    data = request.json
    try:
        new_company = Company(
            company_name=data['company_name'],
            email=data['email'],
            # Add any additional fields your Company model supports
            # Such as description, address, website, etc.
        )
        db.session.add(new_company)
        db.session.commit()
        return jsonify({"success": True, "message": "Company profile created successfully!", "id": new_company.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error creating company profile: {str(e)}"}), 500

# ========== JOBS API ==========
# == CORRECTED JOBS GET ROUTE WITH SORTING ==
@app.route('/jobs', methods=['GET'])
def get_jobs():
    # Join Job with Login and Company tables to get company name
    query = db.session.query(Job, Company.company_name).join(
        Login, Job.created_by == Login.id
    ).join(
        Company, Login.id == Company.login_id
    )
    
    if 'q' in request.args and request.args['q']:
        search_term = request.args['q']
        
        if "title:" in search_term:
            title_term = search_term.split("title:")[1].strip()
            query = query.filter(Job.title.ilike(f"%{title_term}%"))
        elif "job_type:" in search_term:
            type_term = search_term.split("job_type:")[1].strip()
            query = query.filter(Job.job_type.ilike(f"%{type_term}%"))
        elif "location:" in search_term:
            location_term = search_term.split("location:")[1].strip()
            query = query.filter(Job.location.ilike(f"%{location_term}%"))
        elif "status:" in search_term:
            status_term = search_term.split("status:")[1].strip()
            query = query.filter(Job.status.ilike(f"%{status_term}%"))
        elif "company:" in search_term:
            company_term = search_term.split("company:")[1].strip()
            query = query.filter(Company.company_name.ilike(f"%{company_term}%"))
        else:
            search_term = f"%{search_term}%"
            query = query.filter(or_(
                Job.title.ilike(search_term),
                Job.job_type.ilike(search_term),
                Job.location.ilike(search_term),
                Job.status.ilike(search_term),
                Company.company_name.ilike(search_term)
            ))
    
    # --- SORTING LOGIC ADDED ---
    sort_by = request.args.get('sort')
    order = request.args.get('order')

    if sort_by == 'title':
        if order == 'desc':
            query = query.order_by(Job.title.desc())
        else:
            query = query.order_by(Job.title.asc())
    elif sort_by == 'created_at':
        if order == 'desc':
            query = query.order_by(Job.created_at.desc())
        else:
            query = query.order_by(Job.created_at.asc())
    else:
        # Default sort order
        query = query.order_by(Job.updated_at.desc())
    
    results = query.all()
    # --- END OF SORTING LOGIC ---
    
    jobs_data = [{
        'id': job.job_id,
        'job_id': job.job_id,
        'title': job.title,
        'description': job.description,
        'job_type': job.job_type,
        'skills': job.skills,
        'years_of_exp': job.years_of_exp,
        'certifications': job.certifications,
        'location': job.location,
        'salary': job.salary,
        'total_vacancy': job.total_vacancy,
        'filled_vacancy': job.filled_vacancy,
        'status': job.status,
        'form_url': job.form_url,
        'created_at': job.created_at,
        'deadline': job.deadline.strftime('%Y-%m-%d') if job.deadline else None,
        'created_by': job.created_by,
        'company_name': company_name  # Add company name to response
    } for job, company_name in results]
    
    response = make_response(jsonify(jobs_data))
    response.headers['Content-Range'] = f'jobs 0-{len(jobs_data)-1}/{len(jobs_data)}'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Range'
    return response

@app.route('/jobs', methods=['POST'])
def create_job():
    data = request.json
    
    # Parse deadline if it exists
    deadline = None
    if 'deadline' in data and data['deadline']:
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid deadline format. Use YYYY-MM-DD"}), 400
    
    new_job = Job(
        title=data['title'],
        description=data['description'],
        job_type=data['job_type'],
        skills=data.get('skills', ''),
        years_of_exp=data['years_of_exp'],
        certifications=data.get('certifications', ''),
        location=data['location'],
        salary=data['salary'],
        total_vacancy=data['total_vacancy'],
        filled_vacancy=data.get('filled_vacancy', 0),
        status=data['status'],
        form_url=data.get('form_url', ''),
        deadline=deadline,
        created_by=data['created_by']
    )
    
    db.session.add(new_job)
    db.session.commit()
    return jsonify({"message": "Job created successfully!", "id": new_job.job_id}), 201

@app.route('/jobs/<uuid:job_id>', methods=['PUT'])
def update_job(job_id):
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"message": "Job not found"}), 404
    
    data = request.json
    
    # Handle deadline update
    if 'deadline' in data:
        if data['deadline']:
            try:
                job.deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "Invalid deadline format. Use YYYY-MM-DD"}), 400
        else:
            job.deadline = None
    
    # Update other fields (exclude company_name as it's read-only)
    for key, value in data.items():
        if key not in ['deadline', 'company_name']:  # Don't update company_name directly
            setattr(job, key, value)
    
    db.session.commit()
    return jsonify({"message": "Job updated successfully!"})

# == UPDATED JOB DELETE ROUTE (SINGLE) ==
@app.route('/jobs/<uuid:job_id>', methods=['DELETE'])
def delete_job(job_id):
    job = Job.query.get(job_id)
    if not job:
        return jsonify({"message": "Job not found"}), 404
    
    try:
        # Before deleting the job, delete all records from child tables that reference it.
        # This prevents ForeignKeyViolation errors.
        JobApplication.query.filter_by(job_id=job_id).delete(synchronize_session=False)
        Favorite.query.filter_by(job_id=job_id).delete(synchronize_session=False)
        
        # Now it's safe to delete the job itself.
        db.session.delete(job)
        db.session.commit()
        return jsonify({"message": "Job and all related data deleted successfully!", "id": job_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error deleting job: {str(e)}"}), 500


# == UPDATED JOB DELETE ROUTE (BULK) ==
@app.route('/jobs/bulk', methods=['DELETE'])
def delete_jobs_bulk():
    job_ids = request.json.get('ids', [])
    if not job_ids:
        return jsonify({"message": "No IDs provided"}), 400
    
    try:
        # Before bulk deleting jobs, bulk delete all records from child tables.
        JobApplication.query.filter(JobApplication.job_id.in_(job_ids)).delete(synchronize_session=False)
        Favorite.query.filter(Favorite.job_id.in_(job_ids)).delete(synchronize_session=False)
        
        # Now it's safe to bulk delete the jobs.
        num_deleted = Job.query.filter(Job.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"message": f"Deleted {num_deleted} jobs and their related data successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error during bulk job deletion: {str(e)}"}), 500



# =========== BAN / UNBAN ROUTE ===========
@app.route('/users/<uuid:id>', methods=['PUT'])
def update_user_ban_status(id):
    try:
        user = User.query.get(id)
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Extracting is_banned status from request data
        data = request.get_json()
        user.is_banned = data.get('is_banned', user.is_banned)
        
        # Committing the changes to the database
        db.session.commit()
        return jsonify({'message': 'User ban status updated successfully', 'is_banned': user.is_banned}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating user: {str(e)}'}), 500

# Route to update is_banned status for Companies
@app.route('/companies/<uuid:id>', methods=['PUT'])
def update_company_ban_status(id):
    try:
        company = Company.query.get(id)
        if not company:
            return jsonify({'message': 'Company not found'}), 404
        
        # Extracting is_banned status from request data
        data = request.get_json()
        company.is_banned = data.get('is_banned', company.is_banned)
        
        # Committing the changes to the database
        db.session.commit()
        return jsonify({'message': 'Company ban status updated successfully', 'is_banned': company.is_banned}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating company: {str(e)}'}), 500

# ========== DASHBOARD API ==========
'''
@app.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    total_users = User.query.count()
    total_companies = Company.query.count()
    total_jobs = Job.query.count()
    total_applications = JobApplication.query.count()

    trends = []

    # Get the current time in Asia/Kolkata
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    # Get the current time, localized to Kolkata
    now_kolkata = datetime.now(kolkata_tz)

    # Calculate data for the last 9 days
    for i in range(9):
        # Calculate the target date for 'i' days ago, maintaining Kolkata timezone awareness
        target_datetime_kolkata = now_kolkata - timedelta(days=i)

        # Extract the date part (year, month, day) from the Kolkata-aware datetime
        # We then construct naive datetimes for the start/end of THIS specific day in Kolkata time.
        # This assumes your DB stores naive datetimes that represent Kolkata time values.
        start_of_day_kolkata_naive = datetime(
            target_datetime_kolkata.year, target_datetime_kolkata.month, target_datetime_kolkata.day,
            0, 0, 0, 0 # Start of day, set microseconds to 0
        )
        end_of_day_kolkata_naive = datetime(
            target_datetime_kolkata.year, target_datetime_kolkata.month, target_datetime_kolkata.day,
            23, 59, 59, 999999 # End of day, set microseconds to 999999
        )

        # Count applications for the current day
        # Querying directly with naive datetimes that represent Kolkata time
        applications_count = JobApplication.query.filter(
            JobApplication.date_applied >= start_of_day_kolkata_naive,
            JobApplication.date_applied <= end_of_day_kolkata_naive
        ).count()

        # Count new logins (registrations) for the current day
        # Querying directly with naive datetimes that represent Kolkata time
        logins_count = Login.query.filter(
            Login.created_at >= start_of_day_kolkata_naive,
            Login.created_at <= end_of_day_kolkata_naive
        ).count()

        trends.append({
            # The 'x' value should still be the date in Kolkata time for consistent display on frontend.
            "x": target_datetime_kolkata.strftime("%Y-%m-%d"),
            "applications": applications_count,
            "logins": logins_count
        })

    # Reverse the list to have the most recent day last
    trends.reverse()

    return jsonify({
        "metrics": {
            "users": total_users,
            "companies": total_companies,
            "jobs": total_jobs,
            "applications": total_applications
        },
        "trends": trends
    })
'''

@app.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    total_users = User.query.count()
    total_companies = Company.query.count()
    total_jobs = Job.query.count()
    total_applications = JobApplication.query.count()

    range_type = request.args.get('range', 'weekly')  # weekly | monthly | yearly | ten_years

    trends = []

    # Asia/Kolkata time
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    now_kolkata = datetime.now(kolkata_tz)

    def get_counts_for_range(start_naive: datetime, end_naive: datetime):
        applications_count = JobApplication.query.filter(
            JobApplication.date_applied >= start_naive,
            JobApplication.date_applied <= end_naive,
        ).count()

        logins_count = Login.query.filter(
            Login.created_at >= start_naive,
            Login.created_at <= end_naive,
            Login.role != 'admin',
        ).count()

        return applications_count, logins_count

    if range_type == 'monthly':
        # Current month, 4 weekly buckets (1–7, 8–14, 15–21, 22–end)
        year = now_kolkata.year
        month = now_kolkata.month
        days_in_month = calendar.monthrange(year, month)[1]

        for week_idx in range(4):
            start_day = 1 + week_idx * 7
            if start_day > days_in_month:
                break
            end_day = min(start_day + 6, days_in_month)

            start_dt = datetime(year, month, start_day, 0, 0, 0, 0)
            end_dt = datetime(year, month, end_day, 23, 59, 59, 999999)

            applications_count, logins_count = get_counts_for_range(start_dt, end_dt)

            trends.append({
                "x": f"Week {week_idx + 1}",   # Week 1..4
                "applications": applications_count,
                "logins": logins_count,
            })

    elif range_type == 'yearly':
        # Current year, aggregated per month
        year = now_kolkata.year

        for month in range(1, 13):
            start_of_month = datetime(year, month, 1, 0, 0, 0, 0)
            if month == 12:
                end_of_month = datetime(year + 1, 1, 1, 0, 0, 0, 0) - timedelta(microseconds=1)
            else:
                end_of_month = datetime(year, month + 1, 1, 0, 0, 0, 0) - timedelta(microseconds=1)

            applications_count, logins_count = get_counts_for_range(start_of_month, end_of_month)

            trends.append({
                "x": calendar.month_abbr[month],  # Jan, Feb, ...
                "applications": applications_count,
                "logins": logins_count,
            })

    elif range_type == 'ten_years':
        # Last 10 years (inclusive), aggregated per year
        current_year = now_kolkata.year
        start_year = current_year - 9

        for year in range(start_year, current_year + 1):
            start_of_year = datetime(year, 1, 1, 0, 0, 0, 0)
            end_of_year = datetime(year + 1, 1, 1, 0, 0, 0, 0) - timedelta(microseconds=1)

            applications_count, logins_count = get_counts_for_range(start_of_year, end_of_year)

            trends.append({
                "x": str(year),  # e.g., "2016"
                "applications": applications_count,
                "logins": logins_count,
            })

    else:
        # Default: weekly – current calendar week (Mon–Sun)
        days_since_sunday = (now_kolkata.weekday() + 1) % 7
        start_of_week_kolkata = now_kolkata - timedelta(days=days_since_sunday)

        for i in range(7):
            day_kolkata = start_of_week_kolkata + timedelta(days=i)

            start_of_day = datetime(
                day_kolkata.year, day_kolkata.month, day_kolkata.day,
                0, 0, 0, 0,
            )
            end_of_day = datetime(
                day_kolkata.year, day_kolkata.month, day_kolkata.day,
                23, 59, 59, 999999,
            )

            applications_count, logins_count = get_counts_for_range(start_of_day, end_of_day)

            trends.append({
                "x": day_kolkata.strftime("%a"),  # Sun, Mon, ... Sat
                "applications": applications_count,
                "logins": logins_count,
            })

    return jsonify({
        "metrics": {
            "users": total_users,
            "companies": total_companies,
            "jobs": total_jobs,
            "applications": total_applications,
        },
        "trends": trends,
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all() 
    app.run(debug=True)
