from django.contrib import admin
from django.urls import path
from predictor.views import (
    health_check,
    explain_prediction,
    get_canvas_courses,
    get_canvas_category_grades,
    get_canvas_all_data,   # NEW
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Health + Explain
    path("api/health/", health_check),
    path("api/explain/", explain_prediction),

    # Canvas
    path("api/canvas/courses/", get_canvas_courses),
    path("api/canvas/<int:course_id>/grades/", get_canvas_category_grades),
    path("api/canvas/all-data", get_canvas_all_data),
    path("api/canvas/all-data/", get_canvas_all_data),
]
