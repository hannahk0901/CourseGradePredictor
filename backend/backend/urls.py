from django.contrib import admin
from django.urls import path
from predictor.views import health_check, explain_prediction

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check),
    path("api/explain/", explain_prediction),

]
