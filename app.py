from flask import Flask , render_template, request, redirect, url_for, flash, session
from models import StaffProfile, db, User

app = Flask(__name__)
app.secret_key = "trek_management_secret"

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



@app.route ("/register", methods = ["GET", "POST"])
def register():
   if request.method == "GET":
      return render_template("register.html")
   elif request.method == "POST":
      username = request.form.get("username")
      email = request.form.get("email")
      password = request.form.get("password")
      role = request.form.get("role")


   

      if not username or not email or not password or not role:
         flash("Please fill in all fields", "error")
         return redirect(url_for("register"))

      existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
      if existing_user:
         flash("Username or email already exists", "error")
         return redirect(url_for("register"))

      new_user = User(username=username, email=email, password=password, role=role)
      db.session.add(new_user)
      db.session.commit()

      if role == "staff":
        staff_profile = StaffProfile(user_id=new_user.id, approved = False)
        db.session.add(staff_profile)
        db.session.commit()

      flash("Registration successful! Please log in.", "success")
      return redirect(url_for("login"))
  

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("login.html")

    elif request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        # Find user by email
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("User not found", "error")
            return redirect(url_for("login"))

        # Check password
        if user.password != password:
            flash("Incorrect password", "error")
            return redirect(url_for("login"))

        # Save session
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role

        # Admin Login
        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))

        # Staff Login
        elif user.role == "staff":

            staff_profile = StaffProfile.query.filter_by(user_id=user.id).first()

            if not staff_profile.approved:
                flash("Your account is waiting for admin approval.", "error")
                return redirect(url_for("login"))

            return redirect(url_for("staff_dashboard"))

        # Trekker Login
        elif user.role == "trekker":
            return redirect(url_for("user_dashboard"))
@app.route("/admin-treek")
def admin_treek():
   return render_template("admin-treek.html")

@app.route("/add-trek")
def add_trek():
   return render_template("add.html")

@app.route("/staff-dashboard")
def staff_dashboard():
   if "user_id" not in session:
      return redirect(url_for("login"))
   if session["role"] != "staff":
      flash("Access denied", "error")
      return redirect(url_for("login"))
   return render_template("staff-dashboard.html")  
@app.route("/user-dashboard")
def user_dashboard():
   if "user_id" not in session:
      return redirect(url_for("login"))
   if session["role"] != "trekker":
      flash("Access denied", "error")
      return redirect(url_for("login"))
   return render_template("user-dashboard.html")
@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html")
   

if __name__ == "__main__":
    app.run(debug=True)