from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "your_secret_key"

# MongoDB Setup
app.config["MONGO_URI"] = "mongodb://localhost:27017/faculty_desk"  # Replace with your MongoDB URI
mongo = PyMongo(app)


@app.route('/')
def home():
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
        # Debug prints - remove these later once you confirm data is correct
        print("Form Data Received:")
        print("Name:", request.form.get("name"))
        print("Email:", request.form.get("email"))
        print("Contact:", request.form.get("contact"))
        print("Department:", request.form.get("department"))
        print("Role (from select):", request.form.get("role"))
        print("Checkbox 'is_faculty_checkbox':", request.form.get("is_faculty_checkbox"))

        # Get the required fields
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        department_name = request.form["department"]

        # Determine is_faculty flag
        is_faculty = True if role == "faculty" else False

        # Optionally, if you want to check the additional checkbox:
        if request.form.get("is_faculty_checkbox") == "yes":
            is_faculty = True  # This will mark the user as faculty even if role is hod

        department = mongo.db.departments.find_one({"name": department_name})

        # Create the department if it doesn't exist
        if not department:
            department_id = mongo.db.departments.insert_one({
                "name": department_name,
                "short_name": department_name[:3].upper()  # For example, use first three letters
            }).inserted_id
        else:
            department_id = department["_id"]

        existing_user = mongo.db.users.find_one({"email": email})
        if existing_user:
            return "User already exists!"

        hashed_pw = generate_password_hash(password)
        mongo.db.users.insert_one({
            "name": name,
            "email": email,
            "password": hashed_pw,
            "role": role,
            "is_faculty": is_faculty,
            "department_id": department_id
        })

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/teacher_login", methods=["POST"])
def teacher_login():
    email = request.form["email"]
    password = request.form["password"]

    user = mongo.db.users.find_one({"email": email, "role": "faculty"})

    if user and check_password_hash(user["password"], password):
        session['email'] = email
        session['role'] = "faculty"
        return redirect(url_for('faculty_dashboard'))
    else:
        return "Invalid Teacher credentials!"


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
            print("Error: Faculty record not found!")
            return "Error: Faculty record not found in database."

        # Fetch all timetable entries for this faculty
        timetable_entries = list(mongo.db.timetables.find({"faculty_email": session["email"]}))

        # Track unique subjects
        unique_subjects = set()
        subjects_with_buttons = []

        for entry in timetable_entries:
            subject_key = f"{entry['subject']}_{entry['year']}_{entry['section']}"

            # ✅ If subject is unique, add it to the list for button creation
            if subject_key not in unique_subjects:
                unique_subjects.add(subject_key)
                subjects_with_buttons.append(entry)

        return render_template("faculty_dashboard.html", faculty=faculty, timetable=timetable_entries, subjects_with_buttons=subjects_with_buttons)

    return redirect(url_for("login"))




@app.route("/hod_dashboard")
def hod_dashboard():
    if 'email' in session and session.get('role') == "hod":
        user = mongo.db.users.find_one({"email": session['email']})
        # Safely get department_id, avoiding KeyError
        hod = {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "department_id": user.get("department_id", None)  # Added .get() method to avoid KeyError
        }

        # Fetch department name for HOD
        department = mongo.db.departments.find_one({"_id": hod["department_id"]})
        hod["department"] = department["name"] if department else "Unknown"  # Added logic to fetch department name

        # Query faculties only if department_id exists
        faculties = []
        if hod.get("department_id"):  # Ensure department_id is not None
            faculties = mongo.db.users.find({
                "department_id": hod["department_id"],
                "role": "faculty"
            })

        return render_template('hod_dashboard.html', hod=hod, faculties=faculties)
    else:
        return redirect(url_for('login'))


@app.route("/faculty_profile", methods=["GET", "POST"])
def faculty_profile():
    if 'email' in session and session.get('role') == "faculty":
        faculty = mongo.db.users.find_one({"email": session['email']})  # Fetch existing profile data

        if request.method == "POST":
            # Get profile details from form
            education = request.form.get("education")
            specialization = request.form.get("specialization")
            experience = request.form.get("experience")
            courses_taught = request.form.getlist("courses_taught")
            research_interests = request.form.getlist("research_interests")
            skills = request.form.getlist("skills")
            awards = request.form.get("awards")

            # Update faculty profile in database
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

            # Fetch updated profile details immediately after saving
            faculty = mongo.db.users.find_one({"email": session['email']})

        return render_template('faculty_profile.html', faculty=faculty)  # Render updated data on the same page
    else:
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

            timetable_collection = mongo.db.timetables  # Unified collection

            # Check if the time slot is occupied by another faculty
            existing_slot = timetable_collection.find_one(
                {"year": year, "section": section, "day": day, "time": time, "faculty_email": {"$ne": faculty_email}}
            )

            if existing_slot:
                flash(f"⚠ Time slot clash: {existing_slot['subject']} is already scheduled!", "danger")
                return redirect(url_for("edit_timetable"))

            # ✅ Check if subject is unique
            subject_key = f"{subject}_{year}_{section}"
            existing_subject = timetable_collection.find_one({"subject": subject, "year": year, "section": section})

            # ✅ If unique, store it for button creation
            if not existing_subject:
                unique_subjects = mongo.db.unique_subjects
                unique_subjects.update_one(
                    {"subject_key": subject_key},
                    {"$set": {"subject": subject, "year": year, "section": section}},
                    upsert=True
                )

            # Update or insert timetable entry
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

    # ✅ Clear old records to prevent duplicates
    student_collection.delete_many({})

    # ✅ Insert all modified students into the database
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
        print("Error: Faculty record not found!")
        return "Error: Faculty record not found in database."

    # Fetch the latest timetable from the unified `timetables` collection
    timetable_entries = list(mongo.db.timetables.find({"faculty_email": email}))

    return render_template("view_timetable.html", faculty=faculty, timetable=timetable_entries)




if __name__ == "__main__":
    app.run(debug=True)





