import pandas as pd

def answer_question(question, data_context):
   q = question.lower().strip()
   hist_df = data_context.get("hist_df")
   
   if hist_df is None or len(hist_df) == 0:
       return "No data loaded. Upload historical audit data first."
   
   has_defect = "is_defect" in hist_df.columns
   has_login = "Login" in hist_df.columns
   has_week = "Resolve Week" in hist_df.columns
   
   # Build person quality table
   person_q = None
   if has_login and has_defect:
       person_q = hist_df.groupby("Login").agg(
           audits=("is_defect","count"), defects=("is_defect","sum")
       ).reset_index()
       person_q["quality"] = ((person_q["audits"]-person_q["defects"])/person_q["audits"]).round(3)
       person_q = person_q.sort_values("quality")
   
   # Check if asking about a specific person
   if has_login:
       for login in hist_df["Login"].unique():
           if login.lower() in q:
               data = hist_df[hist_df["Login"]==login]
               defs = data["is_defect"].sum() if has_defect else 0
               qual = (len(data)-defs)/len(data)
               result = f"**{login}**: {qual:.0%} quality | {len(data)} audits | {defs} defects"
               # Add defect details
               if defs > 0:
                   for col in ["Defect Driver","Defect Type","Defect Subcategory 1","Defect Subcategory1"]:
                       if col in data.columns:
                           top = data[data["is_defect"]][col].dropna().value_counts().head(3)
                           if len(top)>0:
                               result += f"\n\nDefect drivers: " + ", ".join([f"{k} ({v})" for k,v in top.items()])
                           break
               return result
   
   # Worst/risk/bottom performers
   if any(w in q for w in ["worst","lowest","bottom","risk","struggling","weak","poor"]):
       if person_q is not None:
           bottom = person_q.head(5)
           lines = "\n".join([f"- **{r['Login']}**: {r['quality']:.0%} ({r['defects']} defects / {r['audits']} audits)" for _,r in bottom.iterrows()])
           return f"Bottom 5 performers:\n{lines}"
   
   # Best/top performers
   if any(w in q for w in ["best","top","highest","strong"]):
       if person_q is not None:
           top = person_q.tail(5).iloc[::-1]
           lines = "\n".join([f"- **{r['Login']}**: {r['quality']:.0%} ({r['audits']} audits)" for _,r in top.iterrows()])
           return f"Top 5 performers:\n{lines}"
   
   # Root cause / why / reason
   if any(w in q for w in ["root cause","why","reason","driver","cause"]):
       for col in ["Defect Driver","Defect Rootcause","Defect Rootcause ","Defect Type"]:
           if col in hist_df.columns and has_defect:
               top = hist_df[hist_df["is_defect"]][col].dropna().value_counts().head(7)
               if len(top)>0:
                   lines = "\n".join([f"- **{k}**: {v} ({v/hist_df['is_defect'].sum()*100:.0f}%)" for k,v in top.items()])
                   return f"Top defect drivers:\n{lines}"
       return "No root cause data found in the audit file."
   
   # Queue / area / where
   if any(w in q for w in ["queue","area","where","segment","which"]):
       for col in ["Queue ","Queue","queue name","Function"]:
           if col in hist_df.columns and has_defect:
               top = hist_df[hist_df["is_defect"]][col].dropna().value_counts().head(7)
               if len(top)>0:
                   lines = "\n".join([f"- **{k}**: {v} defects" for k,v in top.items()])
                   return f"Defects by area:\n{lines}"
       return "No queue/area data found."
   
   # Count / how many
   if any(w in q for w in ["how many","count","total","number"]):
       if "defect" in q and has_defect:
           t = int(hist_df["is_defect"].sum())
           return f"**{t}** defects out of {len(hist_df)} total audits ({t/len(hist_df):.1%} defect rate)"
       if any(w in q for w in ["learner","investigator","people","person"]):
           return f"**{hist_df['Login'].nunique()}** unique investigators" if has_login else "Cannot determine - no Login column"
       if "audit" in q:
           return f"**{len(hist_df)}** total audits in the dataset"
   
   # Week / trend / time
   if any(w in q for w in ["week","trend","time","when"]):
       if has_week and has_defect:
           weekly = hist_df.groupby("Resolve Week").agg(a=("is_defect","count"),d=("is_defect","sum")).reset_index()
           weekly["quality"] = ((weekly["a"]-weekly["d"])/weekly["a"]).round(3)
           weekly = weekly.sort_values("Resolve Week")
           worst_wk = weekly.sort_values("quality").iloc[0]
           best_wk = weekly.sort_values("quality",ascending=False).iloc[0]
           return f"**Best week**: {best_wk['Resolve Week']} ({best_wk['quality']:.0%})\n**Worst week**: {worst_wk['Resolve Week']} ({worst_wk['quality']:.0%})\n**Weeks in data**: {len(weekly)}"
   
   # Average / overall / summary
   if any(w in q for w in ["average","overall","summary","quality"]):
       if has_defect:
           qual = (len(hist_df)-hist_df["is_defect"].sum())/len(hist_df)
           return f"**Overall quality: {qual:.1%}**\nTotal audits: {len(hist_df)}\nTotal defects: {int(hist_df['is_defect'].sum())}\nInvestigators: {hist_df['Login'].nunique() if has_login else 'N/A'}"
   
   # Compare
   if "compare" in q or " vs " in q:
       if has_login:
           found = [l for l in hist_df["Login"].unique() if l.lower() in q]
           if len(found)>=2:
               results = []
               for login in found[:2]:
                   data = hist_df[hist_df["Login"]==login]
                   defs = data["is_defect"].sum()
                   qual = (len(data)-defs)/len(data)
                   results.append(f"**{login}**: {qual:.0%} quality ({defs} defects / {len(data)} audits)")
               return "\n".join(results)
           return "Mention two login names to compare."
   
   # Fallback - show summary
   if has_defect:
       qual = (len(hist_df)-hist_df["is_defect"].sum())/len(hist_df)
       return f"I can answer questions about your data.\n\n**Quick stats**: {qual:.0%} quality, {len(hist_df)} audits, {int(hist_df['is_defect'].sum())} defects, {hist_df['Login'].nunique() if has_login else '?'} investigators\n\n**Try asking**:\n- Who is the worst performer?\n- What are the root causes?\n- Which queue has most defects?\n- Show me weekly trend\n- Tell me about [login name]"
   
   return "Upload audit data and try asking about performers, defects, root causes, queues, or weekly trends."
