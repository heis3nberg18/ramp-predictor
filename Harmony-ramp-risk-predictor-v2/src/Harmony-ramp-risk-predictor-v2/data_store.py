"""Data storage module — stores uploaded data for model retraining over time.
Uses SQLite for compact storage with good query performance."""
import sqlite3
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/home/badasha/.workspace/ramp-predictor-v2/model_data.db")


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS training_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_time TEXT, function_type TEXT, batch_name TEXT,
        learner_count INTEGER, data_json TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ramp_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_time TEXT, function_type TEXT,
        week_range TEXT, learner_count INTEGER, data_json TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prediction_time TEXT, function_type TEXT,
        learner TEXT, predicted_quality REAL, risk_level TEXT,
        actual_quality REAL
    )""")
    return conn


def store_training_data(function_type, learner_data, batch_name=""):
    """Store parsed training data for future model improvement."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO training_uploads (upload_time, function_type, batch_name, learner_count, data_json) VALUES (?,?,?,?,?)",
        (datetime.utcnow().isoformat(), function_type, batch_name,
         len(learner_data), json.dumps(learner_data, default=str))
    )
    conn.commit()
    conn.close()


def store_ramp_data(function_type, audit_df, week_range=""):
    """Store uploaded RAMP audit data."""
    conn = _get_conn()
    # Store summary, not full data (space efficient)
    if "Login" in audit_df.columns:
        summary = audit_df.groupby("Login").agg(
            audits=("Login", "count"),
        ).reset_index().to_dict(orient="records")
    else:
        summary = [{"rows": len(audit_df)}]
    conn.execute(
        "INSERT INTO ramp_uploads (upload_time, function_type, week_range, learner_count, data_json) VALUES (?,?,?,?,?)",
        (datetime.utcnow().isoformat(), function_type, week_range,
         len(audit_df["Login"].unique()) if "Login" in audit_df.columns else 0,
         json.dumps(summary, default=str))
    )
    conn.commit()
    conn.close()


def store_predictions(function_type, predictions_list):
    """Store predictions for later accuracy comparison."""
    conn = _get_conn()
    for p in predictions_list:
        conn.execute(
            "INSERT INTO predictions (prediction_time, function_type, learner, predicted_quality, risk_level) VALUES (?,?,?,?,?)",
            (datetime.utcnow().isoformat(), function_type,
             p.get("learner", ""), p.get("predicted_quality", 0), p.get("risk_level", ""))
        )
    conn.commit()
    conn.close()


def get_stored_count():
    """Get count of stored data for display."""
    if not DB_PATH.exists():
        return {"training": 0, "ramp": 0, "predictions": 0}
    conn = _get_conn()
    t = conn.execute("SELECT COUNT(*) FROM training_uploads").fetchone()[0]
    r = conn.execute("SELECT COUNT(*) FROM ramp_uploads").fetchone()[0]
    p = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    conn.close()
    return {"training": t, "ramp": r, "predictions": p}


def get_all_training_data(function_type=None):
    """Retrieve all stored training data for model retraining."""
    if not DB_PATH.exists():
        return []
    conn = _get_conn()
    if function_type:
        rows = conn.execute("SELECT data_json FROM training_uploads WHERE function_type=?", (function_type,)).fetchall()
    else:
        rows = conn.execute("SELECT data_json FROM training_uploads").fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]
