from flask import Flask
from models import db, User

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trek.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
  db.create_all()
  admin = User.query.filter_by(username = "admin").first()

  if admin is None:
    admin = User(
        username="admin",
        email="admin@trek.com",
        password="admin123",
        role="admin"
        )

    db.session.add(admin)
    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)