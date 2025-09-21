import os
import json
import csv
import requests
import pandas as pd
from pathlib import Path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI
import RateMyProfessor_Database_APIs

# ----------------- OpenAI client -----------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cache path
CACHE_PATH = Path("canvas_data_cache.csv")

# ----------------- Canvas API config -----------------
CANVAS_API_URL = os.getenv("CANVAS_API_URL", "https://canvas.pitt.edu/api/v1")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
headers = {"Authorization": f"Bearer {CANVAS_TOKEN}"}

# ----------------- RMP helper -----------------
def get_professor_info(professor_id: int):
    try:
        prof = RateMyProfessor_Database_APIs.fetch_a_professor(professor_id)

        def safe_float(val):
            try:
                return float(str(val).replace("%", "").strip())
            except Exception:
                return None

        def safe_int(val):
            try:
                return int(val)
            except Exception:
                return None

        return {
            "name": f"{prof.first_name} {prof.last_name}",
            "avg_rating": safe_float(prof.avg_rating),
            "avg_difficulty": safe_float(prof.avg_difficulty),
            "num_ratings": safe_int(prof.num_ratings),
            "would_take_again_percent": safe_float(prof.would_take_again_percent),
        }
    except Exception as e:
        return {"error": str(e)}

# ----------------- Health check -----------------
@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})

# ----------------- Explain prediction -----------------
@api_view(["POST"])
def explain_prediction(request):
    course = request.data.get("course")
    grade = request.data.get("predicted_grade")
    factors = request.data.get("factors", [])
    professor_id = request.data.get("professor_id")

    prompt = f"""
    A student is considering {course}.
    Their predicted grade is {grade}.
    Factors influencing this: {', '.join(factors)}.

    Write a short explanation (2-3 sentences) plus a bulleted list of 3 main reasons.
    """
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    explanation = completion.choices[0].message.content.strip()

    professor_info = get_professor_info(professor_id) if professor_id else None

    return Response({
        "explanation": explanation,
        "professor": professor_info
    })

# ----------------- List courses -----------------
@api_view(["GET"])
def get_canvas_courses(request):
   url = f"{CANVAS_API_URL}/courses"
   response = requests.get(url, headers=headers)
   return Response(response.json())

# ----------------- Get grades by category for a course -----------------
@api_view(["GET"])
def get_canvas_category_grades(request, course_id: int):
   course_url = f"{CANVAS_API_URL}/courses/{course_id}"
   course_info = requests.get(course_url, headers=headers).json()

   url = f"{CANVAS_API_URL}/courses/{course_id}/assignment_groups"
   groups = requests.get(url, headers=headers, params={"include[]": "assignments"}).json()

   sub_url = f"{CANVAS_API_URL}/courses/{course_id}/students/submissions"
   submissions = requests.get(sub_url, headers=headers, params={"student_ids[]": "self"}).json()
   submission_map = {s.get("assignment_id"): s for s in submissions if isinstance(s, dict)}

   results = []
   for g in groups:
       total_points, earned_points = 0, 0
       assignments_list = []

       for a in g.get("assignments", []):
           assignment_id = a["id"]
           points_possible = a.get("points_possible") or 0
           submission = submission_map.get(assignment_id)

           score = submission.get("score") if submission else None
           late = submission.get("late") if submission else None
           excused = submission.get("excused") if submission else None

           if score is not None and points_possible > 0:
               earned_points += score
               total_points += points_possible

           assignments_list.append({
               "id": assignment_id,
               "name": a.get("name"),
               "points_possible": points_possible,
               "score": score,
               "late": late,
               "excused": excused,
               "html_url": a.get("html_url"),
           })

       percent = (earned_points / total_points * 100) if total_points > 0 else None

       results.append({
           "category": g["name"],
           "weight": g.get("group_weight"),
           "earned_points": earned_points,
           "total_points": total_points,
           "percent": percent,
           "assignments": assignments_list
       })

   return Response({
       "course": {
           "id": course_info.get("id"),
           "name": course_info.get("name"),
           "course_code": course_info.get("course_code"),
       },
       "categories": results
   })

# ----------------- Get all Canvas data -----------------
@api_view(["GET"])
def get_canvas_all_data(request):
    courses_url = f"{CANVAS_API_URL}/courses"
    params = {
        "enrollment_state[]": ["active", "completed", "invited_or_pending"],
        "per_page": 100,
        "include[]": ["term"],
    }
    courses = requests.get(courses_url, headers=headers, params=params).json()

    all_data, csv_rows = [], []

    def standardize_category(name: str) -> str:
        n = (name or "").lower()
        if any(k in n for k in ["exam", "midterm", "final", "quiz", "test"]):
            return "exams"
        if any(k in n for k in ["project", "capstone", "lab"]):
            return "projects"
        if any(k in n for k in ["participation", "attendance", "discussion", "poll", "peer"]):
            return "participation"
        return "assignments"

    for course in courses:
        try:
            course_id = course.get("id")
            if not course_id:
                continue

            detail_url = f"{CANVAS_API_URL}/courses/{course_id}"
            course_info = requests.get(detail_url, headers=headers).json()
            term = (course.get("term") or {}).get("name", "")

            # Get official grades
            enrollments_url = f"{CANVAS_API_URL}/courses/{course_id}/enrollments"
            enrollments = requests.get(
                enrollments_url,
                headers=headers,
                params={"user_id": "self", "type[]": "StudentEnrollment"},
            ).json()
            final_grade, final_score = None, None
            if isinstance(enrollments, list) and len(enrollments) > 0:
                grades = enrollments[0].get("grades", {})
                final_grade = grades.get("final_grade") or grades.get("current_grade")
                final_score = grades.get("final_score") or grades.get("current_score")

            # Assignment groups + submissions
            groups_url = f"{CANVAS_API_URL}/courses/{course_id}/assignment_groups"
            groups = requests.get(groups_url, headers=headers,
                                  params={"include[]": "assignments"}).json()
            sub_url = f"{CANVAS_API_URL}/courses/{course_id}/students/submissions"
            submissions = requests.get(sub_url, headers=headers,
                                       params={"student_ids[]": "self"}).json()
            submission_map = {s.get("assignment_id"): s for s in submissions if isinstance(s, dict)}

            categories, cat_percents = [], {"projects": None, "assignments": None, "exams": None, "participation": None}
            for g in groups:
                total_points, earned_points = 0, 0
                for a in g.get("assignments", []):
                    points_possible = a.get("points_possible") or 0
                    submission = submission_map.get(a["id"])
                    score = submission.get("score") if submission else None
                    if score is not None and points_possible > 0:
                        earned_points += score
                        total_points += points_possible
                percent = (earned_points / total_points * 100) if total_points > 0 else None

                std_cat = standardize_category(g["name"])
                if percent is not None:
                    if cat_percents[std_cat] is None:
                        cat_percents[std_cat] = percent
                    else:
                        cat_percents[std_cat] = (cat_percents[std_cat] + percent) / 2

                categories.append({
                    "category": g["name"],
                    "standardized": std_cat,
                    "weight": g.get("group_weight"),
                    "percent": percent,
                })

            course_entry = {
                "id": course_id,
                "name": course_info.get("name"),
                "course_code": course_info.get("course_code"),
                "term": term,
                "final_grade": final_grade,
                "final_score": final_score,
                "categories": categories,
                "standardized_percents": cat_percents,
            }
            all_data.append(course_entry)

            row = {
                "course_id": course_id,
                "name": course_info.get("name"),
                "course_code": course_info.get("course_code"),
                "term": term,
                "final_grade": final_grade,
                "final_score": final_score,
                "projects": cat_percents["projects"],
                "assignments": cat_percents["assignments"],
                "exams": cat_percents["exams"],
                "participation": cat_percents["participation"],
            }
            csv_rows.append(row)

        except Exception as e:
            all_data.append({"course": {"id": course.get("id"), "name": course.get("name")}, "error": str(e)})

    try:
        pd.DataFrame(csv_rows).to_csv(CACHE_PATH, index=False)
    except Exception as e:
        print("Cache write failed:", e)

    return Response(all_data)


# ----------------- Predict grade -----------------
@api_view(["POST"])
def predict_grade(request):
    """
    Returns:
      {
        "category_strengths": {"projects": %, "assignments": %, "exams": %, "participation": %},
        "overall_strength": %,
        "punctual_strength": %,
        "final_score": number,
        "margin_of_error": number,
        "range": [low, high],
        "projects": number,        # syllabus weight %
        "assignments": number,     # syllabus weight %
        "exams": number,           # syllabus weight %
        "participation": number,   # syllabus weight %
        "rmp": {
          "avg_difficulty": number | null,
          "would_take_again_percent": number | null
        }
      }
    """
    professor_id = request.data.get("professor_id")
    syllabus_text = (request.data.get("syllabus_text") or "").strip()

    # -------- Guard: need local Canvas cache ----------
    if not CACHE_PATH.exists():
        return Response(
            {"error": "No Canvas data cache found. Run /api/canvas/all-data first."},
            status=400,
        )

    # -------- Load cache ----------
    try:
        df = pd.read_csv(CACHE_PATH)
    except Exception as e:
        return Response({"error": f"Failed to read cache: {str(e)}"}, status=500)

    # -------- Compute historical strengths from all courses ----------
    category_means = {}
    for cat in ["projects", "assignments", "exams", "participation"]:
        if cat in df.columns:
            valid = df[cat].dropna()
            category_means[cat] = float(valid.mean()) if not valid.empty else None
        else:
            category_means[cat] = None

    # If everything is None, set a sane overall (avoid division by zero)
    non_null_vals = [v for v in category_means.values() if v is not None]
    default_overall = float(sum(non_null_vals) / len(non_null_vals)) if non_null_vals else 85.0

    # -------- Ask AI to finalize strengths JSON (ensures all 4 cats present) ----------
    strengths_prompt = f"""
You are given a student's historical Canvas performance by category (percent 0-100), possibly with nulls:

{json.dumps(category_means, indent=2)}

Return pure JSON with:
- "category_strengths": object with keys "projects","assignments","exams","participation" (0-100 floats).
- "overall_strength": float 0-100 (average of the four categories).
- "punctual_strength": float 0-100 (use 100 because lateness already baked in historically).

Rules:
- If any category is null, replace with this fallback overall: {default_overall:.2f}
- Ensure ALL four categories exist.
- Do NOT include any extra fields or prose. JSON only.
"""
    try:
        stage = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": strengths_prompt},
            ],
            response_format={"type": "json_object"},
        )
        strengths = json.loads(stage.choices[0].message.content)
    except Exception as e:
        # Fallback: construct strengths locally if AI call fails
        cs = {
            k: (category_means[k] if category_means[k] is not None else default_overall)
            for k in ["projects", "assignments", "exams", "participation"]
        }
        strengths = {
            "category_strengths": cs,
            "overall_strength": float(sum(cs.values()) / 4.0),
            "punctual_strength": 100.0,
            "_note": f"AI strengths fallback due to error: {e}",
        }

    # -------- RMP micro-profile (optional) ----------
    rmp = get_professor_info(int(professor_id)) if professor_id else None
    rmp_pack = None
    if isinstance(rmp, dict) and "error" not in rmp:
        rmp_pack = {
            "avg_difficulty": rmp.get("avg_difficulty"),
            "would_take_again_percent": rmp.get("would_take_again_percent"),
        }


    # -------- Ask AI to parse syllabus into weights & produce final score ----------
    # Provide defaults if syllabus unclear.
    prediction_prompt = """
Use the provided data to produce a JSON object with:
- "projects","assignments","exams","participation": syllabus weights as percentages (floats), each 0–100, sum ≈ 100.
- "final_score": number (0–100)
- "margin_of_error": number (e.g., 3,4,6)
- "range": [low, high] (floats, clamped 0–100)

Inputs:
1) strengths: student's category_strengths (0–100), overall_strength, punctual_strength.
2) syllabus: free text that may mention grading breakdowns.
3) rmp: { "avg_difficulty": 0–5 or null, "would_take_again_percent": 0–100 or null }.

Method:
- Parse syllabus text to infer weights. If unclear, use defaults: projects=25, assignments=35, exams=35, participation=5.
- Normalize weights to sum to 100.
- Base score = sum(strength[cat] * weight[cat]/100 for each category).
- Difficulty drag: if rmp.avg_difficulty:
    4.0–5.0  => -3
    3.3–3.99 => -2
    2.7–3.29 => -1
    else     => 0
- Punctual bonus: if punctual_strength > 90 => +2, else +0.
- Extra credit: if syllabus text explicitly mentions "extra credit" or similar => +3.
- Margin of error:
    if rmp.would_take_again_percent is null => 5
    elif <30 => 6
    elif 30–100 => 4
    else => 3
- Clamp final_score to 0–100; range = [final_score - margin, final_score + margin] clamped to 0–100.

Return JSON only with exactly these fields.
"""
    ai_inputs = {
        "strengths": strengths,
        "rmp": rmp_pack,
        "syllabus": syllabus_text,
    }

    try:
        stage2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prediction_prompt},
                {"role": "user", "content": json.dumps(ai_inputs, indent=2)},
            ],
            response_format={"type": "json_object"},
        )
        final = json.loads(stage2.choices[0].message.content)
    except Exception as e:
        # Safe fallback: use defaults and computed strengths
        defaults = {"projects": 25.0, "assignments": 35.0, "exams": 35.0, "participation": 5.0}
        s = strengths.get("category_strengths", {})
        base = sum(float(s.get(k, 85.0)) * (defaults[k] / 100.0) for k in defaults)
        margin = 5.0
        final = {
            **defaults,
            "final_score": float(max(0.0, min(100.0, base))),
            "margin_of_error": margin,
            "range": [float(max(0.0, base - margin)), float(min(100.0, base + margin))],
            "_note": f"AI prediction fallback due to error: {e}",
        }

    # -------- Normalize/validate weights presence ----------
    weights = {}
    for k in ["projects", "assignments", "exams", "participation"]:
        val = final.get(k)
        try:
            weights[k] = float(val) if val is not None else None
        except Exception:
            weights[k] = None

    # If any weight missing, fill with defaults and renormalize
    if any(weights[k] is None for k in weights):
        defaults = {"projects": 25.0, "assignments": 35.0, "exams": 35.0, "participation": 5.0}
        weights = defaults
    # Normalize to sum 100
    total = sum(weights.values())
    if total > 0:
        weights = {k: (v * 100.0 / total) for k, v in weights.items()}

    # -------- Build response ----------
    # inside predict_grade, near the end before resp = { ... }

    course_name = None
    try:
        if "canvas_course_id" in request.data and request.data["canvas_course_id"]:
            cid = int(request.data["canvas_course_id"])
            row = df[df["course_id"] == cid]
            if not row.empty:
                course_name = str(row.iloc[0]["name"])
    except Exception as e:
        course_name = None

    # then in resp dict:
    resp = {
        "course_name": course_name,
        "category_strengths": strengths.get("category_strengths"),
        "overall_strength": strengths.get("overall_strength"),
        "punctual_strength": strengths.get("punctual_strength"),
        "final_score": final.get("final_score"),
        "margin_of_error": final.get("margin_of_error"),
        "range": final.get("range"),
        "projects": round(weights["projects"], 2),
        "assignments": round(weights["assignments"], 2),
        "exams": round(weights["exams"], 2),
        "participation": round(weights["participation"], 2),
        "rmp": rmp_pack,
    }


    return Response(resp)
