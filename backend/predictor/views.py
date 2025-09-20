import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})

@api_view(["POST"])
def explain_prediction(request):
    """
    Input: {
      "course": "CS447",
      "predicted_grade": "B+",
      "factors": [
        "Strong GPA in CS",
        "Heavy exam weighting",
        "Professor tagged as tough grader"
      ]
    }
    """
    course = request.data.get("course")
    grade = request.data.get("predicted_grade")
    factors = request.data.get("factors", [])

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

    return Response({"explanation": explanation})
