from flask import Blueprint, render_template, request, redirect
from flask import url_for, session, flash, make_response, jsonify
from config import Config
from models import Admin, College, db, User, Job, Login, Company, Login
import re
import random
import string
from extensions import mail
from flask_mail import Message
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps
import uuid
import dns.resolver
from dns.exception import DNSException


auth_blueprint = Blueprint('auth', __name__)

def no_cache(f):
    """Decorator to prevent caching of responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = make_response(f(*args, **kwargs))
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    return decorated_function

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'login_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def secure_route(f):
    """Enhanced decorator that combines login requirement with no-cache headers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session validity first
        if not check_session_validity():
            return redirect(url_for('auth.login'))
        
        # Execute the route function
        response = make_response(f(*args, **kwargs))
        
        # Add comprehensive cache control headers
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['Last-Modified'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        response.headers['ETag'] = '0'
        
        return response
    return decorated_function

def check_session_validity():
    """Check if the current session is valid"""
    if 'login_id' not in session:
        return False
    
    # Verify the login still exists in database
    login = Login.query.filter_by(id=session['login_id']).first()
    if not login:
        session.clear()
        return False
    
    # Check if user is banned (if applicable)
    if login.role == 'user':
        user = User.query.filter_by(login_id=login.id).first()
        if user and user.is_banned:
            session.clear()
            return False
    elif login.role == 'company':
        company = Company.query.filter_by(login_id=login.id).first()
        if company and company.is_banned:
            session.clear()
            return False
    
    return True

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

@auth_blueprint.route('/signup', methods=['GET', 'POST'])
@no_cache
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # confirm_password = request.form.get('confirm_password')
        role = request.form.get('role') # No default to 'user'
        email = request.form['email']

        allowed_roles = ['user', 'company', 'college']
        
        if not role or role not in allowed_roles:
            flash('Please select a valid role (Job Seeker, Company, or College).', 'danger')
            return redirect(url_for('auth.signup'))
        
        if role == 'admin':
            role = 'user'  # Prevent admin signup via this route
        
        # Confirm password check
        '''if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('auth.signup'))'''

        # Forbidden Username Validation
        username_lower = username.lower()
        if username_lower == 'admin' or username_lower == 'administrator':
            flash('The entered username is not allowed. Please choose a different username.', 'danger')
            return redirect(url_for('auth.signup'))
        
        
        # Username length validation
        if not (3 <= len(username) <= 30):
            flash('Username must be between 3 and 30 characters long.', 'danger')
            return redirect(url_for('auth.signup'))
        
        # Username validation
        # Allowed: single word (alphanumeric), email, or 10-digit phone number
        # username_pattern = r'^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-zA-Z]{2,}$|^[a-zA-Z0-9]+$|^[0-9]{10}$'
        username_pattern = r'^(?![0-9]+@)[a-zA-Z0-9]+$|^[0-9]{10}$'
        if not re.match(username_pattern, username):
            flash('Username must be a single word (letters/numbers only) and a valid email.', 'danger')
            return redirect(url_for('auth.signup'))
        if username.startswith('_') or username.startswith('.') or username.endswith('_') or username.endswith('.'):
            flash('Username cannot start or end with an underscore (_) or period (.)', 'danger')
            return redirect(url_for('auth.signup'))
        if ' ' in username:
            flash('Username cannot contain spaces.', 'danger')
            return redirect(url_for('auth.signup'))

        # Password validation
        password = password.strip()
        '''if ' ' in password:
            flash('Password cannot contain spaces.', 'danger')
            return redirect(url_for('auth.signup'))'''
        if not re.match(r'^[a-zA-Z0-9@#$%^&+=]+$', password):
            flash('Password can only contain letters, numbers, and special characters @#$%^&+=', 'danger')
            return redirect(url_for('auth.signup'))
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('auth.signup'))
        if len(password) > 250:
            flash('Password length is too long.', 'danger')
            return redirect(url_for('auth.signup'))
       
        # Email validation
        email_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]{0,63}@[a-zA-Z0-9][a-zA-Z0-9.-]{0,253}\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('Invalid email format. Please use a valid email (e.g., user@domain.com).', 'danger')
            return redirect(url_for('auth.signup'))
        # Additional format checks
        if '..' in email or email.startswith('.') or email.endswith('.'):
            flash('Email format is invalid.', 'danger')
            return redirect(url_for('auth.signup'))
        if len(email) > 90:
            flash('Password length is too long.', 'danger')
            return redirect(url_for('auth.signup'))

        is_valid_domain, domain_error = validate_email_domain(email)
        if not is_valid_domain:
            flash(domain_error, 'danger')
            return redirect(url_for('auth.signup'))

        # Check for existing username or email
        if Login.query.filter(func.lower(Login.username) == username.lower()).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth.signup'))
        if (User.query.filter_by(email=email).first() or 
            Company.query.filter_by(email=email).first() or 
            College.query.filter_by(email=email).first() or 
            Admin.query.filter_by(email=email).first()):
            flash('Email already exists.', 'danger')
            return redirect(url_for('auth.signup'))

        # Create entry in the Login table
        new_login = Login(username=username, role=role)
        new_login.set_password(password)
        db.session.add(new_login)
        db.session.flush()  # Get the login ID

        # Insert role-specific data
        if role == 'user':
            new_user = User(login_id=new_login.id, name=username, email=email)
            db.session.add(new_user)
        elif role == 'company':
            new_company = Company(login_id=new_login.id, company_name=username, email=email)
            db.session.add(new_company)
        elif role == 'college':
            new_college = College(login_id=new_login.id, college_name=username, email=email)
            db.session.add(new_college)
        elif role == 'admin':
            new_admin = Admin(login_id=new_login.id, name=username, email=email)
            db.session.add(new_admin)
            # pass'''
        else:
            flash('Invalid profile type specified.', 'danger')
            return redirect(url_for('auth.signup'))

        db.session.commit()
        flash('Signup successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth_blueprint.route('/clear-history')
def clear_history():
    """Clear browser history and redirect to login"""
    response = make_response(redirect(url_for('auth.login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# For React-Admin integration
@auth_blueprint.route('/api/check-session', methods=['GET'])
def check_api_session():
    """API endpoint for React-Admin to check auth status.
    print(f"DEBUG check-session: session keys = {list(session.keys())}")
    print(f"DEBUG check-session: login_id = {session.get('login_id')}")
    print(f"DEBUG check-session: role = {session.get('role')}")
    print(f"DEBUG check-session: cookies = {request.cookies}")
    """
    if 'admin_login_id' in session and session.get('admin_role') == 'admin':
        # print("DEBUG check-session: AUTHENTICATED ✅")
        return jsonify({'isAuthenticated': True}), 200
    
    # print("DEBUG check-session: NOT AUTHENTICATED ❌")
    return jsonify({'isAuthenticated': False}), 401

# Update your existing login route to include cache control headers
@auth_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Check for API request
        is_api_request = request.headers.get('X-Requested-With') == 'ReactAdmin'
        # print(f"DEBUG: is_api_request = {is_api_request}")
        
        # Handle JSON data from React-Admin
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            # print(f"DEBUG: Received JSON - username='{username}', password='{password}'")
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            # print(f"DEBUG: Received form - username='{username}'")

        # Handle Admin API Login for React-Admin
        if is_api_request and username:
            # print("DEBUG: Entering admin API login flow")
            
            login_user = Login.query.filter_by(username=username, role='admin').first()
            
            if not login_user:
                # print("DEBUG: Admin user NOT FOUND in database")
                return jsonify({'error': 'Admin user not found in database'}), 401
            
            # print(f"DEBUG: Admin user FOUND - id={login_user.id}, username={login_user.username}")
            # print(f"DEBUG: Checking password...")
            
            password_valid = login_user.check_password(password)
            # print(f"DEBUG: Password valid = {password_valid}")
            
            if not password_valid:
                # print("DEBUG: PASSWORD CHECK FAILED")
                return jsonify({'error': 'Invalid credentials'}), 401
            
            # print("DEBUG: Login successful, setting session")
            
            # Set Flask session for admin
            session['admin_login_id'] = login_user.id
            session['admin_username'] = login_user.username
            session['admin_role'] = login_user.role
            session['admin_last_activity'] = datetime.utcnow()
            session['admin_session_token'] = login_user.session_token
            session.permanent = True
            
            # print(f"DEBUG: Session set - login_id={session['login_id']}, role={session['role']}")
            
            # Return simple JSON response (CORS handled by Flask-CORS globally)
            return jsonify({'message': 'Login successful'}), 200
        
        # --- Handle Standard Web Form Logins for All Other Users ---
        login_user = Login.query.filter_by(username=username).first()
        if not login_user or not login_user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))

        # Ban check for user and company roles
        if login_user.role in ['user', 'company']:
            if login_user.role == 'user':
                user = User.query.filter_by(login_id=login_user.id).first()
                if user and user.is_banned:
                    flash("Cannot login. Your account has been suspended.", 'danger')
                    return redirect(url_for('auth.login'))
            elif login_user.role == 'company':
                company = Company.query.filter_by(login_id=login_user.id).first()
                if company and company.is_banned:
                    flash("Cannot login. Your account has been suspended.", 'danger')
                    return redirect(url_for('auth.login'))

        # Store session details for successful login
        session['login_id'] = login_user.id
        session['username'] = login_user.username
        session['role'] = login_user.role
        session['last_activity'] = datetime.utcnow()
        session['session_token'] = login_user.session_token
        session.permanent = True

        # Redirect based on role
        if login_user.role == 'user':
            user = User.query.filter_by(login_id=login_user.id).first()
            if not user:
                flash('User details not found.', 'danger')
                return redirect(url_for('auth.login'))
            session['user_id'] = user.id  
            return redirect(url_for('user.user_dashboard'))
            
        elif login_user.role == 'company':
            company = Company.query.filter_by(login_id=login_user.id).first()
            if not company:
                flash('Company details not found.', 'danger')
                return redirect(url_for('auth.login'))
            return redirect(url_for('company.company_dashboard'))
            
        elif login_user.role == 'college':
            college = College.query.filter_by(login_id=login_user.id).first()
            if not college:
                flash('College details not found.', 'danger')
                return redirect(url_for('auth.login'))
            session['college_id'] = college.id
            return redirect(url_for('college.college_dashboard'))
        
        # Fallback for any other case
        flash('Invalid role for this login portal.', 'danger')
        return redirect(url_for('auth.login'))
    
    # For GET requests
    return render_template('login.html')

@auth_blueprint.route('/logout')
@no_cache
def logout():
    is_api_request = request.headers.get('X-Requested-With') == 'ReactAdmin'
    
    if is_api_request:
        # ✅ Clear only admin-specific session keys
        session.pop('admin_login_id', None)
        session.pop('admin_username', None)
        session.pop('admin_role', None)
        session.pop('admin_last_activity', None)
        session.pop('admin_session_token', None)
        
        response = make_response(jsonify({'message': 'Logged out successfully'}), 200)
        response.delete_cookie('admin_session', domain='127.0.0.1', path='/')
    else:
        # ✅ Clear web module session keys (unchanged)
        session.pop('login_id', None)
        session.pop('username', None)
        session.pop('role', None)
        session.pop('user_id', None)
        session.pop('college_id', None)
        session.pop('company_id', None)
        session.clear()
    
    # For web form requests, redirect with cookie deletion
    response = make_response(redirect(url_for('auth.login')))
    response.delete_cookie('admin_session', domain='127.0.0.1', path='/')
    
    # Add cache control headers
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Last-Modified"] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    response.headers["ETag"] = "0"
    
    return response

@auth_blueprint.route('/forgot-password', methods=['GET', 'POST'])
@no_cache
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if(user is None):
            user = College.query.filter_by(email=email).first()
            if(user is None):
                user=Company.query.filter_by(email=email).first()
                if(user is None):
                    user=Admin.query.filter_by(email=email).first()

        if user:
            otp = ''.join(random.choices(string.digits, k=6))  # Generate OTP
            session['otp'] = otp
            session['email'] = email  # Store email temporarily
            session['otp_time'] = datetime.utcnow().isoformat()  # Store OTP generation time

            # Send OTP via email
            msg = Message("Password Reset OTP", recipients=[email])
            msg.body = f"Your OTP for password reset is: {otp}. It will expire in 10 minutes."
            mail.send(msg)

            flash("OTP has been sent to your email.", "success")
            return redirect(url_for('auth.verify_otp'))
        else:
            flash("Email not found. Please check and try again.", "danger")

    return render_template('forgot_password.html')

@auth_blueprint.route('/verify-otp', methods=['GET', 'POST'])
@no_cache
def verify_otp(): 
    # Check if OTP and OTP time exist in the session
    if 'otp' not in session or 'otp_time' not in session:
        flash("Session expired. Please request a new OTP.", "danger")
        return redirect(url_for('auth.forgot_password'))

    # Get OTP time and calculate remaining time
    otp_time = datetime.fromisoformat(session['otp_time'])
    remaining_time = (otp_time + timedelta(minutes=10)) - datetime.utcnow()

    # If OTP expired
    if remaining_time.total_seconds() <= 0:
        session.pop('otp', None)
        session.pop('otp_time', None)
        flash("OTP expired. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password'))

    # Handle POST request when OTP is entered
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if entered_otp == session.get('otp'):
            return redirect(url_for('auth.reset_password'))
        else:
            flash("Invalid OTP. Please try again.", "danger")

    # Render the verify_otp page and pass remaining time to template
    return render_template('verify_otp.html', remaining_time=int(remaining_time.total_seconds()))

@auth_blueprint.route('/resend-otp', methods=['POST'])
@no_cache
def resend_otp():
    """Resend OTP to user's email if still in forgot-password flow."""
    if 'email' not in session:
        flash("Session expired. Please request a new OTP.", "danger")
        return redirect(url_for('auth.forgot_password'))

    email = session['email']
    user = User.query.filter_by(email=email).first() or \
           College.query.filter_by(email=email).first() or \
           Company.query.filter_by(email=email).first() or \
           Admin.query.filter_by(email=email).first()

    if not user:
        flash("No account found for this email.", "danger")
        return redirect(url_for('auth.forgot_password'))

    # Generate and send new OTP
    otp = ''.join(random.choices(string.digits, k=6))
    session['otp'] = otp
    session['otp_time'] = datetime.utcnow().isoformat()

    msg = Message("Password Reset OTP (Resent)", recipients=[email])
    msg.body = f"Your new OTP for password reset is: {otp}. It will expire in 10 minutes."
    mail.send(msg)

    flash("A new OTP has been sent to your email.", "info")
    return redirect(url_for('auth.verify_otp'))


@auth_blueprint.route('/otp-timer')
@no_cache
def otp_timer():
    """API endpoint to check remaining OTP time."""
    # If OTP time does not exist in the session
    if 'otp_time' not in session:
        return jsonify({'expired': True, 'remaining_time': 0})

    # Get OTP time and calculate remaining time
    otp_time = datetime.fromisoformat(session['otp_time'])
    remaining_time = (otp_time + timedelta(minutes=10)) - datetime.utcnow()

    # If OTP expired
    if remaining_time.total_seconds() <= 0:
        session.pop('otp', None)
        session.pop('otp_time', None)
        return jsonify({'expired': True, 'remaining_time': 0})

    # Return remaining time if OTP is still valid
    return jsonify({'expired': False, 'remaining_time': int(remaining_time.total_seconds())})

# Password Reset Route
@auth_blueprint.route('/reset-password', methods=['GET', 'POST'])
@no_cache
def reset_password():
    if 'email' not in session:
        flash("Session expired. Please request a new OTP.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Validate password
        if new_password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('auth.reset_password'))

        if ' ' in new_password:
            flash('Password cannot contain spaces.', 'danger')
            return redirect(url_for('auth.reset_password'))

        if not re.match(r'^[a-zA-Z0-9@#$%^&+=]+$', new_password):
            flash('Password can only contain letters, numbers, and special characters @#$%^&+=', 'danger')
            return redirect(url_for('auth.reset_password'))

        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('auth.reset_password'))

        # Hash password
        hashed_password = generate_password_hash(new_password)

        # Find user by email
        email = session.get('email')
        user = User.query.filter_by(email=email).first() or \
               College.query.filter_by(email=email).first() or \
               Company.query.filter_by(email=email).first() or \
               Admin.query.filter_by(email=email).first()

        if user:
            # Get the corresponding Login entry
            login_entry = Login.query.filter_by(id=user.login_id).first()
            if login_entry:
                login_entry.password_hash = hashed_password
                login_entry.session_token = uuid.uuid4()
                db.session.commit()

                # Clear session data
                session.pop('email', None)
                session.pop('otp', None)

                flash("Password reset successful! You can now log in.", "success")
                return redirect(url_for('auth.login'))

        flash("Error resetting password. Please try again.", "danger")

    return render_template('reset_password.html')