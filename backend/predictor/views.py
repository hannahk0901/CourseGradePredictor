import os
import json
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI
import RateMyProfessor_Database_APIs
import traceback

# ----------------- OpenAI client -----------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------- RMP helper -----------------
def get_professor_info(professor_id: int):
    try:
        prof = RateMyProfessor_Database_APIs.fetch_a_professor(professor_id)
        return {
            "name": f"{prof.first_name} {prof.last_name}",
            "avg_rating": float(prof.avg_rating) if prof.avg_rating is not None else None,
            "avg_difficulty": float(prof.avg_difficulty) if prof.avg_difficulty is not None else None,
            "num_ratings": int(prof.num_ratings) if prof.num_ratings is not None else None,
            "would_take_again_percent": float(prof.would_take_again_percent)
                if prof.would_take_again_percent is not None else None,
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

# ----------------- Canvas API -----------------
CANVAS_API_URL = os.getenv("CANVAS_API_URL", "https://canvas.pitt.edu/api/v1")
CANVAS_TOKEN = os.getenv("CANVAS_TOKEN")
headers = {"Authorization": f"Bearer {CANVAS_TOKEN}"}

# List courses
@api_view(["GET"])
def get_canvas_courses(request):
    url = f"{CANVAS_API_URL}/courses"
    response = requests.get(url, headers=headers)
    return Response(response.json())

# Get grades by category for a course (by course ID)
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

    all_data = []
    for course in courses:
        try:
            course_id = course.get("id")
            if not course_id:
                continue

            term = (course.get("term") or {}).get("name", "")
            detail_url = f"{CANVAS_API_URL}/courses/{course_id}"
            course_info = requests.get(detail_url, headers=headers).json()

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

            groups_url = f"{CANVAS_API_URL}/courses/{course_id}/assignment_groups"
            groups = requests.get(
                groups_url, headers=headers, params={"include[]": "assignments"}
            ).json()

            sub_url = f"{CANVAS_API_URL}/courses/{course_id}/students/submissions"
            submissions = requests.get(
                sub_url, headers=headers, params={"student_ids[]": "self"}
            ).json()
            submission_map = {s.get("assignment_id"): s for s in submissions if isinstance(s, dict)}

            categories = []
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

                categories.append({
                    "category": g["name"],
                    "weight": g.get("group_weight"),
                    "earned_points": earned_points,
                    "total_points": total_points,
                    "percent": percent,
                    "assignments": assignments_list
                })

            all_data.append({
                "course": {
                    "id": course_id,
                    "name": course_info.get("name"),
                    "course_code": course_info.get("course_code"),
                    "term": term or course_info.get("term", {}).get("name", "Unknown"),
                    "final_grade": final_grade,
                    "final_score": final_score,
                },
                "categories": categories
            })

        except Exception as e:
            all_data.append({
                "course": {
                    "id": course.get("id"),
                    "name": course.get("name") or "Unknown Course",
                },
                "error": str(e)
            })

    return Response(all_data)

# ----------------- Predict grade -----------------
@api_view(["POST"])
def predict_grade(request):
    canvas_course_id = request.data.get("canvas_course_id")
    professor_id = request.data.get("professor_id")
    student_factors = request.data.get("student_factors", [])
    syllabus_text = request.data.get("syllabus_text", "")

    if not canvas_course_id:
        return Response({"error": "canvas_course_id is required"}, status=400)

    try:
        # --- Fetch Canvas data ---
        groups_url = f"{CANVAS_API_URL}/courses/{canvas_course_id}/assignment_groups"
        groups = requests.get(
            groups_url, headers=headers, params={"include[]": "assignments"}
        ).json()

        subs_url = f"{CANVAS_API_URL}/courses/{canvas_course_id}/students/submissions"
        subs = requests.get(
            subs_url, headers=headers, params={"student_ids[]": "self"}
        ).json()

        if not isinstance(groups, list) or not isinstance(subs, list):
            return Response(
                {"error": "Unexpected response from Canvas", "details": {"groups": groups, "subs": subs}},
                status=500,
            )

        submission_by_aid = {s.get("assignment_id"): s for s in subs if isinstance(s, dict)}

        # --- Per-assignment classification ---
        buckets = {"projects": [], "assignments": [], "exams": [], "participation": []}
        late_count, total_count = 0, 0

        def classify_assignment(name: str, group: str):
            name_l = (name or "").lower()
            group_l = (group or "").lower()
            if "exam" in name_l or "midterm" in name_l or "final" in name_l or "test" in name_l:
                return "exams"
            if "quiz" in name_l:
                return "exams"
            if "project" in name_l or "capstone" in name_l:
                return "projects"
            if "lab" in name_l:
                return "assignments" if "small" in name_l or "recitation" in group_l else "projects"
            if "participation" in name_l or "attendance" in name_l or "discussion" in name_l:
                return "participation"
            if "exam" in group_l or "quiz" in group_l or "test" in group_l:
                return "exams"
            if "project" in group_l:
                return "projects"
            if "participation" in group_l or "attendance" in group_l:
                return "participation"
            return "assignments"

        for g in groups:
            if not isinstance(g, dict):
                continue
            assignments = g.get("assignments", []) or []
            for a in assignments:
                if not isinstance(a, dict):
                    continue
                aid = a.get("id")
                pts = float(a.get("points_possible") or 0)
                sub = submission_by_aid.get(aid) or {}
                score = sub.get("score")
                is_late = sub.get("late") or False
                is_excused = sub.get("excused") or False

                if not pts or score is None or is_excused:
                    continue

                total_count += 1
                if is_late:
                    late_count += 1

                cat = classify_assignment(a.get("name"), g.get("name"))
                pct = (float(score) / pts) * 100.0

                name_l = (a.get("name") or "").lower()
                if "quiz" in name_l:
                    if "daily" in name_l or "tophat" in name_l:
                        pct *= 0.10
                    else:
                        pct *= 0.25

                buckets[cat].append(pct)

        raw_categories = []
        for cat, scores in buckets.items():
            if scores:
                avg = sum(scores) / len(scores)
            else:
                avg = 70.0
            raw_categories.append({"name": cat, "percent": avg})

        late_stats = {"late_assignments": late_count, "total_assignments": total_count}

    except Exception as e:
        traceback.print_exc()
        return Response({"error": f"Failed to fetch Canvas data: {str(e)}"}, status=500)

    rmp = get_professor_info(int(professor_id)) if professor_id else None
    syllabus_summary = syllabus_text

    instruction = """
    You are an analytics model. You must ONLY return valid JSON following this schema:
    {
      "category_strengths": {
        "projects": number,
        "assignments": number,
        "exams": number,
        "participation": number
      },
      "overall_strength": number,
      "punctual_strength": number,
      "target_course": {
        "projects_weight": number,
        "assignments_weight": number,
        "exams_weight": number,
        "participation_weight": number,
        "difficulty_rating": number
      },
      "prediction": {
        "final_score": number,
        "margin_of_error": number,
        "range": [number, number]
      }
    }
    User Metrics Rules:
1. Generalize Canvas categories into exactly four:
   - Projects = programming projects, capstones, major labs.
   - Assignments = homework, small labs, written responses, problem sets.
   - Exams = for now assume this category is all 100% regardless of actual scores.
   - Participation = attendance, recitation, peer review, polls, discussions.
   - If professor provides extra credit, give each category a +5 boost (cap at 100).
   - Never return <40 if graded work exists.

2. Category Strengths:
   - Compute strength as average % score in each category.
   - Weight courses with prerequisites 3× more.
   - Cap so no single course contributes >25% of category score.

3. Overall Strength:
   - Average category strengths with weighting rules.
   - Apply 3× weight for prerequisites/higher-level courses.
   - Cap dominance of one course.

4. Punctual Strength:
   - LateRate = late_assignments ÷ total_assignments.
   - Syllabus strictness scale (1–10):
       * No late work = 10
       * 10% per day with cutoff = 9
       * Flexible extensions = 5
   - PunctualStrength = 100 – (LateRate × Strictness × 50).
   - Clamp 0–100.

🎯 Target Course:
5. Weights: Normalize syllabus grading into Projects, Assignments, Exams, Participation (total = 100).
6. DifficultyRating = (0.5 × Difficulty) + (0.25 × (100 – Rating)) + (0.25 × (100 – WouldTakeAgain)).
   - Range 0–100.
   - Apply up to –3 drag to predicted grade.

🏆 Final Prediction:
7. Final Score = weighted blend of user strengths × syllabus weights.
   Adjustments:
   - Difficulty drag: –0 to –3 points.
   - Punctual bonus: +1–2 if punctual >90 and syllabus strict.
   - Trend bonus: +1–2 if CS strength > overall.
   - Extra credit/curve bonus: +0–2 if syllabus mentions it.

8. Margin of Error:
   - RMP ratings <30 → ±7 points
   - RMP 30–100 → ±5 points
   - RMP >100 → ±3 points
   - Canvas data >20% N/A → add ±2–3 points
   - Flexible grading/EC → add ±1–2 points
   - Clamp final range to 0–100.
    """

    model_inputs = {
        "canvas_categories": raw_categories,
        "lateness": late_stats,
        "rmp": rmp,
        "student_factors": student_factors,
        "syllabus_summary": syllabus_summary,
    }

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise analytics model. Return only valid JSON."},
                {"role": "user", "content": instruction},
                {"role": "user", "content": json.dumps(model_inputs, indent=2)},
            ],
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        raw = completion.choices[0].message.content.strip()
        data = json.loads(raw)

        return Response({
            "inputs_used": model_inputs,
            "category_strengths": data.get("category_strengths"),
            "overall_strength": data.get("overall_strength"),
            "punctual_strength": data.get("punctual_strength"),
            "target_course": data.get("target_course"),
            "final_score": data["prediction"].get("final_score"),
            "margin_of_error": data["prediction"].get("margin_of_error"),
            "range": data["prediction"].get("range"),
        })

    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)
