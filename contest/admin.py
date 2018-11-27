from django.contrib import admin

# Register your models here.
from contest.models import Question, Answer, Quiz, GameSession, Team

admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(Quiz)
admin.site.register(GameSession)
admin.site.register(Team)
