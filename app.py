
from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable
)


app = Flask(__name__)
DATABASE = "portfolio.db"


def init_db():
    connection = sqlite3.connect(DATABASE)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            college TEXT,
            degree TEXT,
            year TEXT,
            career TEXT,
            skills TEXT,
            objective TEXT,
            github TEXT,
            linkedin TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            technologies TEXT,
            github TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            title TEXT NOT NULL,
            issuer TEXT,
            date TEXT,
            certificate_url TEXT
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            career TEXT NOT NULL,
            skill TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Not Started',
            UNIQUE(student_id, career, skill)
        )
    """)
    connection.commit()
    connection.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/profile")
def profile():
    return render_template("profile.html")


@app.route("/save-profile", methods=["POST"])
def save_profile():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    if not name or not email:
        return "Name and email are required.", 400

    connection = sqlite3.connect(DATABASE)
    connection.execute("""
        INSERT INTO students
        (name, email, college, degree, year, career,
         skills, objective, github, linkedin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name, email,
        request.form.get("college", ""),
        request.form.get("degree", ""),
        request.form.get("year", ""),
        request.form.get("career", ""),
        request.form.get("skills", ""),
        request.form.get("objective", ""),
        request.form.get("github", ""),
        request.form.get("linkedin", "")
    ))
    connection.commit()
    connection.close()

    return redirect(url_for("success"))


@app.route("/success")
def success():
    return """
        <h1>Profile saved successfully!</h1>
        <a href="/dashboard">View Dashboard</a>
    """


@app.route("/dashboard")
def dashboard():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    connection.close()

    if student is None:
        return redirect(url_for("profile"))

    return render_template("dashboard.html", student=student)


@app.route("/projects", methods=["GET", "POST"])
def projects():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT id FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if student is None:
        connection.close()
        return redirect(url_for("profile"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not description:
            connection.close()
            return "Title and description are required.", 400

        connection.execute("""
            INSERT INTO projects
            (student_id, title, description, technologies, github)
            VALUES (?, ?, ?, ?, ?)
        """, (
            student["id"], title, description,
            request.form.get("technologies", "").strip(),
            request.form.get("github", "").strip()
        ))

        connection.commit()
        connection.close()
        return redirect(url_for("projects"))

    project_list = connection.execute(
        "SELECT * FROM projects WHERE student_id = ? ORDER BY id DESC",
        (student["id"],)
    ).fetchall()

    connection.close()
    return render_template("projects.html", projects=project_list)


@app.route("/certificates", methods=["GET", "POST"])
def certificates():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT id FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if student is None:
        connection.close()
        return redirect(url_for("profile"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()

        if not title:
            connection.close()
            return "Certificate title is required.", 400

        connection.execute("""
            INSERT INTO certificates
            (student_id, title, issuer, date, certificate_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            student["id"],
            title,
            request.form.get("issuer", "").strip(),
            request.form.get("date", "").strip(),
            request.form.get("certificate_url", "").strip()
        ))

        connection.commit()
        connection.close()
        return redirect(url_for("certificates"))

    certificate_list = connection.execute(
        "SELECT * FROM certificates WHERE student_id = ? ORDER BY id DESC",
        (student["id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "certificates.html",
        certificates=certificate_list
    )

@app.route("/resume")
def generate_resume():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if student is None:
        connection.close()
        return redirect(url_for("profile"))

    projects = connection.execute(
        "SELECT * FROM projects WHERE student_id = ? ORDER BY id DESC",
        (student["id"],)
    ).fetchall()

    certificates = connection.execute(
        "SELECT * FROM certificates WHERE student_id = ? ORDER BY id DESC",
        (student["id"],)
    ).fetchall()

    connection.close()

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ResumeName",
        parent=styles["Title"],
        fontSize=23,
        leading=28,
        textColor=colors.HexColor("#34347A"),
        alignment=TA_CENTER,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#5141A8"),
        spaceBefore=12,
        spaceAfter=5
    ))

    story = []

    def add_text(value, style="BodyText"):
        safe_value = escape(str(value or ""))
        story.append(Paragraph(safe_value, styles[style]))

    def add_section(title):
        story.append(Paragraph(title, styles["SectionHeading"]))
        story.append(HRFlowable(
            width="100%",
            thickness=0.7,
            color=colors.HexColor("#C9C5ED"),
            spaceAfter=7
        ))

    add_text(student["name"], "ResumeName")
    add_text(student["email"], "Normal")

    contact = [
        student["college"],
        student["degree"],
        student["github"],
        student["linkedin"]
    ]
    contact = [escape(str(item)) for item in contact if item]

    if contact:
        story.append(Spacer(1, 5))
        story.append(Paragraph(
            " | ".join(contact), styles["Normal"]
        ))

    if student["objective"]:
        add_section("CAREER OBJECTIVE")
        add_text(student["objective"])

    add_section("EDUCATION")
    add_text(student["college"] or "College not provided")
    add_text(student["degree"] or "Degree not provided")

    if student["year"]:
        add_text("Study year: " + student["year"])

    if student["skills"]:
        add_section("TECHNICAL SKILLS")
        add_text(student["skills"])

    if projects:
        add_section("PROJECTS")

        for project in projects:
            add_text(project["title"], "Heading3")
            add_text(project["description"])

            if project["technologies"]:
                add_text(
                    "Technologies: " + project["technologies"]
                )

            if project["github"]:
                add_text("GitHub: " + project["github"])

            story.append(Spacer(1, 6))

    if certificates:
        add_section("CERTIFICATIONS")

        for certificate in certificates:
            add_text(certificate["title"], "Heading3")

            details = [
                certificate["issuer"],
                certificate["date"]
            ]
            details = [str(item) for item in details if item]

            if details:
                add_text(" | ".join(details))

            if certificate["certificate_url"]:
                add_text(
                    "Certificate: " + certificate["certificate_url"]
                )

    pdf.build(story)
    buffer.seek(0)

    filename = "".join(
        char for char in student["name"]
        if char.isalnum() or char in (" ", "-", "_")
    ).strip() or "Student"

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename.replace(" ", "_") + "_Resume.pdf"
    )


@app.route("/skill-analyzer", methods=["GET", "POST"])
def skill_analyzer():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    connection.close()

    if student is None:
        return redirect(url_for("profile"))

    career_skills = {
        "Python Developer": [
            "Python", "SQL", "Git", "Problem Solving",
            "Data Structures"
        ],
        "Data Analyst": [
            "Python", "SQL", "Excel", "Power BI",
            "Statistics"
        ],
        "Web Developer": [
            "HTML", "CSS", "JavaScript", "Python", "SQL"
        ],
        "Machine Learning Engineer": [
            "Python", "Statistics", "NumPy", "Pandas",
            "Machine Learning"
        ]
    }

    selected_career = "Python Developer"
    matched_skills = []
    missing_skills = []
    match_percentage = 0
    submitted = False

    if request.method == "POST":
        selected_career = request.form.get(
            "career", "Python Developer"
        )

        if selected_career not in career_skills:
            selected_career = "Python Developer"

        submitted = True

        current_skills = [
            skill.strip().lower()
            for skill in (student["skills"] or "").split(",")
            if skill.strip()
        ]

        required_skills = career_skills[selected_career]

        for skill in required_skills:
            if skill.lower() in current_skills:
                matched_skills.append(skill)
            else:
                missing_skills.append(skill)

        match_percentage = round(
            len(matched_skills) / len(required_skills) * 100
        )

    return render_template(
        "skill_analyzer.html",
        student=student,
        careers=career_skills,
        selected_career=selected_career,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        match_percentage=match_percentage,
        submitted=submitted
    )

@app.route("/roadmap")
def learning_roadmap():
    career = request.args.get("career", "Data Analyst")

    learning_plans = {
        "Python Developer": {
            "Python": ("Practice functions, modules, and file handling.", "Beginner"),
            "SQL": ("Practice queries, joins, and database operations.", "Beginner"),
            "Git": ("Learn commits, branches, and GitHub.", "Beginner"),
            "Problem Solving": ("Solve programming problems regularly.", "Intermediate"),
            "Data Structures": ("Study lists, stacks, queues, and trees.", "Intermediate")
        },
        "Data Analyst": {
            "Python": ("Practice Python for data analysis.", "Beginner"),
            "SQL": ("Learn filtering, joins, grouping, and subqueries.", "Beginner"),
            "Excel": ("Practice formulas, sorting, and pivot tables.", "Beginner"),
            "Power BI": ("Build reports and interactive dashboards.", "Intermediate"),
            "Statistics": ("Study averages, distributions, and correlation.", "Beginner")
        },
        "Web Developer": {
            "HTML": ("Build accessible webpage structures.", "Beginner"),
            "CSS": ("Practice layouts, colors, and responsive design.", "Beginner"),
            "JavaScript": ("Learn variables, functions, and DOM events.", "Beginner"),
            "Python": ("Practice Python fundamentals and web development.", "Beginner"),
            "SQL": ("Learn how web applications store and retrieve data.", "Beginner")
        },
        "Machine Learning Engineer": {
            "Python": ("Practice functions, modules, and data processing.", "Beginner"),
            "Statistics": ("Study probability, distributions, and correlation.", "Beginner"),
            "NumPy": ("Practice arrays and numerical operations.", "Beginner"),
            "Pandas": ("Learn to clean and analyze datasets.", "Beginner"),
            "Machine Learning": ("Study model training and evaluation.", "Intermediate")
        }
    }

    if career not in learning_plans:
        career = "Data Analyst"

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    connection.close()

    if student is None:
        return redirect(url_for("profile"))

    skills = [
        skill.strip().lower()
        for skill in (student["skills"] or "").split(",")
        if skill.strip()
    ]

    roadmap = []

    for skill, details in learning_plans[career].items():
        if skill.lower() not in skills:
            roadmap.append({
                "skill": skill,
                "description": details[0],
                "level": details[1]
            })

    return render_template(
        "roadmap.html",
        career=career,
        roadmap=roadmap
    )

@app.route("/progress", methods=["GET", "POST"])
def learning_progress():
    learning_plans = {
        "Python Developer": [
            "Python", "SQL", "Git",
            "Problem Solving", "Data Structures"
        ],
        "Data Analyst": [
            "Python", "SQL", "Excel",
            "Power BI", "Statistics"
        ],
        "Web Developer": [
            "HTML", "CSS", "JavaScript", "Python", "SQL"
        ],
        "Machine Learning Engineer": [
            "Python", "Statistics", "NumPy",
            "Pandas", "Machine Learning"
        ]
    }

    career = request.args.get("career", "Data Analyst")

    if career not in learning_plans:
        career = "Data Analyst"

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    student = connection.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if student is None:
        connection.close()
        return redirect(url_for("profile"))

    if request.method == "POST":
        career = request.form.get("career", career)

        if career not in learning_plans:
            career = "Data Analyst"

        for skill in learning_plans[career]:
            status = request.form.get(
                "status_" + skill, "Not Started"
            )

            if status not in [
                "Not Started", "In Progress", "Completed"
            ]:
                status = "Not Started"

            connection.execute("""
                INSERT INTO learning_progress
                    (student_id, career, skill, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(student_id, career, skill)
                DO UPDATE SET status = excluded.status
            """, (
                student["id"], career, skill, status
            ))

        connection.commit()

    saved_rows = connection.execute("""
        SELECT skill, status
        FROM learning_progress
        WHERE student_id = ? AND career = ?
    """, (student["id"], career)).fetchall()

    connection.close()

    saved_statuses = {
        row["skill"]: row["status"] for row in saved_rows
    }

    roadmap = []

    for skill in learning_plans[career]:
        roadmap.append({
            "skill": skill,
            "status": saved_statuses.get(skill, "Not Started")
        })

    completed = sum(
        1 for item in roadmap
        if item["status"] == "Completed"
    )

    percentage = round(completed / len(roadmap) * 100)

    return render_template(
        "progress.html",
        career=career,
        roadmap=roadmap,
        completed=completed,
        total=len(roadmap),
        percentage=percentage
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
