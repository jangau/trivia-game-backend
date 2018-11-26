from django.contrib import admin

# Register your models here.
from contest.models import Question, Answer, Quiz, Game, GameSession

admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Quiz)
admin.site.register(Game)
admin.site.register(GameSession)
