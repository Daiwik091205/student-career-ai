import sqlite3
import bcrypt
import json

DB_NAME = 'student_career_app.db'

def get_connection():
    return sqlite3.connect(DB_NAME)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            education TEXT,
            experience TEXT,
            interests TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Skills table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            skill_name TEXT NOT NULL,
            proficiency TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_name TEXT NOT NULL,
            description TEXT,
            extracted_skills TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Target Careers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS careers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            career_name TEXT NOT NULL,
            required_skills TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Roadmaps table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roadmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            career_id INTEGER,
            gap_analysis TEXT,
            readiness_score REAL,
            roadmap_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (career_id) REFERENCES careers (id)
        )
    ''')

    # Resume Recommendations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resume_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            resume_filename TEXT,
            resume_text TEXT,
            summary TEXT,
            recommendations_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()

def register_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user_id, hashed = row
        if bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8')):
            return user_id
    return None

def get_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT education, experience, interests FROM profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"education": row[0], "experience": row[1], "interests": row[2]}
    return {"education": "", "experience": "", "interests": ""}

def save_profile(user_id, education, experience, interests):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO profiles (user_id, education, experience, interests)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            education=excluded.education,
            experience=excluded.experience,
            interests=excluded.interests
    ''', (user_id, education, experience, interests))
    conn.commit()
    conn.close()

def add_skill(user_id, skill_name, proficiency):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO skills (user_id, skill_name, proficiency) VALUES (?, ?, ?)", (user_id, skill_name, proficiency))
    conn.commit()
    conn.close()

def get_skills(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, skill_name, proficiency FROM skills WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "skill_name": r[1], "proficiency": r[2]} for r in rows]

def delete_skill(skill_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    conn.close()

def add_project(user_id, project_name, description, extracted_skills=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (user_id, project_name, description, extracted_skills) VALUES (?, ?, ?, ?)", (user_id, project_name, description, extracted_skills))
    conn.commit()
    conn.close()

def get_projects(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, project_name, description, extracted_skills FROM projects WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "project_name": r[1], "description": r[2], "extracted_skills": r[3]} for r in rows]

def delete_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()

def save_target_career(user_id, career_name, required_skills):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO careers (user_id, career_name, required_skills) VALUES (?, ?, ?)", (user_id, career_name, required_skills))
    career_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return career_id

def get_latest_target_career(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, career_name, required_skills FROM careers WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "career_name": row[1], "required_skills": row[2]}
    return None

def save_roadmap(user_id, career_id, gap_analysis, readiness_score, roadmap_json):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO roadmaps (user_id, career_id, gap_analysis, readiness_score, roadmap_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, career_id, gap_analysis, readiness_score, roadmap_json))
    conn.commit()
    conn.close()

def get_latest_roadmap(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT gap_analysis, readiness_score, roadmap_json, c.career_name 
        FROM roadmaps r
        JOIN careers c ON r.career_id = c.id
        WHERE r.user_id = ? 
        ORDER BY r.id DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "gap_analysis": row[0],
            "readiness_score": row[1],
            "roadmap_json": json.loads(row[2]) if row[2] else [],
            "career_name": row[3]
        }
    return None

def save_resume_recommendations(user_id, resume_filename, resume_text, summary, recommendations_json):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO resume_recommendations (user_id, resume_filename, resume_text, summary, recommendations_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, resume_filename, resume_text, summary, recommendations_json))
    conn.commit()
    conn.close()

def get_latest_resume_recommendations(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT resume_filename, resume_text, summary, recommendations_json, created_at
        FROM resume_recommendations
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "resume_filename": row[0],
            "resume_text": row[1],
            "summary": row[2],
            "recommendations": json.loads(row[3]) if row[3] else [],
            "created_at": row[4]
        }
    return None

if __name__ == "__main__":
    initialize_db()
    print("Database initialized.")
