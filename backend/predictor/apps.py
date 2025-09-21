import requests
from django.apps import AppConfig
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI
import RateMyProfessor_Database_APIs


class PredictorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'predictor'
