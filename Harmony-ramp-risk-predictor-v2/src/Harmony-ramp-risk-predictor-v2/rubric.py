"""Rating rubric definitions for all 11 trainer attributes across 3 functions."""

ATTRIBUTES = [
    "communication", "confidence", "engagement", "problem_solving", "knowledge_depth",
    "critical_thinking", "deep_diving", "knowledge_retention", "attention_to_detail",
    "adaptability", "time_management",
]

RUBRIC = {
    "communication": {
        1: "Cannot articulate thoughts. Responses incoherent or off-topic. Unable to explain actions.",
        2: "Struggles to communicate. Needs to repeat/rephrase often. Misses key info.",
        3: "Adequate. Gets point across but lacks structure. Occasionally unclear.",
        4: "Clear and structured. Explains actions well. Asks relevant questions.",
        5: "Exceptional. Concise, precise, professional. Explains complex cases with clarity.",
    },
    "confidence": {
        1: "Extremely hesitant. Cannot decide without hand-holding. Freezes on unfamiliar cases.",
        2: "Low confidence. Second-guesses frequently. Needs reassurance before acting.",
        3: "Moderate. Handles routine independently but hesitates on edge cases.",
        4: "Confident in most scenarios. Seeks guidance only for genuinely complex cases.",
        5: "Highly decisive. Handles ambiguous cases with composure. Independent from day one.",
    },
    "engagement": {
        1: "Disengaged. Frequently absent or distracted. No participation.",
        2: "Minimal. Attends but rarely participates. No initiative.",
        3: "Adequate. Participates when prompted. Completes tasks but nothing beyond.",
        4: "Active. Volunteers answers, asks questions, helps peers. Genuine interest.",
        5: "Exceptional. Drives discussions, seeks extra practice, mentors peers.",
    },
    "problem_solving": {
        1: "Cannot analyze independently. Misses obvious signals. Wrong actions on simple cases.",
        2: "Struggles with analysis. Basic cases OK but fails on multi-step judgment.",
        3: "Adequate. Standard cases correct. Struggles with edge cases or conflicts.",
        4: "Strong. Identifies patterns, handles complex cases, considers multiple factors.",
        5: "Exceptional. Quick root cause ID, novel scenarios handled, proposes improvements.",
    },
    "knowledge_depth": {
        1: "Fundamental gaps. Cannot recall basic SOPs even with prompting.",
        2: "Knows basics but significant gaps. Frequently references docs for routine tasks.",
        3: "Solid foundation. Standard processes known. Gaps in advanced/cross-functional areas.",
        4: "Deep across most areas. Understands nuances, exceptions, dependencies.",
        5: "Expert-level. End-to-end process knowledge, edge cases, policy rationale.",
    },
    "critical_thinking": {
        1: "Takes information at face value. No questioning or analysis of data presented.",
        2: "Occasionally questions data but cannot form independent conclusions.",
        3: "Can identify inconsistencies when prompted. Basic cause-effect reasoning.",
        4: "Proactively identifies gaps in information. Draws logical conclusions from evidence.",
        5: "Exceptional analytical mind. Challenges assumptions, connects disparate data points, anticipates downstream impacts.",
    },
    "deep_diving": {
        1: "Surface-level investigation only. Accepts first answer without further probing.",
        2: "Occasionally digs deeper but stops too early. Misses underlying patterns.",
        3: "Adequate investigation depth for standard cases. Stops at obvious root cause.",
        4: "Thorough investigation. Explores multiple angles, checks related data, finds hidden patterns.",
        5: "Exhaustive deep-diver. Uncovers systemic issues, traces full chain of events, documents findings comprehensively.",
    },
    "knowledge_retention": {
        1: "Forgets previously taught concepts within days. Repeats same mistakes.",
        2: "Retains basics but frequently forgets procedures taught in prior sessions.",
        3: "Retains most concepts but needs occasional refreshers on complex topics.",
        4: "Strong retention. Applies previously learned concepts to new situations without prompting.",
        5: "Exceptional memory. Recalls and applies training from weeks ago. Builds on prior knowledge independently.",
    },
    "attention_to_detail": {
        1: "Misses critical details regularly. Errors in basic data entry and case documentation.",
        2: "Catches obvious details but misses subtle cues. Inconsistent documentation.",
        3: "Adequate attention for routine cases. Occasionally misses nuances in complex cases.",
        4: "Thorough. Catches subtle discrepancies, documents comprehensively, verifies before acting.",
        5: "Meticulous. Zero tolerance for errors. Catches issues others miss. Perfect documentation.",
    },
    "adaptability": {
        1: "Cannot handle any deviation from trained scenarios. Panics with new case types.",
        2: "Struggles with change. Needs extensive support when processes update.",
        3: "Adapts to minor changes with some guidance. Takes time with major shifts.",
        4: "Adapts quickly to new processes. Applies existing knowledge to novel situations.",
        5: "Thrives in ambiguity. Quickly masters new tools/processes. Helps others adapt.",
    },
    "time_management": {
        1: "Cannot manage workload. Consistently misses deadlines. No prioritization.",
        2: "Struggles with volume. Often behind on tasks. Needs help prioritizing.",
        3: "Manages standard workload. Occasionally falls behind during peak periods.",
        4: "Efficient. Handles full workload within SLA. Prioritizes effectively.",
        5: "Exceptional efficiency. Completes ahead of schedule. Helps others manage backlog.",
    },
}

# Function-specific context for rubric
FUNCTION_CONTEXT = {
    "KYC": "KYC (Know Your Customer) — Seller identity verification, document review, compliance checks",
    "SAP": "SAP (Seller Abuse Prevention) — Investigating seller policy violations, appeals, abuse patterns",
    "SAM": "SAM (Seller Account Management) — Account health, payment investigations, seller support",
}
