from dotenv import load_dotenv
load_dotenv()

from app import app  # Assuming your main file is named app.py
from models import db, Login, Admin

# Create an application context so we can talk to the database
with app.app_context():
    print("Creating admin account...")
    
    # 1. Create the login credentials
    admin_login = Login(username='adi', role='admin')
    admin_login.set_password('adi')  # Your desired password
    
    db.session.add(admin_login)
    db.session.commit()  # Commit to generate the ID
    
    # 2. Create the associated Admin profile
    admin_profile = Admin(
        login_id=admin_login.id, 
        name='System Admin', 
        email='admin@myapp.com'
    )
    
    db.session.add(admin_profile)
    db.session.commit()
    
    print("Success! You can now log in with username: '123' and password: '123'")