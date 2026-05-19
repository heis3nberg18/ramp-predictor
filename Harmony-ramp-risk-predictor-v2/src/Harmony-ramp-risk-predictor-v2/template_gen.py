"""Template generator with raw dump instructions and full rubric."""
import pandas as pd
from io import BytesIO
from rubric import RUBRIC, ATTRIBUTES, FUNCTION_CONTEXT


def generate_template(function_type):
    """Generate training data template with instructions and rubric."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Sheet 1: Mid Term ──
        instructions_mt = pd.DataFrame({
            "INSTRUCTIONS": [
                "DUMP RAW DATA BELOW — Include topic-wise question-level data",
                "Required columns: Learner Login/Name, Topic/Section, Question, Answer, Score/Result",
                "The model extracts topic-wise performance patterns from raw data",
                "You can include any additional columns — the system will parse intelligently",
                "",
                "EXAMPLE FORMAT:",
            ],
        })
        example_mt = pd.DataFrame({
            "Learner": ["john_doe", "john_doe", "john_doe", "jane_smith"],
            "Topic": ["Policy Basics", "Document Review", "Escalation Process", "Policy Basics"],
            "Question": ["Q1: What is the SLA?", "Q2: Valid ID types?", "Q3: When to escalate?", "Q1: What is the SLA?"],
            "Correct": ["Yes", "Yes", "No", "Yes"],
            "Score": [1, 1, 0, 1],
            "Total Marks": [1, 1, 1, 1],
        })
        instructions_mt.to_excel(writer, sheet_name="Mid Term", index=False, startrow=0)
        example_mt.to_excel(writer, sheet_name="Mid Term", index=False, startrow=8)

        # ── Sheet 2: Final Assessment ──
        instructions_fa = pd.DataFrame({
            "INSTRUCTIONS": [
                "DUMP RAW DATA BELOW — Include topic-wise question-level data",
                "Same format as Mid Term — topic, question, answer, score per learner",
                "This helps identify which topics improved vs remained weak",
            ],
        })
        example_fa = pd.DataFrame({
            "Learner": ["john_doe", "john_doe", "jane_smith"],
            "Topic": ["Advanced Cases", "Compliance", "Advanced Cases"],
            "Question": ["Q1: Complex scenario", "Q2: Regulatory requirement", "Q1: Complex scenario"],
            "Correct": ["Yes", "Yes", "No"],
            "Score": [1, 1, 0],
        })
        instructions_fa.to_excel(writer, sheet_name="Final Assessment", index=False, startrow=0)
        example_fa.to_excel(writer, sheet_name="Final Assessment", index=False, startrow=5)

        # ── Sheet 3: Resolved Cases ──
        instructions_rc = pd.DataFrame({
            "INSTRUCTIONS": [
                "DUMP RAW LITTWEB DATA BELOW",
                "Include: Learner, Case ID, Topic/Queue, Questions answered, Scores per question",
                "The model uses per-question and per-topic patterns to identify weak areas",
                "Paste the full LittWeb export — system will parse automatically",
            ],
        })
        example_rc = pd.DataFrame({
            "Learner Alias": ["john_doe", "john_doe", "jane_smith"],
            "Case Type": ["Appeals", "Transfers", "Appeals"],
            "Total Actions": [4, 3, 4],
            "Correct Actions": [4, 2, 3],
            "AR%": [1.0, 0.67, 0.75],
            "Avg Score": [0.92, 0.78, 0.81],
        })
        instructions_rc.to_excel(writer, sheet_name="Resolved Cases", index=False, startrow=0)
        example_rc.to_excel(writer, sheet_name="Resolved Cases", index=False, startrow=6)

        # ── Sheet 4: Live Cases ──
        pd.DataFrame({
            "INSTRUCTIONS": [
                "DUMP RAW OBSERVATION DATA BELOW",
                "Score each learner 0-10 on live case handling",
                "Include: Learner, Case Type/Queue, Score, Observer Notes",
                "Optional — leave blank if not conducted for this batch",
            ],
        }).to_excel(writer, sheet_name="Live Cases", index=False, startrow=0)
        pd.DataFrame({
            "Learner": ["john_doe", "jane_smith"],
            "Case Type": ["Appeals", "Transfers"],
            "Score (0-10)": [8.5, 6.0],
            "Notes": ["Confident handling", "Hesitant on escalation decision"],
        }).to_excel(writer, sheet_name="Live Cases", index=False, startrow=6)

        # ── Sheet 5: Trainer Ratings ──
        # Build rating columns
        rating_cols = {"Learner Login": ["john_doe", "jane_smith"]}
        for attr in ATTRIBUTES:
            display_name = attr.replace("_", " ").title() + " (1-5)"
            rating_cols[display_name] = [4, 3]
        rating_cols["Comments"] = ["Strong performer overall", "Needs work on complex cases"]

        pd.DataFrame({
            "INSTRUCTIONS": [
                "Rate each learner 1-5 on ALL attributes below",
                "Refer to the RUBRIC sheet for exact definitions of each score level",
                f"Function context: {FUNCTION_CONTEXT[function_type]}",
                "Add free-text comments in the Comments column",
            ],
        }).to_excel(writer, sheet_name="Trainer Ratings", index=False, startrow=0)
        pd.DataFrame(rating_cols).to_excel(writer, sheet_name="Trainer Ratings", index=False, startrow=6)

        # ── Sheet 6: Miscellaneous ──
        pd.DataFrame({
            "INSTRUCTIONS": [
                "DUMP ANY OTHER TRAINING DATA BELOW",
                "Daily polls, quizzes, activity scores, participation data, etc.",
                "Include: Learner, Activity Type, Score/Result, Date (if available)",
                "The model uses this as supplementary signal for knowledge retention",
            ],
        }).to_excel(writer, sheet_name="Miscellaneous", index=False, startrow=0)
        pd.DataFrame({
            "Learner": ["john_doe", "john_doe", "jane_smith"],
            "Activity": ["Daily Poll Wk1", "Daily Poll Wk2", "Daily Poll Wk1"],
            "Score": [90, 85, 65],
            "Date": ["2026-01-06", "2026-01-13", "2026-01-06"],
        }).to_excel(writer, sheet_name="Miscellaneous", index=False, startrow=6)

        # ── Sheet 7: RUBRIC ──
        rubric_rows = []
        for attr in ATTRIBUTES:
            for score, desc in sorted(RUBRIC[attr].items()):
                rubric_rows.append({
                    "Attribute": attr.replace("_", " ").title(),
                    "Score": score,
                    "Definition": desc,
                })
        rubric_df = pd.DataFrame(rubric_rows)
        rubric_df.to_excel(writer, sheet_name="RUBRIC", index=False)

        # Format rubric sheet
        ws = writer.sheets["RUBRIC"]
        ws.set_column("A:A", 22)
        ws.set_column("B:B", 8)
        ws.set_column("C:C", 80)

    return output.getvalue()
