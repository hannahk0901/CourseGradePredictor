import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI
import RateMyProfessor_Database_APIs

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})

@api_view(["POST"])
def explain_prediction(request):
    """
    Input: {
      "course": "CS1530",
      "predicted_grade": "B+",
      "factors": [
        "Strong GPA in CS",
        "Heavy exam weighting",
        "Professor tagged as tough grader"
      ],
      "professor_id": 2936635
    }
    """
    course = request.data.get("course")
    grade = request.data.get("predicted_grade")
    factors = request.data.get("factors", [])
    professor_id = request.data.get("professor_id")

    # Build explanation with OpenAI
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

    # Fetch professor info if professor_id is provided
    professor_info = None
    if professor_id:
        professor_info = get_professor_info(professor_id)

    return Response({
        "explanation": explanation,
        "professor": professor_info
    })
