from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import sqlite3
import os
from datetime import datetime
from investigation_engine import investigate_claim, transcribe_voice

app = Flask(__name__)

DATABASE = "database/trackback.db"


# DATABASE CONNECTION
def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# ENSURE DATABASE COLUMNS EXIST
def ensure_investigation_columns(connection):

    existing_columns = [
        row[1] for row in
        connection.execute(
            "PRAGMA table_info(investigations)"
        ).fetchall()
    ]

    new_columns = {
        "evidence": "TEXT",
        "ai_analysis": "TEXT",
        "keywords": "TEXT",
        "evidence_comparison": "TEXT"
    }

    for column, data_type in new_columns.items():

        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE investigations ADD COLUMN {column} {data_type}"
            )


# SAVE INVESTIGATION RESULT
def save_investigation(connection, claim, result):

    ensure_investigation_columns(connection)

    cursor = connection.execute(
        """
        INSERT INTO investigations
        (
            claim,
            status,
            analysis,
            created_at,
            evidence,
            ai_analysis,
            keywords,
            evidence_comparison
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            claim,
            result.get("status", "Insufficient Evidence"),
            result.get("analysis", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(result.get("evidence", [])),
            result.get("ai_analysis", ""),
            json.dumps(result.get("keywords", [])),
            json.dumps(result.get("evidence_comparison", {}))
        )
    )

    return cursor.lastrowid


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():

    connection = get_db()

    investigations = connection.execute(
        "SELECT * FROM investigations ORDER BY id DESC"
    ).fetchall()

    total = len(investigations)

    status_counts = {}

    for item in investigations:
        status = item["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    supported = status_counts.get("Supported", 0)
    contradicted = status_counts.get("Contradicted", 0)

    needs_review = sum(
        count for status, count in status_counts.items()
        if status not in ["Supported", "Contradicted"]
    )

    recent = investigations[:5]

    connection.close()

    return render_template(
        "dashboard.html",
        investigations=investigations,
        recent=recent,
        total=total,
        supported=supported,
        contradicted=contradicted,
        needs_review=needs_review,
        status_counts=status_counts
    )


# DELETE INVESTIGATION
@app.route(
    "/delete-investigation/<int:investigation_id>",
    methods=["POST"]
)
def delete_investigation(investigation_id):

    connection = get_db()

    connection.execute(
        "DELETE FROM investigations WHERE id = ?",
        (investigation_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("dashboard"))


# INVESTIGATION PAGE
@app.route("/investigate")
def investigate():
    return render_template("investigate.html")


# TEXT INVESTIGATION API
@app.route("/api/investigate", methods=["POST"])
def analyze_claim():

    data = request.get_json(silent=True) or {}
    claim = data.get("claim", "").strip()

    if not claim:
        return jsonify({
            "error": "Please enter a claim."
        }), 400

    try:

        # Run the investigation only once
        result = investigate_claim(claim)

        connection = get_db()

        # Save investigation and comparison results
        investigation_id = save_investigation(
            connection,
            claim,
            result
        )

        connection.commit()
        connection.close()

        return jsonify({
            "id": investigation_id,
            "claim": claim,
            **result
        })

    except Exception as error:

        print(
            "Investigation error:",
            repr(error),
            flush=True
        )

        return jsonify({
            "error": str(error)
        }), 500


# VOICE INVESTIGATION API
@app.route("/api/voice-investigate", methods=["POST"])
def analyze_voice():

    audio = request.files.get("audio")

    if not audio or not audio.filename:
        return jsonify({
            "error": "Please record audio first."
        }), 400

    allowed_extensions = {
        "webm", "wav", "mp3", "m4a", "ogg", "mp4"
    }

    extension = audio.filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        return jsonify({
            "error": "Unsupported audio format."
        }), 400

    try:

        # Convert recorded audio into text
        transcript = transcribe_voice(
            audio,
            audio.filename
        )

        if not transcript:
            return jsonify({
                "error": "No speech detected."
            }), 400

        # Investigate the transcribed claim
        result = investigate_claim(transcript)

        connection = get_db()

        # Save voice investigation with all comparison data
        investigation_id = save_investigation(
            connection,
            transcript,
            result
        )

        connection.commit()
        connection.close()

        return jsonify({
            "id": investigation_id,
            "transcript": transcript,
            **result
        })

    except Exception as error:

        print(
            "Voice investigation error:",
            repr(error),
            flush=True
        )

        return jsonify({
            "error": str(error)
        }), 500


# REPORT PAGE
@app.route("/report/<int:investigation_id>")
def report(investigation_id):

    connection = get_db()

    cursor = connection.execute(
        "SELECT * FROM investigations WHERE id = ?",
        (investigation_id,)
    )

    result = cursor.fetchone()

    if result is None:
        connection.close()
        return "Investigation not found", 404

    # Convert database row into dictionary
    column_names = [
        column[0] for column in cursor.description
    ]

    investigation = dict(zip(column_names, result))

    connection.close()

    # Restore saved evidence
    try:
        investigation["evidence"] = json.loads(
            investigation.get("evidence") or "[]"
        )
    except (ValueError, TypeError):
        investigation["evidence"] = []

    # Restore saved keywords
    try:
        investigation["keywords"] = json.loads(
            investigation.get("keywords") or "[]"
        )
    except (ValueError, TypeError):
        investigation["keywords"] = []

    # Restore evidence comparison
    try:
        investigation["evidence_comparison"] = json.loads(
            investigation.get("evidence_comparison") or "{}"
        )
    except (ValueError, TypeError):
        investigation["evidence_comparison"] = {}

    # Restore AI analysis
    investigation["ai_analysis"] = (
        investigation.get("ai_analysis")
        or "No AI assessment available."
    )

    return render_template(
        "report.html",
        investigation=investigation
    )


# RUN APPLICATION
if __name__ == "__main__":
    app.run(debug=True)