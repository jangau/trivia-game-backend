from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from contest import api_views

urlpatterns = [
    path('quizzes/', api_views.QuizzesList.as_view()),
    path('quizzes/<int:pk>/', api_views.QuizDetail.as_view(), name='quiz-detail'),
    path('questions/', api_views.QuestionsList.as_view()),
    path('questions/<int:pk>/', api_views.QuestionDetail.as_view(), name='question-detail'),
    path('answers/', api_views.AnswersList.as_view()),
    path('answers/<int:pk>/', api_views.AnswerDetail.as_view(), name='answer-detail'),
    path('start-game/', api_views.start_quiz, name='start-game')
]

urlpatterns = format_suffix_patterns(urlpatterns)
