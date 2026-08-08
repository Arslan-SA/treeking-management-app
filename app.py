from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from models import Booking, StaffProfile, Trek, User, db


ADMIN_EMAIL = "admin@trek.com"
ADMIN_PASSWORD = "admin123"
TREK_STATUSES = ["Pending", "Approved", "Open", "Closed", "Completed"]
STAFF_TREK_STATUSES = ["Open", "Closed", "Ongoing", "Completed"]
BOOKING_STATUSES = ["Booked", "Cancelled", "Completed"]


app = Flask(__name__)
app.secret_key = "trek_management_secret"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trek.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def verify_password(user, password):
    if user.password.startswith("scrypt:") or user.password.startswith("pbkdf2:"):
        return check_password_hash(user.password, password)
    return user.password == password


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            user = User.query.get(session["user_id"])
            if not user or not user.is_active:
                session.clear()
                flash("Your account is inactive. Contact the administrator.", "error")
                return redirect(url_for("login"))

            if role and user.role != role:
                flash("Access denied", "error")
                return redirect(url_for("login"))

            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user():
    if "user_id" not in session:
        return None
    return User.query.get(session["user_id"])


def seed_admin():
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    password_hash = generate_password_hash(ADMIN_PASSWORD)

    if admin is None:
        db.session.add(
            User(
                username="admin",
                email=ADMIN_EMAIL,
                password=password_hash,
                role="admin",
                is_active=True,
            )
        )
    else:
        admin.role = "admin"
        admin.username = "admin"
        admin.password = password_hash
        admin.is_active = True

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_admin()


@app.route("/")
def index():
    if "role" in session:
        return redirect(url_for(f"{session['role']}_dashboard" if session["role"] != "trekker" else "user_dashboard"))
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role")
    phone = request.form.get("phone", "").strip()
    experience = request.form.get("experience", type=int)

    if role not in ["trekker", "staff"]:
        flash("Only trekkers and trek staff can register.", "error")
        return redirect(url_for("register"))

    if not username or not email or not password:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("register"))

    existing_user = User.query.filter(or_(User.username == username, User.email == email)).first()
    if existing_user:
        flash("Username or email already exists.", "error")
        return redirect(url_for("register"))

    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role=role,
        is_active=True,
    )
    db.session.add(new_user)
    db.session.flush()

    if role == "staff":
        db.session.add(
            StaffProfile(
                user_id=new_user.id,
                phone=phone or None,
                experience=experience,
                approved=False,
            )
        )

    db.session.commit()

    if role == "staff":
        flash("Registration successful. Admin approval is required before login.", "success")
    else:
        flash("Registration successful! Please log in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = User.query.filter_by(email=email).first()

    if not user or not verify_password(user, password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    if not user.is_active:
        flash("Your account is inactive. Contact the administrator.", "error")
        return redirect(url_for("login"))

    if user.role == "staff":
        staff_profile = StaffProfile.query.filter_by(user_id=user.id).first()
        if not staff_profile or not staff_profile.approved:
            flash("Your account is waiting for admin approval.", "error")
            return redirect(url_for("login"))

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role

    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if user.role == "staff":
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.route("/admin-dashboard")
@login_required("admin")
def admin_dashboard():
    stats = {
        "total_treks": Trek.query.count(),
        "total_users": User.query.filter_by(role="trekker").count(),
        "total_staff": User.query.filter_by(role="staff").count(),
        "total_bookings": Booking.query.count(),
    }
    recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(8).all()
    return render_template("admin_dashboard.html", stats=stats, recent_bookings=recent_bookings)


@app.route("/admin-treek")
@login_required("admin")
def admin_treek():
    search = request.args.get("search", "").strip()
    query = Trek.query

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Trek.name.ilike(like), Trek.location.ilike(like), Trek.id.cast(db.String).ilike(like)))

    treks = query.order_by(Trek.created_at.desc()).all()
    return render_template("admin-treek.html", treks=treks, search=search)


@app.route("/add-trek", methods=["GET", "POST"])
@login_required("admin")
def add_trek():
    staff_members = (
        User.query.join(StaffProfile)
        .filter(User.role == "staff", User.is_active.is_(True), StaffProfile.approved.is_(True))
        .order_by(User.username)
        .all()
    )

    if request.method == "GET":
        return render_template("add.html", staff_members=staff_members, statuses=TREK_STATUSES)

    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    difficulty = request.form.get("difficulty", "").strip()
    available_slots = request.form.get("available_slots", type=int)
    duration = request.form.get("duration", type=int)
    status = request.form.get("status", "Pending")
    assigned_staff = request.form.get("assigned_staff", type=int)
    description = request.form.get("description", "").strip()

    try:
        start_date = datetime.strptime(request.form.get("start_date", ""), "%Y-%m-%d").date()
        end_date = datetime.strptime(request.form.get("end_date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Please provide valid start and end dates.", "error")
        return redirect(url_for("add_trek"))

    if not name or not location or not difficulty or available_slots is None or duration is None:
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("add_trek"))

    if available_slots < 0 or duration <= 0:
        flash("Slots must be zero or more and duration must be positive.", "error")
        return redirect(url_for("add_trek"))

    if status not in TREK_STATUSES:
        status = "Pending"

    db.session.add(
        Trek(
            name=name,
            location=location,
            difficulty=difficulty,
            available_slots=available_slots,
            start_date=start_date,
            end_date=end_date,
            duration=duration,
            status=status,
            assigned_staff_id=assigned_staff,
            description=description,
        )
    )
    db.session.commit()

    flash("Trek added successfully!", "success")
    return redirect(url_for("admin_treek"))


@app.route("/delete-trek/<int:trek_id>", methods=["POST"])
@login_required("admin")
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    Booking.query.filter_by(trek_id=trek.id).delete()
    db.session.delete(trek)
    db.session.commit()
    flash("Trek deleted successfully!", "success")
    return redirect(url_for("admin_treek"))


@app.route("/edit-trek/<int:trek_id>", methods=["GET", "POST"])
@login_required("admin")
def edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_members = (
        User.query.join(StaffProfile)
        .filter(User.role == "staff", User.is_active.is_(True), StaffProfile.approved.is_(True))
        .order_by(User.username)
        .all()
    )

    if request.method == "GET":
        return render_template("add.html", trek=trek, staff_members=staff_members, statuses=TREK_STATUSES)

    trek.name = request.form.get("name", "").strip()
    trek.location = request.form.get("location", "").strip()
    trek.difficulty = request.form.get("difficulty", "").strip()
    trek.available_slots = request.form.get("available_slots", type=int)
    trek.start_date = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date()
    trek.end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()
    trek.duration = request.form.get("duration", type=int)
    trek.status = request.form.get("status") if request.form.get("status") in TREK_STATUSES else trek.status
    trek.description = request.form.get("description", "").strip()
    trek.assigned_staff_id = request.form.get("assigned_staff", type=int)

    db.session.commit()
    flash("Trek updated successfully!", "success")
    return redirect(url_for("admin_treek"))


@app.route("/staff-approval")
@login_required("admin")
def staff_approval():
    pending_staff = StaffProfile.query.join(User).filter(StaffProfile.approved.is_(False), User.is_active.is_(True)).all()
    return render_template("staff-approval.html", pending_staff=pending_staff)


@app.route("/approve-staff/<int:staff_id>", methods=["POST"])
@login_required("admin")
def approve_staff(staff_id):
    staff = StaffProfile.query.get_or_404(staff_id)
    staff.approved = True
    staff.user.is_active = True
    db.session.commit()
    flash("Staff approved successfully!", "success")
    return redirect(url_for("staff_approval"))


@app.route("/reject-staff/<int:staff_id>", methods=["POST"])
@login_required("admin")
def reject_staff(staff_id):
    staff = StaffProfile.query.get_or_404(staff_id)
    staff.user.is_active = False
    staff.approved = False
    db.session.commit()
    flash("Staff request rejected and account deactivated.", "success")
    return redirect(url_for("staff_approval"))


@app.route("/admin-users")
@login_required("admin")
def admin_users():
    search = request.args.get("search", "").strip()
    query = User.query.filter(User.role == "trekker")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.username.ilike(like), User.email.ilike(like), User.id.cast(db.String).ilike(like)))
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin-users.html", users=users, search=search)


@app.route("/admin-staff")
@login_required("admin")
def admin_staff():
    search = request.args.get("search", "").strip()
    query = User.query.outerjoin(StaffProfile).filter(User.role == "staff")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.username.ilike(like), User.email.ilike(like), User.id.cast(db.String).ilike(like)))
    staff_members = query.order_by(User.created_at.desc()).all()
    return render_template("admin-staff.html", staff_members=staff_members, search=search)


@app.route("/toggle-user/<int:user_id>", methods=["POST"])
@login_required("admin")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Admin account cannot be deactivated.", "error")
        return redirect(url_for("admin_dashboard"))

    user.is_active = not user.is_active
    db.session.commit()
    flash(f"{user.username} is now {'active' if user.is_active else 'inactive'}.", "success")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/delete-staff/<int:user_id>", methods=["POST"])
@login_required("admin")
def delete_staff(user_id):
    staff = User.query.filter_by(id=user_id, role="staff").first_or_404()
    for trek in staff.treks:
        trek.assigned_staff_id = None
    StaffProfile.query.filter_by(user_id=staff.id).delete()
    db.session.delete(staff)
    db.session.commit()
    flash("Staff removed successfully.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin-bookings")
@login_required("admin")
def admin_bookings():
    search = request.args.get("search", "").strip()
    query = Booking.query.join(User).join(Trek)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Booking.id.cast(db.String).ilike(like),
                User.username.ilike(like),
                User.email.ilike(like),
                Trek.name.ilike(like),
                Trek.id.cast(db.String).ilike(like),
            )
        )
    bookings = query.order_by(Booking.booking_date.desc()).all()
    return render_template("admin-bookings.html", bookings=bookings, search=search)


@app.route("/admin-booking/<int:booking_id>/status", methods=["POST"])
@login_required("admin")
def admin_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    status = request.form.get("booking_status")
    if status not in BOOKING_STATUSES:
        flash("Invalid booking status.", "error")
        return redirect(url_for("admin_bookings"))

    if booking.booking_status == "Cancelled" and status == "Booked":
        if booking.trek.available_slots <= 0 or booking.trek.status != "Open":
            flash("Cannot restore booking when slots are full or trek is closed.", "error")
            return redirect(url_for("admin_bookings"))
        booking.trek.available_slots -= 1
    if booking.booking_status != "Cancelled" and status == "Cancelled":
        booking.trek.available_slots += 1

    booking.booking_status = status
    db.session.commit()
    flash("Booking status updated.", "success")
    return redirect(url_for("admin_bookings"))


@app.route("/admin-search")
@login_required("admin")
def admin_search():
    search = request.args.get("search", "").strip()
    results = {"treks": [], "users": [], "staff": []}
    if search:
        like = f"%{search}%"
        results["treks"] = Trek.query.filter(or_(Trek.name.ilike(like), Trek.id.cast(db.String).ilike(like))).all()
        results["users"] = User.query.filter(
            User.role == "trekker",
            or_(User.username.ilike(like), User.email.ilike(like), User.id.cast(db.String).ilike(like)),
        ).all()
        results["staff"] = User.query.filter(
            User.role == "staff",
            or_(User.username.ilike(like), User.email.ilike(like), User.id.cast(db.String).ilike(like)),
        ).all()
    return render_template("admin-search.html", search=search, results=results)


@app.route("/staff-dashboard")
@login_required("staff")
def staff_dashboard():
    treks = Trek.query.filter_by(assigned_staff_id=session["user_id"]).order_by(Trek.start_date).all()
    assigned_count = len(treks)
    open_treks = sum(1 for trek in treks if trek.status == "Open")
    total_participants = sum(len([booking for booking in trek.bookings if booking.booking_status != "Cancelled"]) for trek in treks)

    return render_template(
        "staff-dashboard.html",
        treks=treks,
        assigned_count=assigned_count,
        open_treks=open_treks,
        total_participants=total_participants,
    )


@app.route("/trek-manage/<int:trek_id>", methods=["GET", "POST"])
@login_required("staff")
def manage_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != session["user_id"]:
        flash("You are not assigned to this trek.", "error")
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        available_slots = request.form.get("available_slots", type=int)
        status = request.form.get("status")

        if available_slots is None or available_slots < 0:
            flash("Invalid number of slots.", "error")
            return redirect(url_for("manage_trek", trek_id=trek.id))

        if status not in STAFF_TREK_STATUSES:
            flash("Invalid trek status.", "error")
            return redirect(url_for("manage_trek", trek_id=trek.id))

        trek.available_slots = available_slots
        trek.status = status

        if status == "Completed":
            for booking in trek.bookings:
                if booking.booking_status == "Booked":
                    booking.booking_status = "Completed"

        db.session.commit()
        flash("Trek updated successfully!", "success")
        return redirect(url_for("manage_trek", trek_id=trek.id))

    return render_template("manage-trek.html", trek=trek, statuses=STAFF_TREK_STATUSES)


@app.route("/participants/<int:trek_id>")
@login_required("staff")
def view_participants(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.assigned_staff_id != session["user_id"]:
        flash("You are not assigned to this trek.", "error")
        return redirect(url_for("staff_dashboard"))
    return render_template("staff-participants.html", trek=trek)


@app.route("/staff-booking/<int:booking_id>/status", methods=["POST"])
@login_required("staff")
def staff_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.trek.assigned_staff_id != session["user_id"]:
        flash("You can manage only your assigned trek records.", "error")
        return redirect(url_for("staff_dashboard"))

    status = request.form.get("booking_status")
    if status not in BOOKING_STATUSES:
        flash("Invalid booking status.", "error")
        return redirect(url_for("view_participants", trek_id=booking.trek_id))

    if booking.booking_status != "Cancelled" and status == "Cancelled":
        booking.trek.available_slots += 1
    elif booking.booking_status == "Cancelled" and status == "Booked":
        if booking.trek.available_slots <= 0 or booking.trek.status != "Open":
            flash("Cannot restore booking when slots are full or trek is closed.", "error")
            return redirect(url_for("view_participants", trek_id=booking.trek_id))
        booking.trek.available_slots -= 1

    booking.booking_status = status
    db.session.commit()
    flash("Participant booking status updated.", "success")
    return redirect(url_for("view_participants", trek_id=booking.trek_id))


@app.route("/user-dashboard")
@login_required("trekker")
def user_dashboard():
    difficulty = request.args.get("difficulty", "").strip()
    location = request.args.get("location", "").strip()

    query = Trek.query.filter(Trek.status == "Open", Trek.available_slots > 0)
    if difficulty:
        query = query.filter(Trek.difficulty == difficulty)
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))

    treks = query.order_by(Trek.start_date).all()
    my_bookings = (
        Booking.query.filter_by(user_id=session["user_id"])
        .order_by(Booking.booking_date.desc())
        .all()
    )

    return render_template(
        "user-dashboard.html",
        treks=treks,
        my_bookings=my_bookings,
        difficulty=difficulty,
        location=location,
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required()
def profile():
    user = current_user()
    staff_profile = StaffProfile.query.filter_by(user_id=user.id).first() if user.role == "staff" else None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email:
            flash("Username and email are required.", "error")
            return redirect(url_for("profile"))

        existing_user = User.query.filter(User.id != user.id, or_(User.username == username, User.email == email)).first()
        if existing_user:
            flash("Username or email already exists.", "error")
            return redirect(url_for("profile"))

        user.username = username
        user.email = email
        if password:
            user.password = generate_password_hash(password)

        if staff_profile:
            staff_profile.phone = request.form.get("phone", "").strip() or None
            staff_profile.experience = request.form.get("experience", type=int)

        db.session.commit()
        session["username"] = user.username
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user, staff_profile=staff_profile)


@app.route("/my-bookings")
@login_required("trekker")
def my_bookings():
    bookings = (
        Booking.query.filter_by(user_id=session["user_id"])
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return render_template("my-bookings.html", bookings=bookings)


@app.route("/book-trek/<int:trek_id>")
@login_required("trekker")
def book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    return render_template("book-trek.html", trek=trek)


@app.route("/confirm-booking/<int:trek_id>", methods=["POST"])
@login_required("trekker")
def confirm_booking(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if trek.status != "Open":
        flash("This trek is not open for booking.", "error")
        return redirect(url_for("book_trek", trek_id=trek.id))

    if trek.available_slots <= 0:
        flash("No slots available.", "error")
        return redirect(url_for("book_trek", trek_id=trek.id))

    existing_booking = Booking.query.filter_by(user_id=session["user_id"], trek_id=trek.id).first()

    if existing_booking:
        flash("You have already booked this trek.", "warning")
        return redirect(url_for("my_bookings"))

    db.session.add(
        Booking(
            user_id=session["user_id"],
            trek_id=trek.id,
            booking_status="Booked",
            payment_status="Pending",
        )
    )
    trek.available_slots -= 1
    db.session.commit()

    flash("Booking successful!", "success")
    return redirect(url_for("my_bookings"))


@app.route("/booking/<int:booking_id>")
@login_required()
def booking_details(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    role = session.get("role")

    if role == "trekker" and booking.user_id != session["user_id"]:
        flash("Access denied", "error")
        return redirect(url_for("my_bookings"))
    if role == "staff" and booking.trek.assigned_staff_id != session["user_id"]:
        flash("Access denied", "error")
        return redirect(url_for("staff_dashboard"))

    return render_template("booking-details.html", booking=booking)


@app.route("/cancel-booking/<int:booking_id>", methods=["POST"])
@login_required("trekker")
def cancel_booking(booking_id):
    booking = Booking.query.filter_by(id=booking_id, user_id=session["user_id"]).first_or_404()
    if booking.booking_status != "Booked":
        flash("Only booked treks can be cancelled.", "error")
        return redirect(url_for("my_bookings"))

    booking.booking_status = "Cancelled"
    booking.trek.available_slots += 1
    db.session.commit()
    flash("Booking cancelled.", "success")
    return redirect(url_for("my_bookings"))


if __name__ == "__main__":
    app.run(debug=True)
