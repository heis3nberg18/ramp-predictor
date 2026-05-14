"""Smart parser for training data — handles raw dumps from various systems."""
import pandas as pd
import numpy as np
from prediction_engine import TARGET_QUALITY


def parse_uploaded_training(uploaded_file):
    """Parse multi-sheet training data — handles raw dumps intelligently."""
    xl = pd.ExcelFile(uploaded_file)
    sheets = xl.sheet_names
    data = {"learners": {}, "raw_sheets": {}}

    for sheet in sheets:
        df = xl.parse(sheet)
        data["raw_sheets"][sheet] = df
        sheet_lower = sheet.lower()

        if any(k in sheet_lower for k in ["mid term", "midterm", "mid_term"]):
            _parse_assessment_sheet(df, data["learners"], "midterm")
        elif any(k in sheet_lower for k in ["final", "assessment"]) and "mid" not in sheet_lower:
            _parse_assessment_sheet(df, data["learners"], "final_assessment")
        elif any(k in sheet_lower for k in ["resolved", "littweb", "litt"]):
            _parse_littweb_sheet(df, data["learners"])
        elif any(k in sheet_lower for k in ["live", "observation"]):
            _parse_generic_scores(df, data["learners"], "live_case", max_val=10)
        elif any(k in sheet_lower for k in ["trainer", "rating"]):
            _parse_trainer_ratings(df, data["learners"])
        elif any(k in sheet_lower for k in ["misc", "poll", "activity"]):
            _parse_generic_scores(df, data["learners"], "misc_score", max_val=100)

    return data


def _parse_assessment_sheet(df, learners, score_key):
    """Parse assessment data — handles LMS raw dumps with question-level data."""
    # Detect format: LMS dump has employee_login, question_result, score_percentage
    login_col = _find_col(df, ["employee_login", "login", "learner", "alias", "participant", "name"])
    
    if login_col is None:
        return

    # Check if it's question-level data (LMS format)
    result_col = _find_col(df, ["question_result", "result"])
    score_pct_col = None
    # Prioritize exact match for score_percentage
    for col in df.columns:
        if str(col).lower().strip() == "score_percentage":
            score_pct_col = col
            break
    if score_pct_col is None:
        score_pct_col = _find_col(df, ["percentage", "overall_percent"])
    question_col = _find_col(df, ["question_text", "question"])

    if result_col and question_col:
        # Question-level LMS data — aggregate per learner
        for login, group in df.groupby(login_col):
            login = str(login).strip()
            if not login or login.lower() in ("nan", "n/a", "none") or len(login) > 30:
                continue
            if login not in learners:
                learners[login] = {}

            # Overall score from score_percentage (use max/first non-null unique value per learner)
            if score_pct_col:
                scores = group[score_pct_col].dropna().unique()
                if len(scores) > 0:
                    try:
                        learners[login][score_key] = float(max(scores))
                    except (ValueError, TypeError):
                        pass

            # Question-level accuracy
            if result_col:
                results = group[result_col].dropna().astype(str).str.upper()
                total_q = len(results)
                correct_q = (results == "CORRECT").sum()
                if total_q > 0:
                    learners[login][f"{score_key}_accuracy"] = correct_q / total_q
                    learners[login][f"{score_key}_total_questions"] = total_q
                    learners[login][f"{score_key}_correct"] = int(correct_q)

                    # If no score_percentage found, compute from questions
                    if score_key not in learners[login]:
                        learners[login][score_key] = (correct_q / total_q) * 100

            # Topic-level breakdown
            topic_col = _find_col(group, ["domain_name", "folder_name", "topic", "section", "category"])
            if topic_col:
                topic_results = group.groupby(topic_col)[result_col].apply(
                    lambda x: (x.astype(str).str.upper() == "CORRECT").mean()
                ).to_dict()
                learners[login][f"{score_key}_topics"] = topic_results

    elif score_pct_col:
        # Simple format with just login + score
        for login, group in df.groupby(login_col):
            login = str(login).strip()
            if not login or login.lower() in ("nan", "n/a", "none"):
                continue
            if login not in learners:
                learners[login] = {}
            scores = group[score_pct_col].dropna()
            if len(scores) > 0:
                try:
                    learners[login][score_key] = float(scores.iloc[0])
                except (ValueError, TypeError):
                    pass


def _parse_littweb_sheet(df, learners):
    """Parse LittWeb resolved case data — handles raw dump with multiple rounds."""
    # Find ALL header rows (there can be multiple rounds)
    header_rows = []
    for i in range(len(df)):
        row_vals = [str(v).lower().strip() for v in df.iloc[i].values if pd.notna(v)]
        if any("learner" in v or "alias" in v for v in row_vals) and any("action" in v or "score" in v or "ar" in v for v in row_vals):
            header_rows.append(i)

    if not header_rows:
        return

    # Parse each round and aggregate
    all_rounds = []
    for h_idx, h_row in enumerate(header_rows):
        # Determine end of this round
        end_row = header_rows[h_idx + 1] - 1 if h_idx + 1 < len(header_rows) else len(df)

        round_df = df.iloc[h_row:end_row].copy().reset_index(drop=True)
        round_df.columns = round_df.iloc[0]
        round_df = round_df.iloc[1:].reset_index(drop=True)
        # Drop rows where all values are NaN
        round_df = round_df.dropna(how="all")
        all_rounds.append(round_df)

    # Aggregate across all rounds per learner
    for round_df in all_rounds:
        login_col = _find_col(round_df, ["learner alias", "learner", "login", "alias"])
        score_col = _find_col(round_df, ["avg score", "average", "score"])
        ar_col = _find_col(round_df, ["ar%", "ar", "accuracy"])

        if login_col is None:
            continue

        for _, row in round_df.iterrows():
            login = str(row.get(login_col, "")).strip() if pd.notna(row.get(login_col)) else ""
            if not login or login.lower() in ("nan", "n/a", "none", "learner alias") or len(login) > 25:
                continue
            if login not in learners:
                learners[login] = {}

            # Accumulate scores across rounds
            if score_col and pd.notna(row.get(score_col)):
                try:
                    score = float(row[score_col])
                    existing = learners[login].get("_resolved_scores", [])
                    existing.append(score)
                    learners[login]["_resolved_scores"] = existing
                    # Store average * 10 (LittWeb scores are 0-1)
                    avg = sum(existing) / len(existing)
                    learners[login]["resolved_case"] = avg * 10 if avg <= 1 else avg
                except (ValueError, TypeError):
                    pass


def _parse_trainer_ratings(df, learners):
    """Parse trainer ratings — skips instruction rows, handles various column names."""
    # Find header row
    header_row = None
    for i in range(min(15, len(df))):
        row_vals = [str(v).lower().strip() for v in df.iloc[i].values if pd.notna(v)]
        if any("learner" in v or "login" in v for v in row_vals) and any("(1-5)" in v or "communication" in v or "confidence" in v for v in row_vals):
            header_row = i
            break

    if header_row is not None:
        df = df.iloc[header_row:].reset_index(drop=True)
        seen = {}
        new_cols = []
        for i, c in enumerate(df.iloc[0]):
            name = str(c).strip() if pd.notna(c) else f"col_{i}"
            if name in seen:
                seen[name] += 1
                new_cols.append(f"{name}_{seen[name]}")
            else:
                seen[name] = 0
                new_cols.append(name)
        df.columns = new_cols
        df = df.iloc[1:].reset_index(drop=True)

    login_col = _find_col(df, ["learner", "login", "alias", "participant", "name"])
    if login_col is None:
        return

    for _, row in df.iterrows():
        login = str(row.get(login_col, "")).strip() if pd.notna(row.get(login_col)) else ""
        if not login or login.lower() in ("nan", "n/a", "none", "learner login"):
            continue
        if login not in learners:
            learners[login] = {}

        for col in df.columns:
            if pd.isna(col):
                continue
            col_lower = str(col).lower()
            for attr in ["communication", "confidence", "engagement", "problem_solving", "problem solving",
                         "knowledge", "critical", "deep_div", "deep div", "retention", "attention",
                         "adaptab", "time_man", "time man"]:
                if attr in col_lower:
                    val = row.get(col)
                    if pd.notna(val):
                        try:
                            learners[login][f"rating_{attr.replace(' ', '_')}"] = float(val)
                        except (ValueError, TypeError):
                            pass
            if "comment" in col_lower or "anecdote" in col_lower or "feedback" in col_lower:
                if pd.notna(row.get(col)):
                    learners[login]["trainer_comment"] = str(row[col])


def _parse_generic_scores(df, learners, score_key, max_val=100):
    """Parse generic score sheets — handles instruction rows and multiple score columns."""
    # Find header row — must have a short "learner/login" value (column header, not sentence)
    header_row = None
    for i in range(min(20, len(df))):
        row_vals = [str(v).lower().strip() for v in df.iloc[i].values if pd.notna(v)]
        # Header row has short values like "Learner", "Score", not full sentences
        short_vals = [v for v in row_vals if len(v) < 30]
        has_learner = any(v in ("learner", "login", "alias", "learner login", "participant", "name") for v in short_vals)
        has_score = any("score" in v or "result" in v or "marks" in v for v in short_vals)
        if has_learner and has_score:
            header_row = i
            break

    if header_row is not None:
        df = df.iloc[header_row:].reset_index(drop=True)
        seen = {}
        new_cols = []
        for i, c in enumerate(df.iloc[0]):
            name = str(c).strip() if pd.notna(c) else f"col_{i}"
            if name in seen:
                seen[name] += 1
                new_cols.append(f"{name}_{seen[name]}")
            else:
                seen[name] = 0
                new_cols.append(name)
        df.columns = new_cols
        df = df.iloc[1:].reset_index(drop=True)

    login_col = _find_col(df, ["learner", "login", "alias", "participant", "name"])
    if login_col is None:
        return

    # Find ALL numeric score columns
    score_cols = []
    for col in df.columns:
        if pd.isna(col):
            continue
        col_lower = str(col).lower()
        if any(k in col_lower for k in ["score", "result", "percentage", "marks", "(0-10)", "(0-100)"]):
            score_cols.append(col)

    if not score_cols:
        # Fallback: find any numeric column that's not the login
        for col in df.columns:
            if col != login_col:
                try:
                    vals = pd.to_numeric(df[col], errors="coerce").dropna()
                    if len(vals) > 0 and vals.max() <= max_val:
                        score_cols.append(col)
                except:
                    pass

    for _, row in df.iterrows():
        login = str(row.get(login_col, "")).strip() if pd.notna(row.get(login_col)) else ""
        if not login or login.lower() in ("nan", "n/a", "none", "learner") or len(login) > 25:
            continue
        if login not in learners:
            learners[login] = {}

        # Average all score columns for this learner
        scores = []
        for sc in score_cols:
            val = row.get(sc)
            if pd.notna(val):
                try:
                    scores.append(float(val))
                except (ValueError, TypeError):
                    pass

        if scores:
            avg_score = sum(scores) / len(scores)
            # Store or update (keep highest if multiple entries)
            existing = learners[login].get(score_key)
            if existing is None or avg_score > existing:
                learners[login][score_key] = avg_score


def _find_col(df, keywords):
    """Find first column matching any keyword (case-insensitive)."""
    for col in df.columns:
        if pd.isna(col):
            continue
        col_lower = str(col).lower().strip()
        for kw in keywords:
            if kw in col_lower:
                return col
    return None


def compute_training_features(learner_scores):
    """Convert parsed training data into normalized features."""
    # Filter out junk entries (instruction text, example data)
    junk_keywords = ["instruction", "dump", "include", "optional", "refer to", "function context",
                     "rate each", "add free", "model uses", "example", "john_doe", "jane_smith"]
    
    results = []
    for name, scores in learner_scores.items():
        # Skip junk entries
        if len(name) > 25 or any(kw in name.lower() for kw in junk_keywords):
            continue
        if not any(k in scores for k in ["midterm", "final_assessment", "resolved_case", "live_case"]):
            continue
        # Normalize scores to 0-1
        midterm = scores.get("midterm", 0) / 100 if scores.get("midterm") else None
        final = scores.get("final_assessment", 0) / 100 if scores.get("final_assessment") else None
        live = scores.get("live_case", 0) / 10 if scores.get("live_case") and scores.get("live_case") <= 10 else (scores.get("live_case", 0) / 100 if scores.get("live_case") else None)
        resolved = scores.get("resolved_case", 0) / 10 if scores.get("resolved_case") and scores.get("resolved_case") <= 10 else (scores.get("resolved_case", 0) / 100 if scores.get("resolved_case") else None)
        misc = scores.get("misc_score", 0) / 100 if scores.get("misc_score") else None

        # Ratings
        rating_keys = [k for k in scores if k.startswith("rating_")]
        valid_ratings = [scores[k] for k in rating_keys if scores[k] is not None]
        avg_rating = sum(valid_ratings) / len(valid_ratings) / 5 if valid_ratings else None

        # Composite
        components = [midterm, final, live, resolved, avg_rating, misc]
        valid = [c for c in components if c is not None]
        composite = sum(valid) / len(valid) if valid else 0.5

        results.append({
            "learner": name, "midterm": midterm, "final_assessment": final,
            "live_case": live, "resolved_case": resolved, "avg_rating": avg_rating,
            "misc_score": misc, "composite_score": round(composite, 3),
            "trainer_comment": scores.get("trainer_comment", ""),
            "midterm_topics": scores.get("midterm_topics", {}),
            "final_topics": scores.get("final_assessment_topics", {}),
        })
    return pd.DataFrame(results)


def predict_with_historical(training_df, historical_audit, function_type):
    """Predict RAMP performance using training scores + historical patterns."""
    # Normalize historical audit columns
    if historical_audit is not None:
        # Normalize Login column
        login_col = None
        for col in historical_audit.columns:
            if any(k in str(col).lower() for k in ["investigator login", "login"]):
                login_col = col
                break
        if login_col and login_col != "Login":
            historical_audit = historical_audit.rename(columns={login_col: "Login"})
        if "Login" in historical_audit.columns:
            historical_audit["Login"] = historical_audit["Login"].astype(str).str.split("@").str[0].str.strip()

        # Normalize Defect
        if "Defect" in historical_audit.columns:
            historical_audit["is_defect"] = historical_audit["Defect"].astype(str).str.strip().str.lower().isin(["y", "yes"])
        else:
            historical_audit["is_defect"] = False

    # Compute historical baseline
    if historical_audit is not None and "Login" in historical_audit.columns and "is_defect" in historical_audit.columns:
        total = len(historical_audit)
        defects = historical_audit["is_defect"].sum()
        hist_avg_quality = (total - defects) / total if total else 0.95
        hist_std = 0.05
        person_q = historical_audit.groupby("Login").agg(
            audits=("is_defect", "count"), defs=("is_defect", "sum")).reset_index()
        person_q["q"] = (person_q["audits"] - person_q["defs"]) / person_q["audits"]
        hist_at_risk_rate = (person_q["q"] < TARGET_QUALITY).mean()
    else:
        hist_avg_quality = 0.95
        hist_std = 0.05
        hist_at_risk_rate = 0.15

    # Generate predictions
    predictions = []
    for _, row in training_df.iterrows():
        composite = row["composite_score"]
        z_score = (composite - 0.7) / 0.15
        predicted_quality = np.clip(hist_avg_quality + z_score * hist_std * 0.5, 0.5, 1.0)
        risk_prob = max(0, min(1, 1 - (predicted_quality - (TARGET_QUALITY - 0.1)) / 0.2))

        if risk_prob >= 0.6: risk_level = "🔴 HIGH RISK"
        elif risk_prob >= 0.3: risk_level = "🟡 MEDIUM RISK"
        else: risk_level = "🟢 LOW RISK"

        callouts = []
        if row["midterm"] is not None and row["midterm"] < 0.7:
            callouts.append("⚠️ Below average mid-term — knowledge gaps likely")
        if row["live_case"] is not None and row["live_case"] < 0.7:
            callouts.append("⚠️ Low live case score — real-time handling concerns")
        if row["resolved_case"] is not None and row["resolved_case"] < 0.7:
            callouts.append("⚠️ Low resolved case — case resolution needs work")
        if row["avg_rating"] is not None and row["avg_rating"] < 0.6:
            callouts.append("⚠️ Low trainer ratings — multiple areas flagged")
        if not callouts and "LOW" not in risk_level:
            callouts.append("⚠️ Borderline across multiple areas")
        if not callouts:
            callouts.append("✅ No significant risk indicators")

        predictions.append({
            "learner": row["learner"], "composite_score": composite,
            "predicted_quality": round(predicted_quality, 2),
            "risk_prob": round(risk_prob, 2), "risk_level": risk_level,
            "callouts": callouts, "midterm": row["midterm"],
            "final_assessment": row["final_assessment"],
            "live_case": row["live_case"], "resolved_case": row["resolved_case"],
            "avg_rating": row["avg_rating"],
        })

    return pd.DataFrame(predictions), {
        "hist_avg_quality": round(hist_avg_quality, 3),
        "hist_at_risk_rate": round(hist_at_risk_rate, 3),
        "batch_size": len(predictions),
    }
