from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import re
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

# MongoDB Setup
import os
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/faculty_desk")

mongo = PyMongo(app)

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return 'About Us Page'


@app.route('/faculties')
def faculties():
    return 'Faculties Page'


@app.route('/contact')
def contact():
    return 'Contact Page'


@app.route('/login')
def login():
    return render_template("login.html")


@app.route('/home')
def admin():
    return render_template('home.html')


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        department_name = request.form["department"]
        profile_img = request.files.get("profile_img")

        # Email format validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            flash("⚠️ Invalid email format. Use something like example@domain.com", "danger")
            return redirect(url_for("signup"))

        # Determine faculty status based on role and checkbox
        if role == "faculty":
            is_faculty = True
        else:
            is_faculty = request.form.get("is_faculty_checkbox") == "yes"

        # Create or get department
        department = mongo.db.departments.find_one({"name": department_name})
        if not department:
            department_id = mongo.db.departments.insert_one({
                "name": department_name,
                "short_name": department_name[:3].upper()
            }).inserted_id
        else:
            department_id = department["_id"]

        # Check for existing user
        existing_user = mongo.db.users.find_one({"email": email})
        if existing_user:
            flash("⚠️ User already exists!", "danger")
            return redirect(url_for("signup"))

        # Password validation
        if (
                len(password) < 8 or
                not re.search(r"[A-Z]", password) or
                not re.search(r"[0-9]", password) or
                not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
        ):
            flash(
                "⚠️ Password must be at least 8 characters long and include an uppercase letter, a number, and a special character.",
                "danger")
            return redirect(url_for("signup"))

        # Handle image upload
        profile_img_path = None
        if profile_img and allowed_file(profile_img.filename):
            filename = secure_filename(f"{email}_{profile_img.filename}")
            profile_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            profile_img_path = filename

        # Hash and save user
        hashed_pw = generate_password_hash(password)
        user_data = {
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": role,
            "is_faculty": is_faculty,
            "department_id": department_id
        }

        if profile_img_path:
            user_data["profile_img"] = profile_img_path

        mongo.db.users.insert_one(user_data)

        flash("✅ Registered successfully! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/teacher_login", methods=["POST"])
def teacher_login():
    email = request.form["email"]
    password = request.form["password"]

    user = mongo.db.users.find_one({"email": email})

    if user and check_password_hash(user["password"], password):
        if user["role"] == "faculty" or user.get("is_faculty", False):
            session['email'] = email
            session['role'] = "faculty"
            return redirect(url_for('faculty_dashboard'))
        else:
            return "You are not registered as faculty!"
    else:
        return "Invalid credentials!"


@app.route("/hod_login", methods=["POST"])
def hod_login():
    email = request.form["email"]
    password = request.form["password"]

    user = mongo.db.users.find_one({"email": email, "role": "hod"})

    if user and check_password_hash(user["password"], password):
        session['email'] = email
        session['role'] = "hod"
        return redirect(url_for('hod_dashboard'))
    else:
        return "Invalid HOD credentials!"


@app.route("/faculty_dashboard")
def faculty_dashboard():
    if 'email' in session and session.get('role') == "faculty":
        faculty = mongo.db.users.find_one({"email": session['email']})
        if not faculty:
            return "Error: Faculty record not found in database."

        timetable_entries = list(mongo.db.timetables.find({"faculty_email": session["email"]}))
        unique_subjects = set()
        subjects_with_buttons = []

        for entry in timetable_entries:
            subject_key = f"{entry['subject']}_{entry['year']}_{entry['section']}"
            if subject_key not in unique_subjects:
                unique_subjects.add(subject_key)
                subjects_with_buttons.append(entry)

        # Add default image path if no profile image exists
        if 'profile_img' not in faculty:
            faculty['profile_img'] = 'default_profile.png'

        return render_template("faculty_dashboard.html",
                               faculty=faculty,
                               timetable=timetable_entries,
                               subjects_with_buttons=subjects_with_buttons)

    return redirect(url_for("login"))


@app.route("/hod_dashboard")
def hod_dashboard():
    if 'email' in session and session.get('role') == "hod":
        user = mongo.db.users.find_one({"email": session['email']})
        hod = {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "department_id": user.get("department_id", None),
            "profile_img": user.get("profile_img", "default_profile.png")  # Add this line
        }

        department = mongo.db.departments.find_one({"_id": hod["department_id"]})
        hod["department"] = department["name"] if department else "Unknown"

        faculties = []
        if hod.get("department_id"):
            faculties = mongo.db.users.find({
                "department_id": hod["department_id"],
                "role": "faculty"
            })

        return render_template('hod_dashboard.html', hod=hod, faculties=faculties)

    return redirect(url_for('login'))


@app.route("/faculty_profile", methods=["GET", "POST"])
def faculty_profile():
    if 'email' in session and session.get('role') == "faculty":
        faculty = mongo.db.users.find_one({"email": session['email']})

        if request.method == "POST":
            education = request.form.get("education")
            specialization = request.form.get("specialization")
            experience = request.form.get("experience")
            courses_taught = request.form.getlist("courses_taught")
            research_interests = request.form.getlist("research_interests")
            skills = request.form.getlist("skills")
            awards = request.form.get("awards")

            mongo.db.users.update_one(
                {"email": session['email']},
                {"$set": {
                    "education": education,
                    "specialization": specialization,
                    "experience": experience,
                    "courses_taught": courses_taught,
                    "research_interests": research_interests,
                    "skills": skills,
                    "awards": awards
                }}
            )

            faculty = mongo.db.users.find_one({"email": session['email']})

        return render_template('faculty_profile.html', faculty=faculty)

    return redirect(url_for('login'))


@app.route("/edit_timetable", methods=["GET", "POST"])
def edit_timetable():
    if 'email' in session and session.get('role') == "faculty":
        faculty = mongo.db.users.find_one({"email": session['email']})

        if request.method == "POST":
            department_selected = request.form.get("department")
            year = request.form.get("year")
            section = request.form.get("section")
            day = request.form.get("day")
            time = request.form.get("time")
            subject = request.form.get("subject")
            faculty_email = session["email"]

            timetable_collection = mongo.db.timetables

            existing_slot = timetable_collection.find_one(
                {"year": year, "section": section, "day": day, "time": time, "faculty_email": {"$ne": faculty_email}}
            )

            if existing_slot:
                flash(f"⚠ Time slot clash: {existing_slot['subject']} is already scheduled!", "danger")
                return redirect(url_for("edit_timetable"))

            subject_key = f"{subject}_{year}_{section}"
            existing_subject = timetable_collection.find_one({"subject": subject, "year": year, "section": section})

            if not existing_subject:
                unique_subjects = mongo.db.unique_subjects
                unique_subjects.update_one(
                    {"subject_key": subject_key},
                    {"$set": {"subject": subject, "year": year, "section": section}},
                    upsert=True
                )

            result = timetable_collection.update_one(
                {"faculty_email": faculty_email, "year": year, "section": section, "day": day, "time": time},
                {"$set": {"subject": subject, "teaching_for_department": department_selected}},
                upsert=True
            )

            flash("✅ Timetable updated successfully!", "success")
            return redirect(url_for("faculty_dashboard"))

        return render_template("edit_timetable.html", faculty=faculty)

    return redirect(url_for("login"))


@app.route("/manage_students/<year>/<section>/<subject>")
def manage_students(year, section, subject):
    student_collection_name = f"students_{year.replace(' ', '_')}_{section}_{subject.replace(' ', '_').lower()}"
    student_collection = mongo.db[student_collection_name]
    students = list(student_collection.find({}, {"_id": 0}))

    return render_template("manage_students.html", students=students, year=year, section=section, subject=subject)


@app.route("/update_students/<year>/<section>/<subject>", methods=["POST"])
def update_students(year, section, subject):
    data = request.json
    students = data.get("students", [])

    student_collection_name = f"students_{year.replace(' ', '_')}_{section}_{subject.replace(' ', '_').lower()}"
    student_collection = mongo.db[student_collection_name]

    student_collection.delete_many({})
    if students:
        student_collection.insert_many(students)

    return jsonify({"message": "Student data updated successfully"}), 200


@app.route("/view_faculty_profile/<email>")
def view_faculty_profile(email):
    faculty = mongo.db.users.find_one({"email": email})
    return render_template('view_faculty_profile.html', faculty=faculty)


@app.route("/view_timetable/<email>")
def view_timetable(email):
    faculty = mongo.db.users.find_one({"email": email})
    if not faculty:
        return "Error: Faculty record not found in database."

    timetable_entries = list(mongo.db.timetables.find({"faculty_email": email}))
    return render_template("view_timetable.html", faculty=faculty, timetable=timetable_entries)


if __name__ == "__main__":
    app.run(debug=True)