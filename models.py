import uuid
from datetime import datetime
# import pytz
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Uuid
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
from enum import Enum

class RoleEnum(Enum):
    user = "user"
    admin = "admin"
    company = "company"
    college="college"


# Login Table
class Login(db.Model):
    __tablename__ = 'logins'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('user', 'company', 'admin', 'college', name='role_enum'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session_token = db.Column(Uuid, default=uuid.uuid4, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Login {self.username}>'


# College Table
class College(db.Model):
    __tablename__ = 'college'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_id = db.Column(Uuid, db.ForeignKey('logins.id'), nullable=False, unique=True)
    college_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    website = db.Column(db.Text)
    logo = db.Column(db.Text)
    description = db.Column(db.Text)
    is_banned = db.Column(db.Boolean, default = False)
    created_at = db.Column(db.DateTime,default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    login = db.relationship('Login', backref=db.backref('college', uselist=False, cascade='all, delete'))

    def __repr__(self):
        return f'<College {self.college_name}>'
    

# User Table
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_id = db.Column(Uuid, db.ForeignKey('logins.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    phone = db.Column(db.String(15))
    age = db.Column(db.Integer)
    about_me = db.Column(db.Text)
    profile_picture = db.Column(db.Text)
    college_name = db.Column(db.String(255))  # To store connected college name or manual value.
    created_at = db.Column(db.DateTime,default=datetime.utcnow) # default=datetime.now(pytz.timezone('Asia/Kolkata'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_banned = db.Column(db.Boolean, default = False)

    login = db.relationship('Login', backref=db.backref('user', uselist=False, cascade='all, delete'))
    
    def __repr__(self):
        return f'<User {self.email}>'


# Company Table
class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_id = db.Column(Uuid, db.ForeignKey('logins.id'), nullable=False, unique=True)
    company_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    website = db.Column(db.Text)
    logo = db.Column(db.Text)
    description = db.Column(db.Text)
    industry = db.Column(db.Text)
    is_banned = db.Column(db.Boolean, default = False)
    created_at = db.Column(db.DateTime,default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    login = db.relationship('Login', backref=db.backref('company', uselist=False, cascade='all, delete'))

    def __repr__(self):
        return f'<Company {self.company_name}>'


# Admin Table
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_id = db.Column(Uuid, db.ForeignKey('logins.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime,default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    login = db.relationship('Login', backref=db.backref('admin', uselist=False, cascade='all, delete'))

    def __repr__(self):
        return f'<Admin {self.name}>'


# Job Table
class Job(db.Model):
    __tablename__ = 'jobs'

    job_id = db.Column(Uuid, primary_key=True, default=uuid.uuid4, unique=True)
    title = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=False)
    job_type = db.Column(db.String(20), nullable=False)  # full-time, part-time, contract, internship
    skills = db.Column(db.Text)
    years_of_exp = db.Column(db.Integer, nullable=False)
    certifications = db.Column(db.Text)
    location = db.Column(db.Text)
    salary = db.Column(db.String(50))
    total_vacancy = db.Column(db.Integer, nullable=False)
    filled_vacancy = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    form_url = db.Column(db.Text)  # To store the Google Form link
    deadline = db.Column(db.Date)
    created_at = db.Column(db.DateTime,default=datetime.utcnow) #default=datetime.now(pytz.timezone('Asia/Kolkata')))
    created_by = db.Column(Uuid, db.ForeignKey('logins.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with User (if needed)
    user = db.relationship('Login', backref=db.backref('jobs', lazy=True))

    def __init__(self, title, description, job_type, skills, years_of_exp, certifications, location, salary, 
    total_vacancy, filled_vacancy, status, form_url, deadline, created_by, job_id=None):
        self.title = title
        self.description = description
        self.job_type = job_type
        self.skills = skills
        self.years_of_exp = years_of_exp
        self.certifications = certifications
        self.location = location
        self.salary = salary
        self.total_vacancy = total_vacancy
        self.filled_vacancy = filled_vacancy
        self.status = status
        self.form_url = form_url
        self.deadline = deadline
        self.created_by = created_by
        if job_id is not None:
            self.job_id = job_id

    def to_dict(self):
        return {
            'job_id': str(self.job_id),
            'title': self.title,
            'description': self.description,
            'job_type': self.job_type,
            'skills': self.skills,
            'years_of_exp': self.years_of_exp,
            'certifications': self.certifications,
            'location': self.location,
            'salary': self.salary,
            'total_vacancy': self.total_vacancy,
            'filled_vacancy': self.filled_vacancy,
            'status': self.status,
            'form_url': self.form_url,
            'deadline': self.deadline.strftime('%Y-%m-%d %H:%M:%S') if self.deadline else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'created_by': str(self.created_by)
        }


# Job Application Table
class JobApplication(db.Model):
    __tablename__ = 'job_applications'

    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(Uuid, db.ForeignKey('jobs.job_id'), nullable=False)
    status = db.Column(db.String(20), default='Pending')  # 'pending', 'accepted', 'rejected'
    resume_path = db.Column(db.Text, nullable=True)  # Store path to the resume file
    date_applied = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Timestamp when application is submitted
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Timestamp when status is changed

    # Relationships
    user = db.relationship('User', backref='applications')
    job = db.relationship('Job', backref='applications')

    def __init__(self, user_id, job_id, status='Pending', resume_path=None):
        self.user_id = user_id
        self.job_id = job_id
        self.status = status
        self.resume_path = resume_path
        self.date_applied = datetime.utcnow()
        self.status_updated_at = datetime.utcnow()

# Communication Table
class Communication(db.Model):
    __tablename__ = 'communications'

    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.login_id'))
    college_id = db.Column(Uuid, db.ForeignKey('college.login_id'))
    company_id = db.Column(Uuid, db.ForeignKey('companies.login_id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read_status = db.Column(db.Boolean, nullable=False, default=False)
    hidden = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', backref=db.backref('communications', lazy=True))
    company = db.relationship('Company', backref=db.backref('communications', lazy=True))

    def __init__(self, user_id, college_id, company_id, message):
        self.user_id = user_id
        self.college_id = college_id
        self.company_id = company_id
        self.message = message


# Notification Table
class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.login_id'), nullable=False)
    company_id = db.Column(Uuid, db.ForeignKey('companies.login_id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    read_status = db.Column(db.Boolean, nullable=False, default=False)
    hidden = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('Company', backref='notifications')
    
    def __init__(self, user_id, company_id, message):
        self.user_id = user_id
        self.company_id = company_id
        self.message = message


# Resume Certification Table
class ResumeCertification(db.Model):
    __tablename__ = 'resume_certifications'

    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.id'), nullable=False)
    resume_path = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    certifications = db.relationship('Certification', backref='resume_cert', lazy=True)

    def __repr__(self):
        return f'<ResumeCertification User ID: {self.user_id}>'


# Certification Table
class Certification(db.Model):
    __tablename__ = 'certifications'

    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.id'), nullable=False)
    resume_cert_id = db.Column(Uuid, db.ForeignKey('resume_certifications.id'), nullable=True)
    certification_name = db.Column(db.String(255), nullable=False)
    verification_status = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Certification {self.certification_name} for User ID: {self.user_id}>'


# Coupon Table
class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    code = db.Column(db.String(10), unique=True, nullable=False)
    faculty_id = db.Column(db.String(20), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    college_id = db.Column(Uuid, db.ForeignKey('college.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    college = db.relationship('College', backref=db.backref('coupons', lazy=True))

    def __repr__(self):
        return f"<Coupon {self.code}>"


# Coupon User Table
class Couponuser(db.Model):
    __tablename__ = 'couponuser'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.id'), nullable=False)
    coupon_id = db.Column(Uuid, db.ForeignKey('coupons.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    college = db.relationship('Coupon', backref=db.backref('couponuser', lazy=True))
    user = db.relationship('User', backref=db.backref('couponuser', lazy=True))
    
    def __repr__(self):
        return f"<CouponUser User ID: {self.user_id}, Coupon ID: {self.coupon_id}>"

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(Uuid, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(Uuid, db.ForeignKey('jobs.job_id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('favorites', lazy=True))
    job = db.relationship('Job', backref=db.backref('favorited_by', lazy=True))