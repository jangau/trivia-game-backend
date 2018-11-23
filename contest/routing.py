from django.conf.urls import url

from . import consumers


websocket_urlpatterns = [
    url(r'^ws/game/$', consumers.QuizConsumer),
    url(r'^ws/gamemaster/$', consumers.GameMasterConsumer),
]

