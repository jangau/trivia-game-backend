from django.db import models


ANSWER_LABELS = [
    (1, 'a'),
    (2, 'b'),
    (3, 'c'),
    (4, 'd')
]

QUIZ_TYPES = [
    (1, 'Normal/sequential'),
    (2, 'Timed')
]


class Quiz(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    type = models.IntegerField(choices=QUIZ_TYPES)
    team_order = models.IntegerField(default=0)
    question_order = models.IntegerField(default=0)


class Question(models.Model):
    id = models.AutoField(primary_key=True)
    question_text = models.TextField()
    order = models.IntegerField(null=True)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)


class Answer(models.Model):
    id = models.AutoField(primary_key=True)
    number = models.IntegerField(choices=ANSWER_LABELS)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.CharField(max_length=150)
    is_correct = models.NullBooleanField(default=None)

    class Meta:
        unique_together = (('number', 'question'),
                           ('question', 'is_correct'))


class Team(models.Model):
    id = models.AutoField(primary_key=True)
    device = models.CharField(unique=True, max_length=50)
    name = models.CharField(unique=True, max_length=50)


class AnswerReceived(models.Model):
    id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE)


