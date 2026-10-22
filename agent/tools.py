"""CampusPilot AI tools: internship/scholarship search, learning resources, career planning, comparison.

Every tool has a clear one-line docstring — the tool-selection decision pattern reads that line
as the option description, so keep it accurate and specific.

DATA NOTE: all records in agent/data/ are clearly labelled sample data (data_source = "sample").
No record represents a verified live opportunity. Users must verify directly with the organisation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from strands import tool

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_opportunities() -> dict:
    return json.loads((_DATA_DIR / "opportunities.json").read_text())


def _load_resources() -> dict:
    return json.loads((_DATA_DIR / "resources.json").read_text())


def _year_match(record_years: list[int], requested_year: int | None) -> bool:
    if requested_year is None:
        return True
    return requested_year in record_years


def _skills_overlap(record_skills: list[str], wanted: list[str]) -> bool:
    """True when at least one wanted skill appears (case-insensitive) in the record's skill list."""
    if not wanted:
        return True
    lc_record = [s.lower() for s in record_skills]
    return any(w.lower() in " ".join(lc_record) for w in wanted)


def _extract_year(query: str) -> int | None:
    m = re.search(r"\b([1-4])(?:st|nd|rd|th)?\s*year\b", query, re.I)
    return int(m.group(1)) if m else None


def _extract_skills(query: str) -> list[str]:
    """Very lightweight: pull well-known skill keywords from freetext."""
    keywords = [
        "python", "java", "javascript", "react", "c\\+\\+", "c#", "go", "rust",
        "dsa", "data structures", "algorithms", "machine learning", "ml", "deep learning",
        "sql", "databases", "linux", "docker", "kubernetes", "aws", "cloud",
        "android", "flutter", "react native", "django", "flask", "node", "spring",
        "networking", "cybersecurity", "security", "devops", "git", "tensorflow", "pytorch",
        "html", "css", "system design", "os", "operating systems",
    ]
    found = []
    for kw in keywords:
        if re.search(r"\b" + kw + r"\b", query, re.I):
            found.append(kw.replace("\\+\\+", "++"))
    return found


@tool
def search_opportunities(query: str) -> dict:
    """Search internship and scholarship opportunities by domain, year of study, or skill keywords."""
    data = _load_opportunities()
    year = _extract_year(query)
    skills = _extract_skills(query)
    query_lower = query.lower()

    # Determine whether to filter by type
    want_internships = "scholarship" not in query_lower
    want_scholarships = "internship" not in query_lower

    results: list[dict] = []

    if want_internships:
        for opp in data["internships"]:
            if not _year_match(opp["year_of_study"], year):
                continue
            if not _skills_overlap(opp["skills_required"], skills):
                # fall back: domain keyword match
                if not any(t in query_lower for t in opp["domain"].lower().split()):
                    continue
            results.append({
                "id": opp["id"],
                "type": "internship",
                "title": opp["title"],
                "organisation": opp["organisation"],
                "domain": opp["domain"],
                "skills_required": opp["skills_required"],
                "year_of_study": opp["year_of_study"],
                "duration_weeks": opp["duration_weeks"],
                "paid": opp["paid"],
                "stipend_inr": opp.get("stipend_inr", 0),
                "mode": opp["mode"],
                "deadline": opp["deadline"],
                "apply_url": opp["apply_url"],
                "description": opp["description"],
                "data_source": opp["data_source"],
            })

    if want_scholarships:
        for sch in data["scholarships"]:
            if not _year_match(sch["year_of_study"], year):
                continue
            if not any(t in query_lower for t in sch["domain"].lower().split()) and not want_internships:
                pass  # keep all scholarships when explicitly asked
            results.append({
                "id": sch["id"],
                "type": "scholarship",
                "title": sch["title"],
                "organisation": sch["organisation"],
                "domain": sch["domain"],
                "eligibility": sch["eligibility"],
                "year_of_study": sch["year_of_study"],
                "amount_inr": sch["amount_inr"],
                "renewable": sch["renewable"],
                "deadline": sch["deadline"],
                "apply_url": sch["apply_url"],
                "description": sch["description"],
                "data_source": sch["data_source"],
            })

    disclaimer = (
        "⚠️ SAMPLE DATA: These are synthetic records for demonstration only. "
        "Always verify deadlines, eligibility, and application details directly with the organisation."
    )
    if not results:
        return {
            "results": [],
            "count": 0,
            "disclaimer": disclaimer,
            "message": "No matching opportunities found for your query. Try broadening your search.",
        }
    return {"results": results[:8], "count": len(results), "disclaimer": disclaimer}


@tool
def find_learning_resources(query: str) -> dict:
    """Find free and paid courses, tutorials, and skill-building resources by topic or technology."""
    data = _load_resources()
    query_lower = query.lower()
    skills = _extract_skills(query)
    want_free = "free" in query_lower

    scored: list[tuple[int, dict]] = []
    for course in data["courses"]:
        score = 0
        # Skill/domain/topic match
        for sk in skills:
            if sk in course["domain"].lower() or any(sk in t.lower() for t in course["topics"]):
                score += 2
        # Direct keyword match in title or domain
        for word in re.split(r"\W+", query_lower):
            if len(word) > 2 and (word in course["domain"].lower() or word in course["title"].lower()):
                score += 1
        if want_free and not course["free"]:
            score -= 2
        if not want_free and course["free"]:
            score += 0  # still include free ones
        if score > 0 or not skills:
            scored.append((score, course))

    scored.sort(key=lambda x: -x[0])
    results = [
        {
            "id": c["id"],
            "title": c["title"],
            "provider": c["provider"],
            "domain": c["domain"],
            "topics": c["topics"],
            "level": c["level"],
            "free": c["free"],
            "url": c["url"],
            "duration_hours": c["duration_hours"],
            "description": c["description"],
            "data_source": c["data_source"],
        }
        for _, c in scored[:6]
    ]

    disclaimer = (
        "⚠️ SAMPLE DATA: Course details, pricing, and availability should be verified "
        "directly with the course providers."
    )
    if not results:
        return {
            "results": [],
            "count": 0,
            "disclaimer": disclaimer,
            "message": "No matching resources found. Try searching by technology name (e.g. 'Python', 'DSA', 'AWS').",
        }
    return {"results": results, "count": len(results), "disclaimer": disclaimer}


@tool
def build_career_plan(goal: str) -> dict:
    """Build a structured weekly placement preparation plan or career roadmap based on a student's goal."""
    goal_lower = goal.lower()

    # Detect goal type
    is_placement = any(w in goal_lower for w in ["placement", "campus", "job", "interview", "hire", "crack"])
    is_ml = any(w in goal_lower for w in ["machine learning", "ml", "data science", "ai ", " ai"])
    is_web = any(w in goal_lower for w in ["web", "frontend", "backend", "fullstack", "full stack"])
    is_cloud = any(w in goal_lower for w in ["cloud", "aws", "azure", "devops"])
    is_intern = any(w in goal_lower for w in ["internship", "intern"])

    # Extract duration hint
    weeks_m = re.search(r"\b(\d+)\s*week", goal_lower)
    target_weeks = int(weeks_m.group(1)) if weeks_m else (12 if is_placement else 8)
    target_weeks = max(4, min(target_weeks, 20))

    if is_placement or (not is_ml and not is_web and not is_cloud):
        plan_type = "placement"
        phases = _placement_plan(target_weeks)
    elif is_ml:
        plan_type = "ml_career"
        phases = _ml_plan(target_weeks)
    elif is_web:
        plan_type = "web_career"
        phases = _web_plan(target_weeks)
    else:
        plan_type = "cloud_career"
        phases = _cloud_plan(target_weeks)

    resources_data = _load_resources()
    resources_data  # available for future expansion — not iterated to keep response compact

    disclaimer = (
        "📋 This plan is AI-generated guidance. Adjust to your current skill level and college schedule. "
        "Specific course links are sample data — verify with providers."
    )
    return {
        "plan_type": plan_type,
        "goal": goal,
        "total_weeks": target_weeks,
        "phases": phases,
        "tips": [
            "Practise DSA on LeetCode every day — consistency beats cramming.",
            "Build at least one portfolio project you can demo in an interview.",
            "Contribute to open source early: even small PRs build your GitHub profile.",
            "Mock interviews with peers are as valuable as solo study.",
        ],
        "disclaimer": disclaimer,
    }


def _placement_plan(weeks: int) -> list[dict]:
    w = weeks
    phases = []
    p1 = max(2, w // 4)
    p2 = max(2, w // 4)
    p3 = max(2, w // 4)
    p4 = w - p1 - p2 - p3
    phases.append({
        "phase": 1, "name": "Foundations",
        "weeks": f"1–{p1}",
        "focus": "Strengthen core CS: DSA basics (arrays, strings, sorting), OOP, SQL",
        "daily_tasks": ["1 LeetCode easy/medium problem", "1 chapter of CLRS or GFG DSA", "30-min SQL practice"],
        "resources": ["LeetCode Problems — Beginner to Medium (Free)", "CS50 (Free)"],
    })
    phases.append({
        "phase": 2, "name": "Intermediate DSA + OS/DBMS",
        "weeks": f"{p1+1}–{p1+p2}",
        "focus": "Trees, graphs, DP, recursion; OS and DBMS concepts for technical rounds",
        "daily_tasks": ["2 LeetCode medium problems", "OS / DBMS chapter revision", "One mock quiz"],
        "resources": ["Operating Systems: Three Easy Pieces (Free)", "LeetCode Problems — Beginner to Medium (Free)"],
    })
    phases.append({
        "phase": 3, "name": "Projects + System Design",
        "weeks": f"{p1+p2+1}–{p1+p2+p3}",
        "focus": "Build a portfolio project; intro to system design",
        "daily_tasks": ["Work on personal project", "Read one system design case study", "1 LeetCode hard attempt"],
        "resources": ["System Design Interview Prep"],
    })
    phases.append({
        "phase": 4, "name": "Mock Interviews + Applications",
        "weeks": f"{p1+p2+p3+1}–{w}",
        "focus": "Full mock interview loop, resume polishing, apply to internships",
        "daily_tasks": ["1 mock interview (with peer or tool)", "Resume update", "Apply to 2 opportunities"],
        "resources": ["search_opportunities tool: use it to find matching internships"],
    })
    return phases


def _ml_plan(weeks: int) -> list[dict]:
    return [
        {"phase": 1, "name": "Python + Math Foundations", "weeks": f"1–{max(2, weeks//4)}",
         "focus": "Python fluency, linear algebra, probability, statistics",
         "daily_tasks": ["Python exercises", "Khan Academy linear algebra", "Statistics notes"],
         "resources": ["Python for Everybody Specialisation"]},
        {"phase": 2, "name": "Core ML Algorithms", "weeks": f"{max(2,weeks//4)+1}–{max(4,weeks//2)}",
         "focus": "Regression, classification, clustering, model evaluation",
         "daily_tasks": ["Implement algorithm from scratch", "Kaggle beginner dataset", "Read a paper abstract"],
         "resources": ["Machine Learning Crash Course (Free)"]},
        {"phase": 3, "name": "Deep Learning + Projects", "weeks": f"{max(4,weeks//2)+1}–{weeks}",
         "focus": "Neural networks, CNNs, NLP basics; complete one end-to-end project",
         "daily_tasks": ["PyTorch/TF tutorial", "Work on project", "1 LeetCode problem (keep DSA sharp)"],
         "resources": ["Machine Learning Crash Course (Free)", "find_learning_resources tool for DL courses"]},
    ]


def _web_plan(weeks: int) -> list[dict]:
    return [
        {"phase": 1, "name": "HTML, CSS, JavaScript", "weeks": f"1–{max(2, weeks//4)}",
         "focus": "Build static pages, understand the DOM, basic JS",
         "daily_tasks": ["Build a small UI component", "MDN docs reading", "CSS challenge"],
         "resources": ["CS50 (Free)"]},
        {"phase": 2, "name": "React + Backend Basics", "weeks": f"{max(2,weeks//4)+1}–{max(4,weeks//2)}",
         "focus": "React, REST APIs, Node.js or Python Flask/Django basics",
         "daily_tasks": ["Build a React component", "Write a REST endpoint", "Read an API doc"],
         "resources": ["React — The Complete Guide", "Python for Everybody Specialisation"]},
        {"phase": 3, "name": "Full-Stack Project + Deployment", "weeks": f"{max(4,weeks//2)+1}–{weeks}",
         "focus": "Ship a full-stack project to a public URL, write tests, document the API",
         "daily_tasks": ["Feature commit to project", "Write one test", "Prep a 2-minute project pitch"],
         "resources": ["AWS Cloud Practitioner Essentials (Free)"]},
    ]


def _cloud_plan(weeks: int) -> list[dict]:
    return [
        {"phase": 1, "name": "Cloud Fundamentals", "weeks": f"1–{max(2, weeks//3)}",
         "focus": "AWS / Azure core services, IAM, S3, EC2, networking basics",
         "daily_tasks": ["AWS free-tier lab", "Read a service FAQ", "Linux command practice"],
         "resources": ["AWS Cloud Practitioner Essentials (Free)"]},
        {"phase": 2, "name": "Infrastructure as Code + CI/CD", "weeks": f"{max(2,weeks//3)+1}–{max(4,2*weeks//3)}",
         "focus": "Terraform or CDK basics, Docker, GitHub Actions",
         "daily_tasks": ["Write a Terraform resource", "Dockerise a small app", "Set up a simple pipeline"],
         "resources": ["find_learning_resources tool for DevOps courses"]},
        {"phase": 3, "name": "Certification Prep + Project", "weeks": f"{max(4,2*weeks//3)+1}–{weeks}",
         "focus": "AWS Cloud Practitioner or Solutions Architect Associate prep; deploy a project",
         "daily_tasks": ["Practice exam questions", "Work on cloud project", "Review IAM and security"],
         "resources": ["AWS Cloud Practitioner Essentials (Free)"]},
    ]


@tool
def compare_opportunities(ids: str) -> dict:
    """Compare two or more internships or scholarships side by side by eligibility, skills, duration, and value."""
    id_list = [x.strip().upper() for x in re.split(r"[,\s]+", ids) if x.strip()]
    if len(id_list) < 2:
        return {"error": "Please provide at least two opportunity IDs separated by commas, e.g. 'INT001, INT002'."}

    data = _load_opportunities()
    all_records = {r["id"]: {**r, "type": "internship"} for r in data["internships"]}
    all_records.update({r["id"]: {**r, "type": "scholarship"} for r in data["scholarships"]})

    found = []
    not_found = []
    for oid in id_list:
        if oid in all_records:
            found.append(all_records[oid])
        else:
            not_found.append(oid)

    if len(found) < 2:
        return {
            "error": f"Could not find enough records to compare. Not found: {not_found}. "
                     "Use search_opportunities to discover valid IDs."
        }

    comparison: list[dict] = []
    for rec in found:
        if rec["type"] == "internship":
            entry = {
                "id": rec["id"], "type": "internship", "title": rec["title"],
                "organisation": rec["organisation"], "domain": rec["domain"],
                "skills_required": rec["skills_required"],
                "year_of_study": rec["year_of_study"],
                "duration_weeks": rec["duration_weeks"],
                "paid": rec["paid"], "stipend_inr": rec.get("stipend_inr", 0),
                "mode": rec["mode"], "deadline": rec["deadline"],
                "apply_url": rec["apply_url"], "data_source": rec["data_source"],
            }
        else:
            entry = {
                "id": rec["id"], "type": "scholarship", "title": rec["title"],
                "organisation": rec["organisation"], "domain": rec["domain"],
                "eligibility": rec["eligibility"],
                "year_of_study": rec["year_of_study"],
                "amount_inr": rec["amount_inr"],
                "renewable": rec["renewable"], "deadline": rec["deadline"],
                "apply_url": rec["apply_url"], "data_source": rec["data_source"],
            }
        comparison.append(entry)

    # Build a simple text summary of differences
    summary_lines = []
    if all(r["type"] == "internship" for r in found):
        durations = {r["id"]: r["duration_weeks"] for r in found}
        best_duration = max(durations, key=durations.get)
        stipends = {r["id"]: r.get("stipend_inr", 0) for r in found}
        best_stipend = max(stipends, key=stipends.get)
        summary_lines.append(f"Longest duration: {best_duration} ({durations[best_duration]} weeks).")
        summary_lines.append(f"Highest stipend: {best_stipend} (₹{stipends[best_stipend]:,}/month).")
        paid_ones = [r["id"] for r in found if r.get("paid")]
        if paid_ones:
            summary_lines.append(f"Paid internships: {', '.join(paid_ones)}.")
        unpaid = [r["id"] for r in found if not r.get("paid")]
        if unpaid:
            summary_lines.append(f"Unpaid: {', '.join(unpaid)} — valuable for experience and portfolio.")
    elif all(r["type"] == "scholarship" for r in found):
        amounts = {r["id"]: r.get("amount_inr", 0) for r in found}
        best_amt = max(amounts, key=amounts.get)
        summary_lines.append(f"Highest value: {best_amt} (₹{amounts[best_amt]:,}).")
        renewable = [r["id"] for r in found if r.get("renewable")]
        if renewable:
            summary_lines.append(f"Renewable: {', '.join(renewable)} — can be claimed multiple years.")
    else:
        summary_lines.append("Mixed types: internship(s) and scholarship(s) — apply to both for maximum benefit.")

    if not_found:
        summary_lines.append(f"IDs not found in dataset: {', '.join(not_found)}.")

    disclaimer = (
        "⚠️ SAMPLE DATA: This comparison is based on synthetic records. "
        "Verify all details directly with the organisations before applying."
    )
    return {
        "comparison": comparison,
        "summary": " ".join(summary_lines),
        "not_found": not_found,
        "disclaimer": disclaimer,
    }


TOOLS = [search_opportunities, find_learning_resources, build_career_plan, compare_opportunities]
