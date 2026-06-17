# Database Migration

```sql
flask db init
flask db migrate -m "name"
flask db upgrade
```
use this command in mysql - ALTER TABLE jobs MODIFY COLUMN job_id INT AUTO_INCREMENT PRIMARY KEY;

# .env file format:

```
DATABASE_URL = postgresql://user:password@localhost:5432/database_name
SECRET_KEY =
MAIL_USERNAME =
```
