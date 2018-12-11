from django.conf.urls import url

from contest import views

urlpatterns = [
    url('game/', views.game_view),
]
