# Generated by Django 2.1.3 on 2018-11-22 14:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Answer',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('letter', models.IntegerField(choices=[(1, 'a'), (2, 'b'), (3, 'c'), (4, 'd')])),
                ('answer_text', models.CharField(max_length=150)),
                ('is_correct', models.NullBooleanField(default=None)),
            ],
        ),
        migrations.CreateModel(
            name='AnswerReceived',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('answer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Answer')),
            ],
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('question_text', models.TextField()),
                ('order', models.IntegerField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('type', models.IntegerField(choices=[(1, 'Normal/sequential'), (2, 'Timed')])),
                ('team_order', models.IntegerField(default=0)),
                ('question_order', models.IntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('device', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='question',
            name='quiz',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Quiz'),
        ),
        migrations.AddField(
            model_name='answerreceived',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Question'),
        ),
        migrations.AddField(
            model_name='answerreceived',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Team'),
        ),
        migrations.AddField(
            model_name='answer',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contest.Question'),
        ),
        migrations.AlterUniqueTogether(
            name='answer',
            unique_together={('question', 'is_correct'), ('letter', 'question')},
        ),
    ]