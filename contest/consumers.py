from random import randint

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

        self.send(json.dumps({"type": "info",
                              "message": message}))

    def _send_info(self, message):
        async_to_sync(self.channel_layer.group_send)(
            'game_master',
            {
                'type': 'info',
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

        if request_type == 'category':
            category = data.get('category')
            game_id = data.get('game')
            team_name = data.get('team')
            try:
                game = DuelGame.objects.get(id=game_id)
            except DuelGame.DoesNotExist:
                self._send_error('Category selected for wrong game id {}'.format(game_id))
                return
            try:
                team = GameTeam.objects.get(team__name=team_name, game_session=game.session)
            except GameTeam.DoesNotExist:
                self._send_error('Category selected by non existing team')
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
            if ((game.first_player_turn and (team.id != game.first_team.id))
               or (not game.first_player_turn and (team.id != game.second_team_id))):
                self.send(json.dumps({'type': 'error', 'message': 'Wrong team selected category'}))
                self._send_error('Wrong team selected category')
                return

            removed_categories.append(category)
            game.categories_removed = json.dumps(removed_categories)
            game.selected_category = category
            game.state = 2
            game.save()
            async_to_sync(self.channel_layer.group_send)(
                'game_master',
                {
                    'type': 'category.receive',
                    'team': data.get('team'),
                    'category': category,
                    'game': game.id
                }
            )

        elif request_type == 'answer':
            answer_number = data.get('answer')  # is 1,2,3,4 corresponding to a,b,c,d
            question_id = data.get('question')
            game_id = data.get('game')
            team_name = data.get('team')

            try:
                question = Question.objects.get(id=question_id)
                if answer_number:
                    the_answer = Answer.objects.get(number=answer_number, question=question)
                else:
                    the_answer = None
                game = DuelGame.objects.get(id=game_id)
                team = GameTeam.objects.get(team__name=team_name, game_session=game.session)
            except Exception:
                self.send("Error reading answer data from {}".format(data))
                self._send_error("Error reading answer data from {}".format(data))
                return

            # See if the player who guessed is on his turn
            if game.is_final is False:
                if game.first_player_turn:
                    if team.team.name != game.first_team.team.name:
                        self._send_error("Wrong team ({}) answered for game{}".format(team.team.name, str(game_id)))
                        return
                elif team.team.name != game.second_team.team.name:
                    self._send_error("Wrong team ({}) answered for game{}".format(team.team.name, str(game_id)))
                    return

                # See if next question
                removed_categories = json.loads(game.categories_removed)
                # First, update score
                if the_answer.is_correct:
                    if game.first_player_turn:
                        game.first_team_score = game.first_team_score + 1
                    else:
                        game.second_team_score = game.second_team_score + 1
                self._send_info('Team {} answered "{}) {}" and {} correct'.format(
                    team.team.name,
                    answer_number,
                    the_answer.answer_text,
                    "is" if the_answer.is_correct else "isn't"
                ))

                if Question.objects.filter(quiz__gamesession=game.session).exclude(category__in=removed_categories).count() > 0:
                    # We continue the game as categories are available
                    game.state = 1
                    game.first_player_turn = not game.first_player_turn
                    game.save()
                    self._send_info('Game {} continues'.format(game_id))

                else:
                    # Go to next game
                    session = game.session
                    session.games_order = session.games_order + 1
                    session.save()
                    game.save()

                    # Reset device status
                    GameTeam.objects.filter(game_session=session).update(
                        device_registered=False,
                        device_unique_id=None
                    )
                    self._send_info('Game {} finished'.format(game_id))
            else:
                if ((team_name != game.first_team.team.name) and
                   (team_name != game.second_team.team.name) and
                   (team_name != game.third_team.team.name)):
                    self._send_error("Wrong team answered: {}".format(team_name))
                    return

                game.answer_count = game.answer_count + 1

                if the_answer is None:
                    game.round_log = json.loads(game.round_log).append('Team {} ran out of time'.format(team_name))
                elif the_answer.is_correct:
                    if team == game.first_team:
                        game.first_team_score = game.first_team_score + 1
                    elif team == game.second_team:
                        game.second_team_score = game.second_team_score + 1
                    else:
                        game.third_team_score = game.third_team_score + 1

                    # Set the round winner so we can
                    game.round_log = json.loads(game.round_log).append('Team {} answered correctly!'.format(team_name))
                    if not game.round_winner:
                        game.round_winner = team

                if game.answer_count == 3:
                    removed_categories = json.loads(game.categories_removed)
                    # Next round
                    if Question.objects.filter(quiz__gamesession=game.session).exclude(category__in=removed_categories).count() > 0:
                        # We continue the game as categories are available
                        game.state = 1
                        self._send_info("Round won by {}".format(game.round_winner))
                        self._send_info(game.round_log)
                        self._send_info("Starting next round")
                        game.answer_count = 0
                        game.round_winner = None
                        game.round_log = None
                        game.selected_category = None
                        game.save()
                    else:
                        # Game finished announce the winner
                        ranking = [{'team': game.first_team.team.name,
                                    'score': game.first_team_score},
                                   {'team': game.second_team.team.name,
                                    'score': game.second_team_score},
                                   {'team': game.third_team.team.name,
                                    'score': game.third_team_score}]

                        ranking_final = sorted(ranking, key=lambda k: k['score'], reverse=True)
                        self.send(json.dumps(
                            {"type": "game_over",
                             "ranking": ranking_final}
                        ))

                        async_to_sync(self.channel_layer.group_send)(
                            'game_master',
                            {'type': 'game.over',
                             'ranking': ranking_final}
                        )
        elif request_type == 'register':
            name = data.get('team')
            game_id = data.get('game')
            device_id = data.get('device')

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
                if team.device_registered is True:
                    event = {"type": "unregistered",
                             "device_id": team.device_unique_id}
                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'device.unregistered',
                            'message': 'Device {} removed from game {}'.format(team.device_unique_id,
                                                                               game_id)
                        }
                    )
                    async_to_sync(self.channel_layer.group_send)(
                        'players',
                        event
                    )
                team.device_registered = True
                team.device_unique_id = device_id
                team.save()
                game.refresh_from_db()
                self.send(json.dumps({
                    'type': 'device_registered',
                    'team': name,
                    'device': device_id
                }))
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'info',
                        'message': 'Device {} registered for team {}'.format(device_id, name)
                    }
                )
                if game.first_team.device_registered and game.second_team.device_registered:
                    game.state = 1
                    game.save()
                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'info',
                            'message': 'All devices registered, proceed to game start'
                        }
                    )
            else:
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'error',
                        'message': 'Unknown team attemped register'
                    }
                )
        elif request_type == 'connected':
            device_id = data.get('device')

            try:
                gt = GameTeam.objects.filter(device_unique_id=device_id).order_by("id").last()
            except GameTeam.DoesNotExist:
                return  # This means no game is started

            if gt is None:
                return

            # Restore the game state of the device
            try:
                self.send(json.dumps({
                    'type': 'device_reconnect',
                    'device': device_id,
                    'team': gt.team.name,
                    'game': DuelGame.objects.get(session=gt.game_session, game_order=gt.game_session.games_order).id
                }))
            except DuelGame.DoesNotExist:
                return  # Something might've changed

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
            'questionID': event.get('questionID'),
            'answers': event.get('answers'),
            'team': event.get('team')
        }))

    def category_send(self, event):
        self.send(json.dumps(event))

    def unregistered(self, event):
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
                teams = [game.first_team.team.name, game.second_team.team.name]
                async_to_sync(self.channel_layer.group_send)(
                    'players',
                    {
                        'type': 'register.devices',
                        'teams': teams,
                        'game': game.id
                    }
                )
            elif game.state == 1:
                categories_removed = json.loads(game.categories_removed)
                categories = dict()

                if game.is_final is False:
                    for q in game.session.quiz.question_set.all():
                        if q.category not in categories.keys():
                            categories[q.category] = not q.category in categories_removed

                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'send.categories',
                            'categories': categories,
                            'team': game.first_team.team.name if game.first_player_turn else game.second_team.team.name
                        }
                    )
                else:
                    if game.selected_category is None:
                        categories = list({q.category for q in game.session.quiz.question_set.exclude(
                                           category__in=categories_removed)})

                        category_idx = randint(0, len(categories) - 1)
                        game.selected_category = categories[category_idx]
                        game.state = 2
                        game.save()

                    self.send(json.dumps({'type': "category.chosen",
                                          'category': game.selected_category}))

            elif game.state == 2:
                # Must send the question
                # First get the available questions
                questions_removed = json.loads(game.session.questions_removed)
                category = game.selected_category
                q = Question.objects\
                    .exclude(id__in=questions_removed)\
                    .filter(category=category)
                # See how many questions we can use
                count = q.count()
                # Get a random question we can use
                try:
                    random_question_index = randint(0, count-1)
                except ValueError:
                    self.send(json.dumps({'type': 'error',
                                          'message': 'no questions'}))
                    return
                selected_question = q.all()[random_question_index]
                # Send the data
                async_to_sync(self.channel_layer.group_send)(
                    'game_master',
                    {
                        'type': 'send.question',
                        'question_text': selected_question.question_text,
                        'question_id': selected_question.id,
                        'answers': {answer.number: answer.answer_text for answer in Answer.objects.filter(question=selected_question)},
                        'team': game.first_team.team.name if game.first_player_turn else game.second_team.team.name
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

    def send_question(self, event):
        async_to_sync(self.channel_layer.group_send)(
            'players',
            {
                'type': 'question.send',
                'question': event.get('question_text'),
                'questionID': event.get('question_id'),
                'answers': event.get('answers'),
                'team': event.get('team')
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

    def device_unregistered(self, event):
        self.send(json.dumps(event))

    def error(self, event):
        self.send(json.dumps({
            'error': event.get('message')
        }))

    def info(self, event):
        self.send(json.dumps({
            'info': event.get('message')
        }))
