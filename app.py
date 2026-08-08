from flask import Flask , render_template, request, redirect, url_for, flash, session
from models import StaffProfile, Trek, db, User
from datetime import datetime, timezone

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
    if "user_id" not in session:
      return redirect(url_for("login"))
    if session.get("role") != "admin":
      flash("Access denied", "error")
      return redirect(url_for("login"))

    treks = Trek.query.all()
    return render_template("admin-treek.html", treks=treks)

@app.route("/add-trek", methods = ["GET", "POST"])
def add_trek():
    if request.method == "GET":

        staff_members = User.query.filter_by(role="staff").all()

        return render_template(
            "add.html",
            staff_members=staff_members
        )


    if request.method == "POST":
      name = request.form.get("name")
      location = request.form.get("location")
      difficulty = request.form.get("difficulty")
      available_slots = int(request.form.get("available_slots"))
      start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
      end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
      duration = int(request.form.get("duration"))
      status = request.form.get("status")
      assigned_staff = request.form.get("assigned_staff")
      description = request.form.get("description")

      if assigned_staff:
         assigned_staff = int(assigned_staff)
      if not name or not location or not difficulty or not available_slots or not start_date or not end_date or not duration:
         flash("Please fill in all fields", "error")
         return redirect(url_for("add_trek"))

      new_trek = Trek(
        name = name,
        location = location,
        difficulty = difficulty,
        available_slots = available_slots,
        start_date = start_date,
        end_date = end_date,
        duration = duration,
        status = status,
        assigned_staff_id = assigned_staff
      )
      db.session.add(new_trek)
      db.session.commit()

      flash("Trek added successfully!", "success")
      return redirect(url_for("admin_treek"))

@app.route("/delete-trek/<int:trek_id>", methods=["POST"])
def delete_trek(trek_id):
    trek = Trek.query.get(trek_id)
    if trek:
        db.session.delete(trek)
        db.session.commit()
        flash("Trek deleted successfully!", "success")
    else:
        flash("Trek not found.", "error")
    return redirect(url_for("admin_treek"))

@app.route("/edit-trek/<int:trek_id>", methods=["GET", "POST"])
def edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    # Get all approved staff
    staff_members = (
        User.query
        .join(StaffProfile)
        .filter(
            User.role == "staff",
            StaffProfile.approved == True
        )
        .all()
    )

    if request.method == "GET":
        return render_template(
            "add.html",
            trek=trek,
            staff_members=staff_members
        )

    trek.name = request.form.get("name")
    trek.location = request.form.get("location")
    trek.difficulty = request.form.get("difficulty")
    trek.available_slots = int(request.form.get("available_slots"))
    trek.start_date = datetime.strptime(
        request.form.get("start_date"),
        "%Y-%m-%d"
    ).date()
    trek.end_date = datetime.strptime(
        request.form.get("end_date"),
        "%Y-%m-%d"
    ).date()
    trek.duration = int(request.form.get("duration"))
    trek.status = request.form.get("status")
    trek.description = request.form.get("description")

    assigned_staff = request.form.get("assigned_staff")

    if assigned_staff:
        trek.assigned_staff_id = int(assigned_staff)
    else:
        trek.assigned_staff_id = None

    db.session.commit()

    flash("Trek updated successfully!", "success")
    return redirect(url_for("admin_treek"))

@app.route("/staff-dashboard")
def staff_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    treks = Trek.query.filter_by(
        assigned_staff_id=session["user_id"]
    ).all()

    assigned_count = len(treks)

    open_treks = Trek.query.filter_by(
        assigned_staff_id=session["user_id"],
        status="Open"
    ).count()

    # We don't have bookings yet
    total_participants = 0

    return render_template(
        "staff-dashboard.html",
        treks=treks,
        assigned_count=assigned_count,
        open_treks=open_treks,
        total_participants=total_participants
    )
@app.route("/user-dashboard")
def user_dashboard():
   if "user_id" not in session:
      return redirect(url_for("login"))
   if session.get("role") != "trekker":
      flash("Access denied", "error")
      return redirect(url_for("login"))
   return render_template("user-dashboard.html")
@app.route("/admin-dashboard")
def admin_dashboard():
    print(session)

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html")

@app.route("/staff-approval")
def staff_approval():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    pending_staff = StaffProfile.query.filter_by(
        approved=False
    ).all()

    return render_template(
        "staff-approval.html",
        pending_staff=pending_staff
    )

@app.route("/approve-staff/<int:staff_id>")
def approve_staff(staff_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    staff = StaffProfile.query.get_or_404(staff_id)

    staff.approved = True

    db.session.commit()

    flash("Staff approved successfully!", "success")

    return redirect(url_for("staff_approval"))

@app.route("/trek-manage/<int:trek_id>")
def manage_trek(trek_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    trek = Trek.query.filter_by(
        id=trek_id,
        assigned_staff_id=session["user_id"]
    ).first_or_404()

    return render_template(
        "manage-trek.html",
        trek=trek
    )

@app.route("/participants/<int:trek_id>")
def view_participants(trek_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "staff":
        flash("Access denied", "error")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    return render_template(
        "staff-participants.html",
        trek=trek
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get_or_404(session["user_id"])

    if request.method == "POST":

        user.username = request.form.get("username")
        user.email = request.form.get("email")
        user.password = request.form.get("password")

        db.session.commit()

        session["username"] = user.username

        flash("Profile updated successfully!", "success")

        return redirect(url_for("profile"))

    return render_template(
        "profile.html",
        user=user
    )



if __name__ == "__main__":
    app.run(debug=True)