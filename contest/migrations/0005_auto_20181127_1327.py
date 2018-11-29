# Generated by Django 2.1.3 on 2018-11-27 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contest', '0004_gameteam_device_registered'),
    ]

    operations = [
        migrations.AddField(
            model_name='duelgame',
            name='categories_removed',
            field=models.CharField(default='[]', max_length=1000),
        ),
        migrations.AddField(
            model_name='duelgame',
            name='first_player_turn',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterUniqueTogether(
            name='gameteam',
            unique_together={('team', 'game_session')},
        ),
    ]