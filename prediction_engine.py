"""
KYC RAMP Risk Prediction Engine
================================
Core prediction logic ported from Document4 model.
Uses Random Forest Classifier with 23 features derived from:
- Early RAMP weeks quality (Wk 1-2)
- Audit defect data (types, severity, rates)
- Trainer/course historical performance
- Peer comparison
- Pre-training audit history
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
from collections import defaultdict
import warnings
warnings.filterwarnings("ignore")

TARGET_QUALITY = 0.92  # Below this = "at risk"


def parse_training_data(kyc_path, sheet_name="IH-UPS"):
    """Parse KYC Q1 TQ training quality data."""
    df = pd.read_excel(kyc_path, sheet_name=sheet_name)
    score_cols = {}
    for col in df.columns:
        if "Score" in str(col) and "Avg" not in str(col):
            for part in str(col).split():
                try:
                    wk = int(part)
                    score_cols[col] = wk
                    break
                except ValueError:
                    pass

    rows = []
    for _, row in df.iterrows():
        participant = row.get("Participant")
        if not participant or pd.isna(participant):
            continue
        train_wk = int(row.get("Training Week", 0)) if pd.notna(row.get("Training Week")) else 0
        scores = {}
        for col, abs_wk in score_cols.items():
            val = row[col]
            if pd.notna(val) and val != "N/A" and val != "":
                try:
                    ramp_wk = abs_wk - train_wk
                    if ramp_wk > 0:
                        scores[ramp_wk] = float(val)
                except (ValueError, TypeError):
                    pass
        rows.append({
            "batch": row.get("Batch ID", ""),
            "train_wk": train_wk,
            "participant": str(participant).strip(),
            "trainer": row.get("Trainer", ""),
            "course": row.get("Course", ""),
            "scores": scores,
        })
    return rows


def parse_audit_data(audit_path, participants):
    """Parse audit data and group by login and resolve week."""
    if audit_path.endswith(".csv"):
        df = pd.read_csv(audit_path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(audit_path)

    audit = {}
    for _, row in df.iterrows():
        login = str(row.get("Login", "")).strip()
        if login not in participants:
            continue
        rwk = str(row.get("Resolve Week", "")).strip()
        try:
            wk_num = int(rwk.split("Week")[1].strip())
        except (IndexError, ValueError):
            continue
        if login not in audit:
            audit[login] = {}
        if wk_num not in audit[login]:
            audit[login][wk_num] = []
        audit[login][wk_num].append(row.to_dict())
    return audit


def build_features(training_rows, audit_data, completed_weeks=(1, 2)):
    """Build 23-feature vector for each learner based on completed RAMP weeks."""
    batch_info = defaultdict(lambda: {"participants": set()})
    pm = {}
    for row in training_rows:
        pm[row["participant"]] = row
        batch_info[row["batch"]]["participants"].add(row["participant"])

    # Compute trainer met rate and course miss rate from all data
    trainer_met = defaultdict(lambda: {"total": 0, "met": 0})
    course_miss = defaultdict(lambda: {"total": 0, "missed": 0})
    for row in training_rows:
        scores = row["scores"]
        later_scores = [scores[rw] for rw in scores if rw > max(completed_weeks)]
        if later_scores:
            avg = sum(later_scores) / len(later_scores)
            trainer_met[row["trainer"]]["total"] += 1
            course_miss[row["course"]]["total"] += 1
            if avg >= TARGET_QUALITY:
                trainer_met[row["trainer"]]["met"] += 1
            else:
                course_miss[row["course"]]["missed"] += 1

    trainer_met_rate = {t: d["met"] / d["total"] if d["total"] else 0 for t, d in trainer_met.items()}
    course_miss_rate = {c: d["missed"] / d["total"] if d["total"] else 0 for c, d in course_miss.items()}

    features_list = []
    for row in training_rows:
        login = row["participant"]
        scores = row["scores"]

        # Only include learners with data in completed weeks
        if not any(rw in scores for rw in completed_weeks):
            continue

        wk_scores = [scores.get(rw) for rw in completed_weeks]
        valid_scores = [s for s in wk_scores if s is not None]
        if not valid_scores:
            continue

        ea = sum(valid_scores) / len(valid_scores)
        em = min(valid_scores)
        ev = max(valid_scores) - min(valid_scores) if len(valid_scores) > 1 else 0
        bs = len(batch_info[row["batch"]]["participants"])

        # Early audit features
        eaud = 0; edef = 0; edt = set(); hi = 0; med = 0
        for rw in completed_weeks:
            abs_wk = rw + row["train_wk"]
            for r in audit_data.get(login, {}).get(abs_wk, []):
                eaud += 1
                score_val = str(r.get("Score", "")).strip()
                sub = str(r.get("Defect Subcategory 1", "")).strip()
                if sub and score_val not in ("No Impact, Well Done!", "No Impact Feedback", "No Impact", ""):
                    edef += 1
                    edt.add(sub)
                    if "High" in score_val:
                        hi += 1
                    elif "Medium" in score_val:
                        med += 1
        edr = edef / eaud if eaud else 0

        # Peer average
        peers = batch_info[row["batch"]]["participants"] - {login}
        ps = [pm[p]["scores"].get(rw) for p in peers if p in pm for rw in completed_weeks if rw in pm[p].get("scores", {})]
        valid_ps = [s for s in ps if s is not None]
        pa = sum(valid_ps) / len(valid_ps) if valid_ps else 0

        # Historical (pre-training) audit features
        h_aud = 0; h_def = 0; h_dt = set(); h_hi = 0; h_med = 0
        for abs_wk in sorted(audit_data.get(login, {}).keys()):
            if abs_wk <= row["train_wk"]:  # Pre-training
                for r in audit_data[login][abs_wk]:
                    h_aud += 1
                    score_val = str(r.get("Score", "")).strip()
                    sub = str(r.get("Defect Subcategory 1", "")).strip()
                    if sub and score_val not in ("No Impact, Well Done!", "No Impact Feedback", "No Impact", "",
                                                  "System Miss", "Process Miss"):
                        h_def += 1
                        h_dt.add(sub)
                        if "High" in score_val:
                            h_hi += 1
                        elif "Medium" in score_val:
                            h_med += 1

        wk1 = scores.get(min(completed_weeks))
        wk2 = scores.get(max(completed_weeks)) if len(completed_weeks) > 1 else wk1

        features = [
            wk1 if wk1 is not None else ea,
            wk2 if wk2 is not None else ea,
            ea, em, ev, bs, edr, len(edt), eaud, edef, hi, med,
            trainer_met_rate.get(row["trainer"], 0),
            course_miss_rate.get(row["course"], 0),
            pa,
            1 if (wk1 is not None and wk1 < TARGET_QUALITY) else 0,
            1 if em < 0.85 else 0,
            h_aud, h_def, h_def / h_aud if h_aud else 0, len(h_dt), h_hi, h_med,
            1 if h_aud > 0 else 0,
        ]

        # Target: actual performance in weeks after completed_weeks
        target_weeks = [rw for rw in scores if rw > max(completed_weeks)]
        actual_scores = [scores[rw] for rw in target_weeks]
        actual_avg = sum(actual_scores) / len(actual_scores) if actual_scores else None

        features_list.append({
            "login": login,
            "course": row["course"],
            "trainer": row["trainer"],
            "batch": row["batch"],
            "train_wk": row["train_wk"],
            "wk_scores": {rw: scores.get(rw) for rw in completed_weeks},
            "early_avg": round(ea, 3),
            "early_min": round(em, 3),
            "early_defect_rate": round(edr, 3),
            "hist_defect_rate": round(h_def / h_aud, 3) if h_aud else 0,
            "hist_audits": h_aud,
            "trainer_met_rate": round(trainer_met_rate.get(row["trainer"], 0), 3),
            "course_miss_rate": round(course_miss_rate.get(row["course"], 0), 3),
            "peer_avg": round(pa, 3),
            "features": features,
            "actual_avg": round(actual_avg, 3) if actual_avg is not None else None,
            "actual_met": actual_avg >= TARGET_QUALITY if actual_avg is not None else None,
            "all_scores": scores,
        })

    return features_list


def train_and_predict(features_list):
    """Train Random Forest and generate predictions using cross-validation."""
    # Split into those with actuals (for training) and those without (predict only)
    with_actuals = [f for f in features_list if f["actual_avg"] is not None]
    without_actuals = [f for f in features_list if f["actual_avg"] is None]

    if len(with_actuals) < 5:
        # Not enough data to train — use heuristic
        for f in features_list:
            f["risk_prob"] = 1 - f["early_avg"] if f["early_avg"] else 0.5
            f["prediction"] = "AT RISK" if f["risk_prob"] >= 0.5 else "LOW RISK"
        return features_list, None

    X_train = np.array([f["features"] for f in with_actuals])
    y_train = np.array([0 if f["actual_met"] else 1 for f in with_actuals])  # 1 = at risk

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=5, min_samples_leaf=3,
        min_samples_split=5, random_state=42, class_weight="balanced"
    )

    # Cross-val predictions for those with actuals
    cv_folds = min(5, len(with_actuals))
    if cv_folds >= 2 and len(set(y_train)) > 1:
        cv_probs = cross_val_predict(rf, X_train, y_train, cv=cv_folds, method="predict_proba")[:, 1]
        for i, f in enumerate(with_actuals):
            f["risk_prob"] = round(float(cv_probs[i]), 3)
            f["prediction"] = "AT RISK" if cv_probs[i] >= 0.5 else "LOW RISK"
    else:
        for f in with_actuals:
            f["risk_prob"] = 1 - f["early_avg"]
            f["prediction"] = "AT RISK" if f["risk_prob"] >= 0.5 else "LOW RISK"

    # Train on all actuals, predict for those without
    rf.fit(X_train, y_train)
    if without_actuals:
        X_pred = np.array([f["features"] for f in without_actuals])
        probs = rf.predict_proba(X_pred)[:, 1]
        for i, f in enumerate(without_actuals):
            f["risk_prob"] = round(float(probs[i]), 3)
            f["prediction"] = "AT RISK" if probs[i] >= 0.5 else "LOW RISK"

    # Compute metrics
    metrics = {}
    actual_labels = y_train
    pred_labels = np.array([1 if f["prediction"] == "AT RISK" else 0 for f in with_actuals])
    if len(set(actual_labels)) > 1:
        metrics["accuracy"] = round(accuracy_score(actual_labels, pred_labels), 3)
        metrics["f1"] = round(f1_score(actual_labels, pred_labels, zero_division=0), 3)
        metrics["precision"] = round(precision_score(actual_labels, pred_labels, zero_division=0), 3)
        metrics["recall"] = round(recall_score(actual_labels, pred_labels, zero_division=0), 3)
        metrics["confusion_matrix"] = confusion_matrix(actual_labels, pred_labels).tolist()

    all_predictions = with_actuals + without_actuals
    return all_predictions, metrics


FEATURE_NAMES = [
    "Wk1 Score", "Wk2 Score", "Early Avg", "Early Min", "Early Variance",
    "Batch Size", "Early Defect Rate", "Defect Types", "Early Audits", "Early Defects",
    "High Impact", "Medium Impact", "Trainer Met Rate", "Course Miss Rate", "Peer Avg",
    "Wk1 Below Target", "Early Min Below 85%",
    "Hist Audits", "Hist Defects", "Hist Defect Rate", "Hist Defect Types",
    "Hist High Impact", "Hist Medium Impact", "Has History",
]
