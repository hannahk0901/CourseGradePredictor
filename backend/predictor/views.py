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
        return {
            "name": f"{prof.first_name} {prof.last_name}",
            "avg_rating": float(prof.avg_rating) if prof.avg_rating else None,
            "avg_difficulty": float(prof.avg_difficulty) if prof.avg_difficulty else None,
            "num_ratings": int(prof.num_ratings) if prof.num_ratings else None,
            "would_take_again_percent": float(prof.would_take_again_percent)
                if prof.would_take_again_percent else None,
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



# ----------------- Get all Canvas data (course-level summary, standardized categories) -----------------
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
        """Map Canvas category names into one of the 4 standardized groups."""
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
                        # average multiple Canvas groups mapping to same category
                        cat_percents[std_cat] = (cat_percents[std_cat] + percent) / 2

                categories.append({
                    "category": g["name"],
                    "standardized": std_cat,
                    "weight": g.get("group_weight"),
                    "percent": percent,
                })

            # Save JSON for API response
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

            # Save CSV row with fixed category columns
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

    # Save CSV
    try:
        pd.DataFrame(csv_rows).to_csv(CACHE_PATH, index=False)
    except Exception as e:
        print("Cache write failed:", e)

    return Response(all_data)

# ----------------- Predict grade -----------------
# ----------------- Predict grade -----------------
@api_view(["POST"])
def predict_grade(request):
    professor_id = request.data.get("professor_id")
    syllabus_text = request.data.get("syllabus_text", "")

    if not CACHE_PATH.exists():
        return Response(
            {"error": "No Canvas data cache found. Run /api/canvas/all-data first."},
            status=400,
        )

    try:
        df = pd.read_csv(CACHE_PATH)
    except Exception as e:
        return Response({"error": f"Failed to read cache: {str(e)}"}, status=500)

    # ---- Compute averages across ALL courses ----
    category_means = {}
    for cat in ["projects", "assignments", "exams", "participation"]:
        if cat in df.columns:
            valid = df[cat].dropna()
            category_means[cat] = valid.mean() if not valid.empty else None
        else:
            category_means[cat] = None

    # Default fallback if everything is empty
    overall_strength = (
        sum(v for v in category_means.values() if v is not None)
        / max(1, sum(v is not None for v in category_means.values()))
    )

    # Build strengths JSON for AI
    strengths_prompt = """
    You are given Canvas category averages:
    projects, assignments, exams, participation.
    Return JSON with category_strengths, overall_strength, and punctual_strength.
    Rules:
    - Always include all four categories.
    - If a category is None, set it equal to overall_strength.
    - overall_strength = average of the four categories.
    - punctual_strength = 100 (lateness already factored in).
    """
    stage = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": strengths_prompt},
            {"role": "user", "content": json.dumps(category_means, indent=2)},
        ],
        response_format={"type": "json_object"},
    )
    strengths = json.loads(stage.choices[0].message.content)

    # --- Prediction step ---
    rmp = get_professor_info(int(professor_id)) if professor_id else None
    prediction_prompt = """
    Using strengths, syllabus, and RMP:
    - Normalize syllabus grading into projects, assignments, exams, participation (sum=100).
    - Final score = weighted blend of strengths × syllabus weights.
    - Adjustments: difficulty drag (–3 max), punctual bonus (+2 if punctual>90), extra credit (+3 if syllabus mentions).
    - Margin of error: RMP <30 = ±6, 30–100 = ±4, >100 = ±3.
    - Range = [final – margin, final + margin], clamp 0–100.
    Return JSON { "final_score": number, "margin_of_error": number, "range": [low, high] }
    """
    stage2 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prediction_prompt},
            {"role": "user", "content": json.dumps(
                {"strengths": strengths, "rmp": rmp, "syllabus": syllabus_text},
                indent=2,
            )},
        ],
        response_format={"type": "json_object"},
    )
    final = json.loads(stage2.choices[0].message.content)

    return Response({
        **strengths,
        "final_score": final.get("final_score"),
        "margin_of_error": final.get("margin_of_error"),
        "range": final.get("range"),
    })
