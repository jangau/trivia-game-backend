import json

from django.db import models


ANSWER_LABELS = [
    (1, 'a'),
    (2, 'b'),
    (3, 'c'),
    (4, 'd')
]


DUEL_GAME_STATES = [
    (0, 'Not started'),
    (1, 'Category'),
    (2, 'Question'),
    (5, 'Finished')
]


class Quiz(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)


class Question(models.Model):
    id = models.AutoField(primary_key=True)
    question_text = models.TextField()
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    category = models.CharField(max_length=100)

    def __str__(self):
        return "{}: {}".format(self.category, self.question_text[:200])


class Answer(models.Model):
    id = models.AutoField(primary_key=True)
    number = models.IntegerField(choices=ANSWER_LABELS)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.CharField(max_length=150)
    is_correct = models.NullBooleanField(default=None)

    class Meta:
        unique_together = (('number', 'question'),
                           ('question', 'is_correct'))

    def __str__(self):
        return "Q{}/{}: {}".format(self.question_id,
                                   self.get_number_display(), self.answer_text[:50])


class Team(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=50)

    def __str__(self):
        return self.name


class AnswerReceived(models.Model):
    id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE)


class GameSession(models.Model):
    id = models.AutoField(primary_key=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    winner = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True)
    questions_removed = models.CharField(max_length=300)
    games_order = models.IntegerField(default=1)


class GameTeam(models.Model):
    id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    game_session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    device_registered = models.BooleanField(default=False)

    class Meta:
        unique_together = (('team', 'game_session'),)


class DuelGame(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(GameSession, on_delete=models.CASCADE)
    step = models.IntegerField(default=1)
    categories_removed = models.CharField(max_length=1000, default='[]')
    first_team = models.ForeignKey(GameTeam, on_delete=models.CASCADE,
                                   related_name='first_team')
    first_team_score = models.IntegerField(default=0)
    second_team = models.ForeignKey(GameTeam, on_delete=models.CASCADE,
                                    related_name='second_team')
    second_team_score = models.IntegerField(default=0)
    first_player_turn = models.BooleanField(default=True)
    state = models.IntegerField(default=0, choices=DUEL_GAME_STATES)

    def get_all_categories_count(self):
        return len({q.category for q in self.session.quiz.question_set})

    def get_removed_categories_count(self):
        return len(json.loads(self.categories_removed))
