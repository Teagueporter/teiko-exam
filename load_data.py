import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "cell-count.csv"
DB_PATH = ROOT / "teiko.db"
POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS cell_counts;
DROP TABLE IF EXISTS samples;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS projects;

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL UNIQUE
);

CREATE TABLE subjects (
    subject_id INTEGER PRIMARY KEY,
    subject_code TEXT NOT NULL,
    project_id INTEGER NOT NULL REFERENCES projects(project_id),
    condition TEXT NOT NULL,
    age INTEGER,
    sex TEXT NOT NULL,
    treatment TEXT NOT NULL,
    response TEXT CHECK (response IN ('yes', 'no') OR response IS NULL),
    UNIQUE (project_id, subject_code)
);

CREATE TABLE samples (
    sample_id INTEGER PRIMARY KEY,
    sample_code TEXT NOT NULL UNIQUE,
    subject_id INTEGER NOT NULL REFERENCES subjects(subject_id),
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL
);

CREATE TABLE cell_counts (
    sample_id INTEGER NOT NULL REFERENCES samples(sample_id),
    population TEXT NOT NULL,
    count INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample_id, population)
);

CREATE INDEX idx_subjects_condition_treatment_response
    ON subjects(condition, treatment, response);
CREATE INDEX idx_samples_type_time ON samples(sample_type, time_from_treatment_start);
CREATE INDEX idx_cell_counts_population ON cell_counts(population);
"""


def get_or_create_project(conn: sqlite3.Connection, project_name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO projects(project_name) VALUES (?)", (project_name,))
    row = conn.execute(
        "SELECT project_id FROM projects WHERE project_name = ?", (project_name,)
    ).fetchone()
    return int(row[0])


def get_or_create_subject(conn: sqlite3.Connection, row: dict[str, str], project_id: int) -> int:
    conn.execute(
        """
        INSERT OR IGNORE INTO subjects(
            subject_code, project_id, condition, age, sex, treatment, response
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["subject"],
            project_id,
            row["condition"],
            int(row["age"]) if row["age"] else None,
            row["sex"],
            row["treatment"],
            row["response"] or None,
        ),
    )
    subject = conn.execute(
        "SELECT subject_id FROM subjects WHERE project_id = ? AND subject_code = ?",
        (project_id, row["subject"]),
    ).fetchone()
    return int(subject[0])


def insert_sample(conn: sqlite3.Connection, row: dict[str, str], subject_id: int) -> int:
    conn.execute(
        """
        INSERT INTO samples(sample_code, subject_id, sample_type, time_from_treatment_start)
        VALUES (?, ?, ?, ?)
        """,
        (
            row["sample"],
            subject_id,
            row["sample_type"],
            int(row["time_from_treatment_start"]),
        ),
    )
    sample = conn.execute(
        "SELECT sample_id FROM samples WHERE sample_code = ?", (row["sample"],)
    ).fetchone()
    return int(sample[0])


def load_data() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Expected input file at {CSV_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)

        with CSV_PATH.open(newline="") as source:
            reader = csv.DictReader(source)
            for row in reader:
                project_id = get_or_create_project(conn, row["project"])
                subject_id = get_or_create_subject(conn, row, project_id)
                sample_id = insert_sample(conn, row, subject_id)
                conn.executemany(
                    """
                    INSERT INTO cell_counts(sample_id, population, count)
                    VALUES (?, ?, ?)
                    """,
                    [(sample_id, population, int(row[population])) for population in POPULATIONS],
                )

        conn.commit()

    print(f"Loaded {CSV_PATH.name} into {DB_PATH.name}")


if __name__ == "__main__":
    load_data()
