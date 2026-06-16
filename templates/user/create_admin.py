from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, Login, Admin

with app.app_context():
    print("Creating admin account...")
    
    admin_login = Login(username='123', role='admin')
    admin_login.set_password('123')
    
    db.session.add(admin_login)
    db.session.commit()
    
    admin_profile = Admin(
        login_id=admin_login.id, 
        name='System Admin', 
        email='admin@myapp.com'
    )
    
    db.session.add(admin_profile)
    db.session.commit()
    
    print("Success! You can now log in with username: '123' and password: '123'")
