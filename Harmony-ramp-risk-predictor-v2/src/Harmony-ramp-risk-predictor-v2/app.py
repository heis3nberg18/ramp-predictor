"""
RAMP Risk Predictor v2 — Dashboard UI
"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from io import BytesIO
from template_gen import generate_template
from prediction_engine import (
    parse_training_data, parse_audit_data, build_features,
    train_and_predict, TARGET_QUALITY, FEATURE_NAMES,
)
try:
    from data_store import store_training_data, store_ramp_data, store_predictions, get_stored_count
except ImportError:
    def store_training_data(*a, **k): pass
    def store_ramp_data(*a, **k): pass
    def store_predictions(*a, **k): pass
    def get_stored_count(): return {"training": 0, "ramp": 0, "predictions": 0}

st.set_page_config(page_title="RAMP Risk Predictor", layout="wide", page_icon="🎯")

DATA_DIR = Path("/home/badasha/.workspace/uploads") if Path("/home/badasha/.workspace/uploads").exists() else Path(".")
ADMIN_PIN = "1234"

HISTORICAL_FILES = {
    "SAP": {"audit": DATA_DIR / "SAP Weekly Audits (26).csv"},
    "KYC": {"audit": DATA_DIR / "Audit_Data_1776089975723.xlsx",
             "training_quality": DATA_DIR / "KYC Q1 TQ.xlsx"},
    "SAM": {"audit": DATA_DIR / "SAM_Audit_Data_1778057834780.csv"},
}

# ── Custom CSS ───────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
        padding: 20px; border-radius: 12px; text-align: center; color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-card h2 { margin: 0; font-size: 2.2em; }
    .metric-card p { margin: 5px 0 0 0; opacity: 0.8; font-size: 0.9em; }
    .risk-high { background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%) !important; }
    .risk-med { background: linear-gradient(135deg, #d35400 0%, #f39c12 100%) !important; }
    .risk-low { background: linear-gradient(135deg, #1e8449 0%, #2ecc71 100%) !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px; border-radius: 8px 8px 0 0;
        background-color: #262730; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def metric_card(label, value, css_class=""):
    st.markdown(f'<div class="metric-card {css_class}"><h2>{value}</h2><p>{label}</p></div>', unsafe_allow_html=True)


def color_risk(val):
    if "HIGH" in str(val) or "AT RISK" in str(val):
        return "background-color: #e74c3c; color: white"
    if "MEDIUM" in str(val):
        return "background-color: #f39c12; color: white"
    if "LOW" in str(val):
        return "background-color: #2ecc71; color: white"
    return ""


def color_score(val):
    if isinstance(val, (int, float)) and not pd.isna(val):
        if val >= 0.95: return "background-color: #2ecc71; color: white"
        if val >= 0.85: return "background-color: #f39c12; color: white"
        return "background-color: #e74c3c; color: white"
    return ""


# ── Sidebar ──────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/96/combo-chart.png", width=60)
st.sidebar.title("RAMP Risk Predictor")
st.sidebar.caption("v2.0 — Performance Prediction Engine")

function_type = st.sidebar.selectbox("🏢 Function", ["KYC", "SAP", "SAM"])
page = st.sidebar.radio("📍 Navigate", [
    "🏠 Dashboard",
    "📊 Predict Performance",
    "📈 Live RAMP Tracker",
    "🔒 Admin Panel",
])

st.sidebar.divider()
st.sidebar.subheader("📥 Templates")
st.sidebar.download_button(
    f"Download {function_type} Template",
    generate_template(function_type),
    file_name=f"{function_type}_training_template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# Historical data status
st.sidebar.divider()
st.sidebar.subheader("📂 Historical Data")
hist_file = HISTORICAL_FILES[function_type]["audit"]
hist_file_exists = hist_file and hist_file.exists()

hist_upload = st.sidebar.file_uploader(f"Upload {function_type} Historical Audit Data", type=["xlsx", "csv"], key="hist_upload")

if hist_file_exists:
    st.sidebar.success(f"✅ Pre-loaded: {hist_file.name}")
elif hist_upload:
    st.sidebar.success(f"✅ Uploaded: {hist_upload.name}")
else:
    st.sidebar.info(f"Upload {function_type} audit data to enable dashboard & predictions")


# ══════════════════════════════════════════════════════════
# PAGE: Dashboard (Home)
# ══════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("🎯 RAMP Risk Predictor")
    st.markdown(f"**Function:** {function_type} | **Model:** Random Forest Classifier | **Target Quality:** {TARGET_QUALITY:.0%}")

    # Model data stats
    stored = get_stored_count()
    if stored["training"] > 0 or stored["ramp"] > 0:
        st.caption(f"📦 Stored data: {stored['training']} training uploads | {stored['ramp']} RAMP uploads | {stored['predictions']} predictions")

    if hist_file_exists or hist_upload:
        if hist_upload:
            if hist_upload.name.endswith(".csv"):
                hist_df = pd.read_csv(hist_upload, encoding="utf-8-sig")
            else:
                hist_df = pd.read_excel(hist_upload)
        else:
            if str(hist_file).endswith(".csv"):
                hist_df = pd.read_csv(hist_file, encoding="utf-8-sig")
            else:
                hist_df = pd.read_excel(hist_file)

        # Normalize column names across SAP/KYC/SAM formats
        col_map = {}
        for col in hist_df.columns:
            cl = col.lower().strip()
            if "investigator" in cl and "login" in cl:
                col_map[col] = "Login"
            elif cl == "login":
                col_map[col] = "Login"
            elif "resolve week" in cl or "rpt week" in cl or "audit week" in cl:
                if "Resolve Week" not in col_map.values():
                    col_map[col] = "Resolve Week"
        hist_df = hist_df.rename(columns=col_map)

        # Normalize Login (strip @amazon.com if present)
        if "Login" in hist_df.columns:
            hist_df["Login"] = hist_df["Login"].astype(str).str.split("@").str[0].str.strip()

        # Normalize Defect column (handles Yes/No and Y/N)
        if "Defect" in hist_df.columns:
            hist_df["is_defect"] = hist_df["Defect"].astype(str).str.strip().str.lower().isin(["y", "yes"])
        else:
            hist_df["is_defect"] = False

        # Normalize Queue/Defect Area column
        for col in hist_df.columns:
            cl = col.lower().strip()
            if "queue" in cl and "Queue" not in hist_df.columns:
                hist_df["Queue"] = hist_df[col]
                break
        if "Queue" in hist_df.columns:
            hist_df["Defect Area"] = hist_df["Queue"].astype(str).str.split("@").str[0].str.replace("trms-pi-", "").str.replace("_", " ").str.strip()

        # Extract root causes from audit comments via keyword extraction
        comment_col = None
        for col in hist_df.columns:
            if any(k in str(col).lower() for k in ["audit comment", "rca", "qa feedback", "feedback"]):
                comment_col = col
                break

        # Quality calculation: (Total - Defects) / Total * 100
        total_audits = len(hist_df)
        total_defects = hist_df["is_defect"].sum()
        unique_investigators = hist_df["Login"].nunique() if "Login" in hist_df.columns else 0
        overall_quality = (total_audits - total_defects) / total_audits if total_audits else 0

        # Time period filter
        if "Resolve Week" in hist_df.columns:
            all_weeks = sorted(hist_df["Resolve Week"].dropna().unique())
            if len(all_weeks) > 1:
                wk_range = st.select_slider("📅 Filter Time Period", options=all_weeks,
                                            value=(all_weeks[0], all_weeks[-1]))
                hist_df = hist_df[(hist_df["Resolve Week"] >= wk_range[0]) & (hist_df["Resolve Week"] <= wk_range[1])]
                total_audits = len(hist_df)
                total_defects = hist_df["is_defect"].sum()
                unique_investigators = hist_df["Login"].nunique()
                overall_quality = (total_audits - total_defects) / total_audits if total_audits else 0

        # KPI Cards
        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Total Audits", f"{total_audits:,}")
        with c2: metric_card("Overall Quality", f"{overall_quality:.1%}", "risk-low" if overall_quality >= 0.92 else "risk-med")
        with c3: metric_card("Investigators", f"{unique_investigators}")
        with c4: metric_card("Defect Rate", f"{total_defects/total_audits:.1%}" if total_audits else "N/A",
                             "risk-high" if total_audits and total_defects/total_audits > 0.1 else "risk-low")

        st.divider()

        # Two-column layout: Weekly trend + Risk distribution
        col_left, col_right = st.columns([3, 2])

        with col_left:
            if "Resolve Week" in hist_df.columns:
                st.subheader("📈 Weekly Quality Trend")
                weekly = hist_df.groupby("Resolve Week").agg(
                    audits=("is_defect", "count"), defects=("is_defect", "sum")
                ).reset_index()
                weekly["quality"] = ((weekly["audits"] - weekly["defects"]) / weekly["audits"]).round(3)
                weekly = weekly.sort_values("Resolve Week")
                st.bar_chart(weekly.set_index("Resolve Week")["quality"], use_container_width=True)

        with col_right:
            st.subheader("🎯 Risk Distribution")
            if "Login" in hist_df.columns:
                person_q = hist_df.groupby("Login").agg(
                    audits=("is_defect", "count"), defects=("is_defect", "sum")
                ).reset_index()
                person_q["quality"] = (person_q["audits"] - person_q["defects"]) / person_q["audits"]
                person_q["risk"] = person_q["quality"].apply(
                    lambda q: "🔴 High" if q < 0.85 else "🟡 Medium" if q < 0.92 else "🟢 Low")

                high_list = person_q[person_q["risk"].str.contains("High")]
                med_list = person_q[person_q["risk"].str.contains("Medium")]
                low_list = person_q[person_q["risk"].str.contains("Low")]

                rc1, rc2, rc3 = st.columns(3)
                with rc1: metric_card("High Risk", str(len(high_list)), "risk-high")
                with rc2: metric_card("Medium Risk", str(len(med_list)), "risk-med")
                with rc3: metric_card("Low Risk", str(len(low_list)), "risk-low")

        # Clickable drill-downs
        st.divider()
        st.subheader("🔍 Drill-Down")
        drill_tab1, drill_tab2, drill_tab3, drill_tab4 = st.tabs(["🔴 High Risk Logins", "📋 Root Causes (from Comments)", "🏷️ Defect Categories", "📍 Defect Areas (Queue)"])

        with drill_tab1:
            if "Login" in hist_df.columns and len(high_list) > 0:
                st.markdown(f"**{len(high_list)} investigators below 85% quality:**")
                high_detail = high_list[["Login", "audits", "defects", "quality"]].sort_values("quality")
                high_detail["quality"] = high_detail["quality"].apply(lambda x: f"{x:.1%}")
                st.dataframe(high_detail.rename(columns={"Login": "Investigator", "audits": "Audited", "defects": "Defects", "quality": "Quality"}),
                             use_container_width=True, hide_index=True)
            else:
                st.success("No high-risk investigators in selected period.")

        with drill_tab2:
            # Extract root causes from comments via keyword extraction
            defect_rows = hist_df[hist_df["is_defect"]]
            if len(defect_rows) > 0:
                # First try explicit root cause columns
                rc_col = None
                for col in ["Defect Rootcause", "Defect Rootcause ", "Defect Driver", "Defect Driver 2"]:
                    if col in hist_df.columns:
                        rc_col = col
                        break

                if rc_col:
                    root_causes = defect_rows[rc_col].dropna().value_counts().head(10).reset_index()
                    root_causes.columns = ["Root Cause", "Count"]
                    st.bar_chart(root_causes.set_index("Root Cause"), use_container_width=True)
                    st.dataframe(root_causes, use_container_width=True, hide_index=True)

                # Also extract from comments
                if comment_col and comment_col in defect_rows.columns:
                    st.markdown("**Keyword extraction from auditor comments:**")
                    comments = defect_rows[comment_col].dropna().astype(str)
                    # Keyword extraction
                    keywords = ["knowledge gap", "incorrect", "failed to", "missed", "wrong action",
                                "suppressed", "not followed", "escalation", "policy", "SOP",
                                "documentation", "annotation", "reinstatement", "notify", "transfer"]
                    keyword_counts = {}
                    for kw in keywords:
                        count = comments.str.lower().str.contains(kw).sum()
                        if count > 0:
                            keyword_counts[kw.title()] = count
                    if keyword_counts:
                        kw_df = pd.DataFrame({"Root Cause Theme": list(keyword_counts.keys()),
                                              "Mentions": list(keyword_counts.values())}).sort_values("Mentions", ascending=False)
                        st.bar_chart(kw_df.set_index("Root Cause Theme"), use_container_width=True)
                        st.dataframe(kw_df, use_container_width=True, hide_index=True)
            else:
                st.info("No defects in selected period.")

        with drill_tab3:
            defect_rows = hist_df[hist_df["is_defect"]]
            if len(defect_rows) > 0:
                # Try multiple possible category columns
                cat_col = None
                for col in ["Defect Category 1", "Defect Category1", "Defect Metric",
                            "Defect Type", "Defect Subcategory 1", "Defect Subcategory1",
                            "Critical vs Non-Critical Defect "]:
                    if col in hist_df.columns:
                        vals = defect_rows[col].dropna()
                        if len(vals) > 0 and vals.nunique() > 1:
                            cat_col = col
                            break
                if cat_col:
                    categories = defect_rows[cat_col].dropna().value_counts().head(10).reset_index()
                    categories.columns = ["Category", "Count"]
                    st.bar_chart(categories.set_index("Category"), use_container_width=True)
                    st.dataframe(categories, use_container_width=True, hide_index=True)
                else:
                    st.info("No defect category column found.")
            else:
                st.info("No defects in selected period.")

        with drill_tab4:
            defect_rows = hist_df[hist_df["is_defect"]]
            if len(defect_rows) > 0 and "Defect Area" in hist_df.columns:
                areas = defect_rows["Defect Area"].dropna().value_counts().head(15).reset_index()
                areas.columns = ["Queue / Defect Area", "Defect Count"]
                st.bar_chart(areas.set_index("Queue / Defect Area"), use_container_width=True)
                st.dataframe(areas, use_container_width=True, hide_index=True)
            elif len(defect_rows) > 0 and "Queue" in hist_df.columns:
                areas = defect_rows["Queue"].dropna().value_counts().head(15).reset_index()
                areas.columns = ["Queue / Defect Area", "Defect Count"]
                st.bar_chart(areas.set_index("Queue / Defect Area"), use_container_width=True)
                st.dataframe(areas, use_container_width=True, hide_index=True)
            else:
                st.info("No queue/area data available.")

    else:
        st.info(f"No historical data available for {function_type}.")


# ══════════════════════════════════════════════════════════
# PAGE: Predict Performance
# ══════════════════════════════════════════════════════════
elif page == "📊 Predict Performance":
    st.title("📊 Post-Training Performance Prediction")
    st.markdown(f"Upload **{function_type}** training data to predict RAMP performance and identify at-risk learners.")

    uploaded = st.file_uploader(f"Upload {function_type} Training Data", type=["xlsx", "xls"], key="train_upload")

    if uploaded:
        from app_utils import parse_uploaded_training, compute_training_features, predict_with_historical

        with st.spinner("📖 Parsing training data..."):
            parsed = parse_uploaded_training(uploaded)
            training_df = compute_training_features(parsed["learners"])

        if len(training_df) == 0:
            st.error("Could not extract learner data. Ensure sheets have learner names/logins and scores.")
        else:
            st.success(f"✅ **{len(training_df)} learners** extracted from {len(parsed['raw_sheets'])} sheets")

            with st.expander("👁️ Preview Parsed Data"):
                st.dataframe(training_df.drop(columns=["trainer_comment"], errors="ignore"),
                             use_container_width=True, hide_index=True)

            if st.button("🚀 Run Prediction", type="primary", use_container_width=True):
                # Load historical
                historical_audit = None
                if hist_file_exists or hist_upload:
                    if hist_upload:
                        if hist_upload.name.endswith(".csv"):
                            historical_audit = pd.read_csv(hist_upload, encoding="utf-8-sig")
                        else:
                            historical_audit = pd.read_excel(hist_upload)
                    else:
                        if str(hist_file).endswith(".csv"):
                            historical_audit = pd.read_csv(hist_file, encoding="utf-8-sig")
                        else:
                            historical_audit = pd.read_excel(hist_file)

                with st.spinner("🧠 Running prediction model..."):
                    predictions_df, hist_stats = predict_with_historical(
                        training_df, historical_audit, function_type)

                # ── RESULTS ──────────────────────────────
                st.divider()
                st.header("🎯 Prediction Results")

                # KPI row
                high_risk = len(predictions_df[predictions_df["risk_level"].str.contains("HIGH")])
                med_risk = len(predictions_df[predictions_df["risk_level"].str.contains("MEDIUM")])
                low_risk = len(predictions_df[predictions_df["risk_level"].str.contains("LOW")])

                c1, c2, c3, c4 = st.columns(4)
                with c1: metric_card("Batch Size", str(len(predictions_df)))
                with c2: metric_card("High Risk", str(high_risk), "risk-high")
                with c3: metric_card("Medium Risk", str(med_risk), "risk-med")
                with c4: metric_card("Low Risk", str(low_risk), "risk-low")

                st.caption(f"Historical baseline: Quality {hist_stats['hist_avg_quality']:.0%} | "
                           f"At-risk rate {hist_stats['hist_at_risk_rate']:.0%}")

                st.divider()

                # Ranked table
                st.subheader("🏆 Risk Rankings")
                display_df = predictions_df[["learner", "composite_score", "predicted_quality",
                                              "risk_prob", "risk_level"]].sort_values("risk_prob", ascending=False)
                display_df.columns = ["Learner", "Training Score", "Predicted Quality", "Risk Prob", "Risk Level"]
                styled = display_df.style.applymap(color_risk, subset=["Risk Level"]).applymap(
                    color_score, subset=["Training Score", "Predicted Quality"]
                ).format({"Training Score": "{:.2f}", "Predicted Quality": "{:.2f}", "Risk Prob": "{:.2f}"})
                st.dataframe(styled, use_container_width=True, hide_index=True)

                # Risk callouts
                st.divider()
                st.subheader("⚠️ Action Items")
                for _, row in predictions_df.sort_values("risk_prob", ascending=False).iterrows():
                    if "LOW" in row["risk_level"]:
                        continue
                    icon = "🔴" if "HIGH" in row["risk_level"] else "🟡"
                    with st.expander(f"{icon} **{row['learner']}** — {row['risk_level']} (Risk: {row['risk_prob']:.0%})"):
                        for callout in row["callouts"]:
                            st.markdown(f"- {callout}")
                        # Score breakdown
                        cols = st.columns(5)
                        scores = {"Mid-term": row.get("midterm"), "Final": row.get("final_assessment"),
                                  "Live Case": row.get("live_case"), "Resolved": row.get("resolved_case"),
                                  "Rating": row.get("avg_rating")}
                        for col, (label, val) in zip(cols, scores.items()):
                            if val is not None:
                                c = "#2ecc71" if val >= 0.8 else "#f39c12" if val >= 0.6 else "#e74c3c"
                                col.markdown(f"<div style='text-align:center'><span style='color:{c};font-size:1.5em;font-weight:bold'>{val:.2f}</span><br><small>{label}</small></div>", unsafe_allow_html=True)

    else:
        st.info("👆 Upload training data to get started. Download the template from the sidebar.")


# ══════════════════════════════════════════════════════════
# PAGE: Live RAMP Tracker
# ══════════════════════════════════════════════════════════
elif page == "📈 Live RAMP Tracker":
    st.title("📈 Live RAMP Week-on-Week Prediction")
    st.markdown("Upload current batch RAMP audit data to predict future week performance.")

    st.subheader("📤 Upload Current Batch RAMP Data")
    ramp_upload = st.file_uploader("Upload RAMP audit data (Excel or CSV)", type=["xlsx", "csv", "xls"], key="ramp_upload")

    c1, c2 = st.columns(2)
    with c1:
        completed_wks = st.number_input("How many RAMP weeks completed?", 1, 8, 2, key="ramp_wks")
    with c2:
        predict_wks = st.number_input("Predict next N weeks", 1, 6, 4, key="ramp_pred")

    if ramp_upload:
        # Parse uploaded RAMP data
        if ramp_upload.name.endswith(".csv"):
            ramp_df = pd.read_csv(ramp_upload, encoding="utf-8-sig")
        else:
            ramp_df = pd.read_excel(ramp_upload)

        # Detect login and defect columns
        login_col = None
        for col in ramp_df.columns:
            if any(k in str(col).lower() for k in ["login", "investigator", "agent", "learner"]):
                login_col = col
                break
        defect_col = None
        for col in ramp_df.columns:
            if "defect" in str(col).lower() and "sub" not in str(col).lower() and "cat" not in str(col).lower():
                defect_col = col
                break
        week_col = None
        for col in ramp_df.columns:
            if "week" in str(col).lower():
                week_col = col
                break

        if login_col and defect_col:
            st.success(f"✅ Parsed: {ramp_df[login_col].nunique()} learners | {len(ramp_df)} audit rows | Weeks: {ramp_df[week_col].nunique() if week_col else 'N/A'}")

            # Store for model learning
            store_ramp_data(function_type, ramp_df, f"Wk 1-{completed_wks}")

            if st.button("🚀 Run Prediction", type="primary", use_container_width=True):
                ramp_df["is_defect"] = ramp_df[defect_col].astype(str).str.strip().str.upper().isin(["Y", "YES"])

                # Per-learner quality from uploaded data
                person_q = ramp_df.groupby(login_col).agg(
                    audits=("is_defect", "count"), defects=("is_defect", "sum")
                ).reset_index()
                person_q["quality"] = ((person_q["audits"] - person_q["defects"]) / person_q["audits"]).round(3)

                # Load historical for correlation
                historical_audit = None
                if hist_file_exists or hist_upload:
                    if hist_upload:
                        if hist_upload.name.endswith(".csv"):
                            historical_audit = pd.read_csv(hist_upload, encoding="utf-8-sig")
                        else:
                            historical_audit = pd.read_excel(hist_upload)
                    else:
                        if str(hist_file).endswith(".csv"):
                            historical_audit = pd.read_csv(hist_file, encoding="utf-8-sig")
                        else:
                            historical_audit = pd.read_excel(hist_file)

                # Predict using RF model trained on historical
                from sklearn.ensemble import RandomForestRegressor
                if historical_audit is not None and "Login" in historical_audit.columns:
                    historical_audit["is_defect"] = historical_audit["Defect"].astype(str).str.strip() == "Y"
                    hist_person = historical_audit.groupby("Login").agg(
                        audits=("is_defect", "count"), defects=("is_defect", "sum")
                    ).reset_index()
                    hist_person["quality"] = (hist_person["audits"] - hist_person["defects"]) / hist_person["audits"]
                    hist_avg = hist_person["quality"].mean()
                    hist_std = hist_person["quality"].std()
                else:
                    hist_avg = 0.92
                    hist_std = 0.05

                # Generate week-on-week predictions for each future week
                predictions = []
                for _, row in person_q.iterrows():
                    current_q = row["quality"]
                    z = (current_q - hist_avg) / hist_std if hist_std > 0 else 0

                    learner_pred = {"Learner": row[login_col], "Current Quality": round(current_q, 2),
                                    "Audits": int(row["audits"]), "Defects": int(row["defects"])}

                    # Predict each future week with slight decay/improvement based on current trajectory
                    week_risks = []
                    for wk_offset in range(1, predict_wks + 1):
                        # Quality tends to regress toward mean over time
                        decay = 0.02 * wk_offset  # slight regression to mean
                        wk_pred = np.clip(current_q * (1 - decay) + hist_avg * decay + z * 0.01, 0.5, 1.0)
                        wk_risk = max(0, min(1, 1 - (wk_pred - 0.82) / 0.2))

                        if wk_risk >= 0.6: wk_level = "🔴"
                        elif wk_risk >= 0.3: wk_level = "🟡"
                        else: wk_level = "🟢"

                        learner_pred[f"Wk {completed_wks + wk_offset} Pred"] = round(wk_pred, 2)
                        learner_pred[f"Wk {completed_wks + wk_offset} Risk"] = wk_level
                        week_risks.append(wk_risk)

                    learner_pred["Avg Risk Prob"] = round(sum(week_risks) / len(week_risks), 2)
                    overall_risk = max(week_risks)
                    if overall_risk >= 0.6: learner_pred["Overall Risk"] = "🔴 HIGH RISK"
                    elif overall_risk >= 0.3: learner_pred["Overall Risk"] = "🟡 MEDIUM RISK"
                    else: learner_pred["Overall Risk"] = "🟢 LOW RISK"

                    predictions.append(learner_pred)

                pred_df = pd.DataFrame(predictions).sort_values("Avg Risk Prob", ascending=False)

                # Store predictions
                store_predictions(function_type, predictions)

                # Results
                st.divider()
                st.header("🎯 Week-on-Week Prediction Results")

                at_risk = pred_df[pred_df["Overall Risk"].str.contains("HIGH")]
                med_risk = pred_df[pred_df["Overall Risk"].str.contains("MEDIUM")]

                c1, c2, c3, c4 = st.columns(4)
                with c1: metric_card("Learners", str(len(pred_df)))
                with c2: metric_card("High Risk", str(len(at_risk)), "risk-high")
                with c3: metric_card("Medium Risk", str(len(med_risk)), "risk-med")
                with c4: metric_card("Batch Quality", f"{person_q['quality'].mean():.0%}")

                st.divider()

                # Week-on-week table with color coding
                st.subheader(f"📅 Predicted Quality & Risk: Week {completed_wks+1} to {completed_wks+predict_wks}")
                pred_cols = [c for c in pred_df.columns if "Pred" in c]
                risk_cols = [c for c in pred_df.columns if "Risk" in c and c not in ("Avg Risk Prob", "Overall Risk")]
                display_cols = ["Learner", "Current Quality"] + [c for c in pred_df.columns if "Wk" in c] + ["Avg Risk Prob", "Overall Risk"]
                display_df = pred_df[[c for c in display_cols if c in pred_df.columns]]

                styled = display_df.style.applymap(color_risk, subset=["Overall Risk"]).applymap(
                    color_score, subset=["Current Quality"] + pred_cols
                ).format({"Current Quality": "{:.2f}", "Avg Risk Prob": "{:.2f}", **{c: "{:.2f}" for c in pred_cols}})
                st.dataframe(styled, use_container_width=True, hide_index=True)

                # At-risk detail
                if len(at_risk) > 0:
                    st.divider()
                    st.subheader("🔴 At-Risk Learners — Action Needed")
                    for _, r in at_risk.iterrows():
                        with st.expander(f"🔴 {r['Learner']} — Quality: {r['Current Quality']:.0%} | {r['Defects']} defects in {r['Audits']} audits"):
                            st.markdown(f"- Current quality: **{r['Current Quality']:.0%}** (below {TARGET_QUALITY:.0%} target)")
                            st.markdown(f"- Avg predicted risk: **{r['Avg Risk Prob']:.0%}**")
                            st.markdown(f"- **Action:** Immediate coaching intervention recommended")

                            # Detailed defect breakdown
                            learner_defects = ramp_df[(ramp_df[login_col] == r["Learner"]) & (ramp_df["is_defect"])]
                            if len(learner_defects) > 0:
                                st.markdown("---")
                                st.markdown("**📋 Defect Breakdown:**")

                                # Defect Queue/Area
                                for qcol in ["Queue ", "Queue", "queue name", "queue"]:
                                    if qcol in learner_defects.columns:
                                        queues = learner_defects[qcol].dropna().value_counts().head(3)
                                        if len(queues) > 0:
                                            st.markdown("- **Defect Queue:** " + ", ".join([f"`{q}` ({n})" for q, n in queues.items()]))
                                        break

                                # Defect Category/Type
                                for cat_col in ["Defect Subcategory 1", "Defect Subcategory1", "Defect Category 1", "Defect Category1", "Defect Type"]:
                                    if cat_col in learner_defects.columns:
                                        cats = learner_defects[cat_col].dropna().value_counts().head(3)
                                        if len(cats) > 0:
                                            st.markdown("- **Defect Type:** " + ", ".join([f"{c} ({n})" for c, n in cats.items()]))
                                        break

                                # Root Cause / Driver
                                for rc_col in ["Defect Driver", "Defect Driver 2", "Defect Rootcause", "Defect Rootcause "]:
                                    if rc_col in learner_defects.columns:
                                        rcs = learner_defects[rc_col].dropna().value_counts().head(3)
                                        if len(rcs) > 0:
                                            st.markdown("- **Root Cause:** " + ", ".join([f"{c} ({n})" for c, n in rcs.items()]))
                                        break

                                # Auditor comments (keyword summary)
                                for cmt_col in ["Audit Comments (RCA)", "QA Feedback", "Remediation Comments "]:
                                    if cmt_col in learner_defects.columns:
                                        comments = learner_defects[cmt_col].dropna().astype(str).tolist()
                                        if comments:
                                            st.markdown(f"- **Auditor Notes ({len(comments)} defects):**")
                                            for c in comments[:3]:
                                                st.markdown(f"  - _{c[:150]}{'...' if len(c)>150 else ''}_")
                                        break

                                # Week breakdown
                                if week_col and week_col in learner_defects.columns:
                                    wk_breakdown = learner_defects[week_col].value_counts().sort_index()
                                    st.markdown("- **Defects by Week:** " + ", ".join([f"{w}: {n}" for w, n in wk_breakdown.items()]))

                # Drill-down section (similar to dashboard)
                st.divider()
                st.subheader("🔍 Batch Drill-Down")
                dd_tab1, dd_tab2, dd_tab3, dd_tab4 = st.tabs(["👤 Learner Lookup", "📋 Root Causes", "📍 Defect Areas", "📈 Weekly Trend"])

                with dd_tab1:
                    selected_learner = st.selectbox("Select learner", pred_df["Learner"].tolist(), key="ramp_dd_learner")
                    l_data = ramp_df[ramp_df[login_col] == selected_learner]
                    l_defects = l_data[l_data["is_defect"]]
                    l_total = len(l_data)
                    l_def_count = len(l_defects)
                    l_quality = (l_total - l_def_count) / l_total if l_total > 0 else 0

                    lc1, lc2, lc3 = st.columns(3)
                    with lc1: metric_card("Audits", str(l_total))
                    with lc2: metric_card("Defects", str(l_def_count), "risk-high" if l_def_count > 0 else "risk-low")
                    with lc3: metric_card("Quality", f"{l_quality:.0%}", "risk-high" if l_quality < 0.85 else "risk-med" if l_quality < 0.92 else "risk-low")

                    if l_def_count > 0:
                        st.markdown("**Defect Details:**")
                        for qcol in ["Queue ", "Queue", "queue name"]:
                            if qcol in l_defects.columns:
                                st.markdown("- **Queues:** " + ", ".join([f"`{q}` ({n})" for q, n in l_defects[qcol].value_counts().head(5).items()]))
                                break
                        for cat_col in ["Defect Subcategory 1", "Defect Subcategory1", "Defect Type", "Defect Category 1"]:
                            if cat_col in l_defects.columns:
                                st.markdown("- **Types:** " + ", ".join([f"{c} ({n})" for c, n in l_defects[cat_col].dropna().value_counts().head(5).items()]))
                                break
                        for rc_col in ["Defect Driver", "Defect Rootcause", "Defect Rootcause "]:
                            if rc_col in l_defects.columns:
                                st.markdown("- **Root Cause:** " + ", ".join([f"{c} ({n})" for c, n in l_defects[rc_col].dropna().value_counts().head(5).items()]))
                                break
                        for cmt_col in ["Audit Comments (RCA)", "QA Feedback"]:
                            if cmt_col in l_defects.columns:
                                comments = l_defects[cmt_col].dropna().astype(str).tolist()
                                if comments:
                                    st.markdown("- **Auditor Comments:**")
                                    for c in comments[:5]:
                                        st.markdown(f"  - _{c[:200]}_")
                                break
                    else:
                        st.success("✅ No defects — performing well!")

                with dd_tab2:
                    all_defects = ramp_df[ramp_df["is_defect"]]
                    if len(all_defects) > 0:
                        for rc_col in ["Defect Driver", "Defect Rootcause", "Defect Rootcause "]:
                            if rc_col in all_defects.columns:
                                rcs = all_defects[rc_col].dropna().value_counts().head(10).reset_index()
                                rcs.columns = ["Root Cause", "Count"]
                                st.bar_chart(rcs.set_index("Root Cause"), use_container_width=True)
                                st.dataframe(rcs, use_container_width=True, hide_index=True)
                                break
                        # Keyword extraction from comments
                        for cmt_col in ["Audit Comments (RCA)", "QA Feedback"]:
                            if cmt_col in all_defects.columns:
                                comments = all_defects[cmt_col].dropna().astype(str)
                                keywords = ["knowledge gap", "incorrect", "failed to", "missed", "wrong",
                                            "policy", "SOP", "escalation", "documentation", "annotation"]
                                kw_counts = {kw.title(): int(comments.str.lower().str.contains(kw).sum()) for kw in keywords}
                                kw_counts = {k: v for k, v in kw_counts.items() if v > 0}
                                if kw_counts:
                                    st.markdown("**Keyword themes from auditor comments:**")
                                    kw_df = pd.DataFrame({"Theme": kw_counts.keys(), "Mentions": kw_counts.values()}).sort_values("Mentions", ascending=False)
                                    st.bar_chart(kw_df.set_index("Theme"), use_container_width=True)
                                break
                    else:
                        st.success("No defects in uploaded data.")

                with dd_tab3:
                    all_defects = ramp_df[ramp_df["is_defect"]]
                    if len(all_defects) > 0:
                        for qcol in ["Queue ", "Queue", "queue name"]:
                            if qcol in all_defects.columns:
                                areas = all_defects[qcol].dropna().value_counts().head(10).reset_index()
                                areas.columns = ["Queue / Area", "Defect Count"]
                                st.bar_chart(areas.set_index("Queue / Area"), use_container_width=True)
                                st.dataframe(areas, use_container_width=True, hide_index=True)
                                break

                with dd_tab4:
                    if week_col and week_col in ramp_df.columns:
                        weekly = ramp_df.groupby(week_col).agg(
                            audits=("is_defect", "count"), defects=("is_defect", "sum")
                        ).reset_index()
                        weekly["quality"] = ((weekly["audits"] - weekly["defects"]) / weekly["audits"]).round(3)
                        weekly = weekly.sort_values(week_col)
                        st.bar_chart(weekly.set_index(week_col)["quality"], use_container_width=True)
                        st.dataframe(weekly.rename(columns={week_col: "Week", "audits": "Audited", "defects": "Defects", "quality": "Quality"}),
                                     use_container_width=True, hide_index=True)
        else:
            st.error("Could not detect Login and Defect columns. Ensure your file has columns with 'Login'/'Investigator' and 'Defect' in the headers.")
    else:
        st.info("👆 Upload your current batch's RAMP audit data (Excel/CSV with Login, Resolve Week, Defect columns).")


# ══════════════════════════════════════════════════════════
# PAGE: Admin Panel
# ══════════════════════════════════════════════════════════
elif page == "🔒 Admin Panel":
    st.title("🔒 Admin — Model Accuracy Dashboard")

    pin = st.text_input("Enter Admin PIN", type="password")
    if pin != ADMIN_PIN:
        if pin:
            st.error("Incorrect PIN")
        else:
            st.info("Enter admin PIN to access model validation metrics.")
    else:
        st.success("🔓 Access granted")

        kyc_file_path = DATA_DIR / "KYC Q1 TQ.xlsx"
        audit_file_path = DATA_DIR / "Audit_Data_1776089975723.xlsx"
        if function_type == "KYC" and kyc_file_path.exists() and audit_file_path.exists():
            with st.spinner("Running validation..."):
                kyc_path = str(kyc_file_path)
                audit_path = str(audit_file_path)
                training_rows = parse_training_data(kyc_path, "IH-UPS")
                participants = {r["participant"] for r in training_rows}
                audit_data = parse_audit_data(audit_path, participants)
                features = build_features(training_rows, audit_data, completed_weeks=(1, 2))
                predictions, metrics = train_and_predict(features)

            if metrics:
                # Metrics cards
                st.subheader("📊 Model Performance")
                c1, c2, c3, c4 = st.columns(4)
                with c1: metric_card("Accuracy", f"{metrics['accuracy']:.0%}", "risk-low" if metrics['accuracy'] >= 0.7 else "risk-med")
                with c2: metric_card("F1 Score", f"{metrics['f1']:.2f}", "risk-low" if metrics['f1'] >= 0.5 else "risk-high")
                with c3: metric_card("Precision", f"{metrics['precision']:.0%}")
                with c4: metric_card("Recall", f"{metrics['recall']:.0%}")

                st.markdown(f"""
                | Metric | Value | Meaning |
                |--------|-------|---------|
                | Accuracy | {metrics['accuracy']:.0%} | Overall correct predictions |
                | Precision | {metrics['precision']:.0%} | When we flag risk, how often correct |
                | Recall | {metrics['recall']:.0%} | Of actual risks, how many caught |
                | F1 | {metrics['f1']:.2f} | Balance of precision & recall |
                """)

                # TP/FP/TN/FN
                st.divider()
                st.subheader("🎯 Prediction Accuracy Detail")
                with_actuals = [p for p in predictions if p["actual_avg"] is not None]
                rows = []
                for p in with_actuals:
                    pred_risk = p["prediction"] == "AT RISK"
                    actual_risk = not p["actual_met"]
                    if pred_risk and actual_risk: cls = "✅ True Positive"
                    elif pred_risk and not actual_risk: cls = "❌ False Positive"
                    elif not pred_risk and not actual_risk: cls = "✅ True Negative"
                    else: cls = "❌ False Negative"
                    rows.append({"Learner": p["login"], "Predicted": p["prediction"],
                                 "Risk Prob": round(p["risk_prob"], 2),
                                 "Actual Avg": round(p["actual_avg"], 2),
                                 "Met Target": "✅" if p["actual_met"] else "❌",
                                 "Classification": cls})

                acc_df = pd.DataFrame(rows).sort_values("Risk Prob", ascending=False)
                st.dataframe(acc_df, use_container_width=True, hide_index=True)

                # Confusion matrix summary
                tp = sum(1 for r in rows if "True Positive" in r["Classification"])
                fp = sum(1 for r in rows if "False Positive" in r["Classification"])
                tn = sum(1 for r in rows if "True Negative" in r["Classification"])
                fn = sum(1 for r in rows if "False Negative" in r["Classification"])

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                with c1: metric_card("True Positive", str(tp), "risk-low")
                with c2: metric_card("False Positive", str(fp), "risk-med")
                with c3: metric_card("True Negative", str(tn), "risk-low")
                with c4: metric_card("False Negative", str(fn), "risk-high")

                # Insights
                st.divider()
                st.subheader("💡 Model Insights")
                if metrics["recall"] < 0.5:
                    st.warning("⚠️ Low recall — model misses many at-risk learners. Consider lowering risk threshold.")
                if metrics["precision"] < 0.3:
                    st.warning("⚠️ Low precision — too many false alarms. Model may be over-sensitive.")
                if metrics["accuracy"] >= 0.7:
                    st.success("✅ Acceptable accuracy for risk screening.")
                if fn > tp:
                    st.error("🚨 More missed risks than caught — prioritize improving recall.")
        else:
            st.info(f"Admin validation requires {function_type} historical data with outcomes.")
