from flask import Flask
from models.models import db, User
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydatabase.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def create_admin_user():
  admin_email = 'admin@example.com'
  admin_user = User.query.filter_by(email=admin_email).first()

  if not admin_user:
    admin_user = 'admin'
    hashed_password = generate_password_hash('adminpassword', method='pbkdf2:sha256', salt_length=8)

    admin_user = User(
      username=admin_user,
      password=hashed_password,
      status='approved',
      roles='admin'
    )

    db.session.add(admin_user)
    db.session.commit()
    print('Admin user created successfully.' )
  else:
    print('Admin user already exists.')

  with app.app_context():
    db.create_all()
    create_admin_user()

  if __name__ == '__main__':
    app.run(debug=True)