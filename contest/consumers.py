from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
import json

from contest.models import GameTeam, DuelGame, Question, Answer


class QuizConsumer(WebsocketConsumer):

    def _send_error(self, message):
        async_to_sync(self.channel_layer.group_send)(
            'game_master',
            {
                'type': 'error',
                'message': message
            }
        )

    def connect(self):
        self.accept()
        async_to_sync(self.channel_layer.group_add)("players", self.channel_name)

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("players", self.channel_name)

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception as exc:
            self.send("message received: \"{}\" is not valid json".format(text_data))
            self._send_error('Invalid request {}'.format(exc))
            return

        request_type = data.get('type')

        if request_type == 'answer':
            answer = data.get('answer')
            async_to_sync(self.channel_layer.group_send)(
                'game_master',
                {
                    'type': 'answer.receive',
                    'team': data.get('name'),
                    'answer': answer
                }
            )
        elif request_type == 'category':
            category = data.get('category')
            game_id = data.get('game')
            try:
                game = DuelGame.objects.get(id=game_id)
            except DuelGame.DoesNotExist:
                self._send_error('Category selected for wrong game id {}'.format(game_id))
                return
            removed_categories = json.loads(game.categories_removed)
            if category in removed_categories:
                self.send(json.dumps({'type': 'error', 'message': 'category not available'}))
                self._send_error('Category no longer available for this game {}'.format(category))
                return
            category_exists = game.session.quiz.question_set.filter(category=category).count() > 0
            if category_exists < 1:
                self.send(json.dumps({'type': 'error', 'message': 'category not available'}))
                self._send_error('Category not found: {}'.format(category))
                return
            removed_categories.append(category)
            game.categories_removed = json.dumps(removed_categories)
            game.state = 2
            game.save()
            async_to_sync(self.channel_layer.group_send)(
                'game_master',
                {
                    'type': 'category.receive',
                    'team': data.get('name'),
                    'category': category,
                    'game': game.id
                }
            )
        elif request_type == 'answer':
            answer = data.get('answer')  # is 1,2,3,4 corresponding to a,b,c,d
            question = data.get('question')
            game_id = data.get('game')
            try:
                game = DuelGame.objectsget(id=game_id)
            except DuelGame.DoesNotExist:
                self._send_error('Answer received for wrong game id {}'.format(game_id))

            correct = False
            answer_correct = Answer.objects.get(question__id=question, is_correct=True)
            if answer_correct.number == answer:
                if game.first_player_turn == True:
                    game.first_team_score += 1
                else:
                    game.second_team_score += 1

            # Check if game finished
            if game.get_all_categories_count() == game.get_removed_categories_count():
                game.state = 5  # Coresponding to finished state

            game.first_player_turn = not game.first_player_turn

            if game.first_player_turn is True:
                pass

        elif request_type == 'register':
            name = data.get('team')
            game_id = data.get('game')

            try:
                game = DuelGame.objects.get(id=game_id)
                team = GameTeam.objects.get(team__name=name, game_session=game.session)
            except Exception as exc:
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'error',
                        'message': 'Team or game not found {}'.format(exc)
                    }
                )
                self.send('Team or game not found')
                return

            if team == game.first_team or team == game.second_team:
                team.device_registered = True
                team.save()
                self.send(json.dumps({
                    'type': 'device_registered',
                    'team': name
                }))
            else:
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'error',
                        'message': 'Unknown team attemped register'
                    }
                )

    def register_devices(self, event):
        self.send(json.dumps({
            'type': 'register_device',
            'teams': event.get('teams'),
            'game': event.get('game')
        }))

    def question_send(self, event):
        self.send(json.dumps({
            'type': 'question_send',
            'question': event.get('question'),
            'anwers': event.get('answers')
        }))

    def category_send(self, event):
        self.send(json.dumps(event))


class GameMasterConsumer(WebsocketConsumer):

    def connect(self):
        async_to_sync(self.channel_layer.group_add)("game_master", self.channel_name)
        self.accept()

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("game_master", self.channel_name)

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception as exc:
            self.send("message received: \"{}\" is not valid json. Error: {}".format(
                text_data, exc))
            return

        action_type = data.get('type')

        if action_type == 'duel_game_continue':
            game_id = data.get('game')
            try:
                game = DuelGame.objects.get(id=game_id)

            except DuelGame.DoesNotExist:
                self.send(json.dumps({
                    'error': 'Game with id {} does not exist'.format(game_id)
                }))
                return

            # See the state of the game
            game_state = game.state
            if game_state == 0:
                game.state = 1
                game.save()

            if game.state == 1:
                categories_removed = json.loads(game.categories_removed)
                categories = {q.category for q in game.session.quiz.question_set.exclude(
                    category__in=categories_removed
                )}
                game.save()
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'send.categories',
                        'categories': list(categories),
                        'team': game.first_team.team.name
                    }
                )

    def answer_receive(self, event):
        self.send(json.dumps({
            'team': event.get('team'),
            'answer': event.get('answer')
        }))

    def category_receive(self, event):
        self.send(json.dumps(event))

    def register_devices(self, event):
        self.send(
            json.dumps(
                {'type': 'info',
                 'message': "Must register {} to {}".format(event.get('teams'),
                                                            event.get('game'))}
                ))
        async_to_sync(self.channel_layer.group_send)(
            'players',
            {
                'type': 'register.devices',
                'teams': event.get('teams'),
                'game': event.get('game')
            }
        )

    def send_question(self, event):
        async_to_sync(self.channel_layer.group_send)(
            'players',
            {
                'type': 'question.send',
                'question': event.get('question_text'),
                'answers': event.get('answers'),
                'to': event.get('teams')
            }
        )

    def send_categories(self, event):
        self.send(json.dumps(event))
        async_to_sync(self.channel_layer.group_send)(
            'players',
            {
                'type': 'category.send',
                'categories': event.get('categories'),
                'to': event.get('team')
            }
        )

    def error(self, event):
        self.send(json.dumps({
            'error': event.get('message')
        }))
