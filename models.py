from flask_sqlalchemy import SQLAlchemy
from datetime import UTC, datetime

db = SQLAlchemy()

class User(db.Model):
  __tablename__ = 'users'
  id = db.Column(db.Integer, primary_key = True)
  username = db.Column(db.String(50), nullable = False, unique = True)
  email = db.Column(db.String(120), unique = True , nullable = False)
  password = db.Column(db.String(220),nullable = False)
  role = db.Column(db.String(90), nullable = False)
  is_active = db.Column(db.Boolean, default = True)
  created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

  def __repr__(self):
    return f"user {self.username}"

class StaffProfile(db.Model):
  __tablename__ = 'staff_profiles'
  id = db.Column(db.Integer, primary_key = True)

  user_id = db.Column(
    db.Integer,
    db.ForeignKey("users.id"),
    unique = True,
    nullable = False
  )
  phone = db.Column(db.String(15))
  experience = db.Column(db.Integer)
  approved = db.Column(db.Boolean, default=False)
  user = db.relationship(
    "User",
    backref=db.backref("staff_profile", uselist=False, cascade="all, delete-orphan")
  )

  def __repr__(self):
    return f"staff {self.user_id}"

class Trek(db.Model):
  __tablename__ = 'treks'
  id = db.Column(db.Integer, primary_key = True)
  name = db.Column(db.String(50), nullable = False)
  location = db.Column(db.String(100), nullable = False)
  difficulty = db.Column(db.String(20), nullable = False)
  available_slots = db.Column(db.Integer, nullable = False)
  status = db.Column(db.String(20), default = "Open")
  start_date = db.Column(db.Date, nullable = False)
  end_date = db.Column(db.Date, nullable = False)
  description = db.Column(db.Text)
  duration = db.Column(db.Integer, nullable = False)
  created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

  assigned_staff_id = db.Column(
  db.Integer,
  db.ForeignKey("users.id")
  )


  assigned_staff = db.relationship(
  "User",
  backref="treks"
  )

  def __repr__(self):
    return f"trek{self.name}"
  
class Booking(db.Model):
  __tablename__ = "bookings"
  __table_args__ = (
    db.UniqueConstraint("user_id", "trek_id", name="uq_user_trek_booking"),
  )
  id = db.Column(db.Integer, primary_key = True)
  user_id = db.Column(
    db.Integer,
    db.ForeignKey("users.id"),
    nullable = False
  )
  trek_id = db.Column(
    db.Integer,
    db.ForeignKey("treks.id"),
    nullable = False
  )
  booking_date = db.Column(db.DateTime, default=lambda:datetime.now(UTC))
  booking_status = db.Column(db.String(50), default="Pending")
  payment_status = db.Column(db.String(50), default="Pending")
  user = db.relationship("User", backref="bookings")
  trek = db.relationship("Trek", backref="bookings")

  def __repr__(self):
    return f"<Booking {self.id}>"
