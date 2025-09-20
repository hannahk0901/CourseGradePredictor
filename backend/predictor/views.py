import os
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI
import RateMyProfessor_Database_APIs

# ----------------- OpenAI client -----------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------- RMP helper -----------------
def get_professor_info(professor_id: int):
    try:
        prof = RateMyProfessor_Database_APIs.fetch_a_professor(professor_id)
        return {
            "name": f"{prof.first_name} {prof.last_name}",
            "avg_rating": prof.avg_rating,
            "avg_difficulty": prof.avg_difficulty,
            "num_ratings": prof.num_ratings,
            "would_take_again_percent": prof.would_take_again_percent,
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
    """
    Input: {
      "course": "CS1530",
      "predicted_grade": "B+",
      "factors": ["Strong GPA", "Heavy exam weighting"],
      "professor_id": 2936635
    }
    """
    course = request.data.get("course")
    grade = request.data.get("predicted_grade")
    factors = request.data.get("factors", [])
    professor_id = request.data.get("professor_id")

    # OpenAI explanation
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

    professor_info = None
    if professor_id:
        professor_info = get_professor_info(professor_id)

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
    # 0. Get course info
    course_url = f"{CANVAS_API_URL}/courses/{course_id}"
    course_info = requests.get(course_url, headers=headers).json()

    # 1. Get assignment groups
    url = f"{CANVAS_API_URL}/courses/{course_id}/assignment_groups"
    groups = requests.get(url, headers=headers, params={"include[]": "assignments"}).json()

    # 2. Get submissions for current student
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

# ----------------- NEW: All data for all courses -----------------
# ----------------- NEW: All data for all courses -----------------
# ----------------- NEW: All data for all courses -----------------
@api_view(["GET"])
def get_canvas_all_data(request):
    """
    Fetch all courses except Fall 2025, and include final grade info.
    """
    courses_url = f"{CANVAS_API_URL}/courses"
    params = {
        "enrollment_state[]": ["active", "completed", "invited_or_pending"],  # include current + past
        "per_page": 100,
        "include[]": ["term"],  # explicitly request term info
    }
    courses = requests.get(courses_url, headers=headers, params=params).json()

    all_data = []
    for course in courses:
        try:
            course_id = course.get("id")
            if not course_id:
                continue

            # 🔴 Skip Fall 2025 courses
            term = (course.get("term") or {}).get("name", "")
            if "fall 2025" in term.lower():
                continue

            # Always fetch detail for reliability
            detail_url = f"{CANVAS_API_URL}/courses/{course_id}"
            course_info = requests.get(detail_url, headers=headers).json()

            # 🔑 Fetch enrollment info to get grades
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

            # Assignment groups
            groups_url = f"{CANVAS_API_URL}/courses/{course_id}/assignment_groups"
            groups = requests.get(
                groups_url, headers=headers, params={"include[]": "assignments"}
            ).json()

            # Submissions
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
