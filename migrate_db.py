import modal
import sqlite3

app = modal.App("teacher-assistant-migration")
volume = modal.Volume.from_name("teacher-assistant-data")

@app.function(volumes={"/data": volume})
def migrate_db():
    db_path = "/data/teacher_assistant.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA foreign_keys=off;")
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute('''CREATE TABLE IF NOT EXISTS submissions_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name    TEXT NOT NULL,
            submission_type TEXT NOT NULL CHECK(submission_type IN ('notebook', 'assignment', 'solution', 'question', 'youtube')),
            file_path       TEXT,
            original_text   TEXT,
            extracted_text  TEXT,
            status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
            created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );''')
        cursor.execute("INSERT INTO submissions_new SELECT * FROM submissions;")
        cursor.execute("DROP TABLE submissions;")
        cursor.execute("ALTER TABLE submissions_new RENAME TO submissions;")
        cursor.execute("COMMIT;")
        cursor.execute("PRAGMA foreign_keys=on;")
        print("Migration successful.")
    except Exception as e:
        cursor.execute("ROLLBACK;")
        print("Error migrating: ", e)
    finally:
        conn.close()
