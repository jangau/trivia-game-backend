import time
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
            if game.state == 5:
                # If the game is finished, answers will not work
                self._send_error("Game finished, cannot get any more answers")
                return
            if game.is_final is False:
                if game.first_player_turn and (game.state != 3):
                    if team.team.name != game.first_team.team.name:
                        self._send_error("Wrong team ({}) answered for game{}".format(team.team.name, str(game_id)))
                        return
                elif team.team.name != game.second_team.team.name and (game.state != 3):
                    self._send_error("Wrong team ({}) answered for game{}".format(team.team.name, str(game_id)))
                    return

                # See if next question
                removed_categories = json.loads(game.categories_removed)

                async_to_sync(self.channel_layer.group_send)(
                    "game_master",
                    {
                        "type": "answer.receive",
                        "team": team_name,
                        "answer": answer_number
                    }
                )

                # First, update score
                if the_answer is None:
                    pass
                elif the_answer.is_correct:
                    if game.first_player_turn:
                        game.first_team_score = game.first_team_score + 1
                    else:
                        game.second_team_score = game.second_team_score + 1
                else:
                    if game.state == 3:
                        # Someone rushed and answered incorrectly
                        # He will lose
                        if team_name == game.first_team.team.name:
                            game.second_team_score += 1
                        else:
                            game.first_team_score += 1

                if the_answer is None:
                    self._send_info('Answer was null')
                else:
                    self._send_info('Team {} answered "{}. {}" and {} correct'.format(
                        team.team.name,
                        answer_number,
                        the_answer.answer_text if the_answer else "did not answer",
                        "is" if the_answer.is_correct else "isn't"
                    ))
                game.correct_answer = Answer.objects.get(question=question, is_correct=True).number
                categories_left_count = len({q.category for q in Question.objects.filter(
                    quiz__gamesession=game.session
                ).exclude(
                    category__in=removed_categories
                )})
                if categories_left_count > 1:
                    # We continue the game as categories are available
                    game.state = 1
                    game.first_player_turn = not game.first_player_turn
                    game.save()
                    self._send_info('Game {} continues'.format(game_id))

                else:
                    # See if we have a tie
                    if game.first_team_score == game.second_team_score:
                        # We have a tie, we need to send another question
                        game.state = 3
                        game.save()
                        self._send_info('Game {} is a tie, sending last question'.format(game_id))
                        return

                    winner = game.first_team if game.first_team_score > game.second_team_score else game.second_team
                    game.winner = winner
                    game.state = 5
                    # Go to next game
                    session = game.session
                    session.games_order = session.games_order + 1
                    session.save()
                    game.save()

                    event = {"type": "unregistered",
                             "device_id": "all"}

                    async_to_sync(self.channel_layer.group_send)('players', event)

                    # Reset device status
                    GameTeam.objects.filter(game_session=session).update(
                        device_registered=False,
                        device_unique_id=None
                    )

                    # See if we are starting the final, to select the players
                    if DuelGame.objects.get(session=session, game_order=session.games_order).is_final:
                        # We have a final, let's find the winners of the previous rounds
                        # First let's get the games
                        normal_games = DuelGame.objects.filter(session=session, is_final=False)
                        winners = [game.winner for game in normal_games]
                        print(winners)
                        if len(winners) != 3:
                            self._send_error("Winners are not 3! (It's {})".format(len(winners)))
                            return
                        final = DuelGame.objects.get(session=session, is_final=True)
                        final.first_team = winners[0]
                        final.second_team = winners[1]
                        final.third_team = winners[2]
                        final.save()

                    self._send_info('Game {} finished, winner is {}'.format(game_id, winner.team.name))

            else:
                if ((team_name != game.first_team.team.name) and
                   (team_name != game.second_team.team.name) and
                   (team_name != game.third_team.team.name)):
                    self._send_error("Wrong team answered: {}".format(team_name))
                    return

                async_to_sync(self.channel_layer.group_send)(
                    "game_master",
                    {
                        "type": "answer.receive",
                        "team": team_name,
                        "answer": answer_number
                    }
                )

                game.answer_count = game.answer_count + 1

                if the_answer is None:
                    game.round_log = json.dumps(
                        json.loads(game.round_log).append('Team {} ran out of time'.format(team_name)))
                elif the_answer.is_correct:
                    if team == game.first_team:
                        game.first_team_score = game.first_team_score + 1
                    elif team == game.second_team:
                        game.second_team_score = game.second_team_score + 1
                    else:
                        game.third_team_score = game.third_team_score + 1

                    # Set the round winner so we can
                    game.round_log = json.dumps(
                        json.loads(game.round_log).append('Team {} answered correctly!'.format(team_name)))
                    game.correct_answer = the_answer.number
                    if not game.round_winner:
                        game.round_winner = team.team.name
                game.save()
                print("Number of answers: {}".format(game.answer_count))
                if game.answer_count >= 3:
                    removed_categories = json.loads(game.categories_removed)
                    game.correct_answer = Answer.objects.get(question=question, is_correct=True).number
                    # Next round
                    if Question.objects.filter(quiz__gamesession=game.session).exclude(category__in=removed_categories).count() > 0:
                        # We continue the game as categories are available
                        game.state = 1
                        self._send_info("Round won by {}".format(game.round_winner))
                        self._send_info(game.round_log)
                        self._send_info("Starting next round")
                        game.answer_count = 0
                        game.round_winner = None
                        game.round_log = json.dumps([])
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
                        game.save()
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

            if team == game.first_team or team == game.second_team or team == game.third_team:
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
                if game.first_team.device_registered and game.second_team.device_registered and not game.is_final:
                    game.state = 1
                    game.save()
                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'info',
                            'message': 'All devices registered, proceed to game start'
                        }
                    )
                elif game.first_team.device_registered and game.second_team.device_registered and game.third_team.device_registered:
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
        print("Sending question!")
        self.send(json.dumps({
            'type': 'question_send',
            'question': event.get('question'),
            'questionID': event.get('questionID'),
            'answers': event.get('answers'),
            'team': event.get('team')
        }))

    def category_send(self, event):
        print("Sending category!")
        self.send(json.dumps(event))

    def unregistered(self, event):
        self.send(json.dumps(event))


class GameMasterConsumer(WebsocketConsumer):

    def connect(self):
        async_to_sync(self.channel_layer.group_add)("game_master", self.channel_name)
        self.accept()

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("game_master", self.channel_name)

    def answer_reveal(self, event):
        self.send(json.dumps(event))

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception as exc:
            self.send("message received: \"{}\" is not valid json. Error: {}".format(
                text_data, exc))
            return

        action_type = data.get('type')

        if action_type == 'reveal_answer':
            game_id = data.get('game')
            try:
                game = DuelGame.objects.get(id=game_id)

            except DuelGame.DoesNotExist:
                self.send(json.dumps({
                    'error': 'Game with id {} does not exist'.format(game_id)
                }))
                return

            async_to_sync(self.channel_layer.group_send)(
                'game_master',
                {
                    'type': 'answer.reveal',
                    'answer': game.correct_answer,
                }
            )
        elif action_type == 'duel_game_continue':
            game_id = data.get('game')
            try:
                game = DuelGame.objects.get(id=game_id)

            except DuelGame.DoesNotExist:
                self.send(json.dumps({
                    'error': 'Game with id {} does not exist'.format(game_id)
                }))
                return
            print (game.state)
            # See the state of the game
            game_state = game.state
            if game_state == 0:
                if game.is_final:
                    teams = [game.winner.team.name for game in DuelGame.objects.filter(session=game.session, is_final=False)]
                else:
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
                    send_team = game.first_team.team.name if game.first_player_turn else game.second_team.team.name
                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'send.categories',
                            'categories': categories,
                            'team': send_team,
                            'first_team_score': game.first_team_score,
                            'first_team_name': game.first_team.team.name,
                            'second_team_score': game.second_team_score,
                            'second_team_name': game.second_team.team.name
                        }
                    )
                    time.sleep(0.2)
                    async_to_sync(self.channel_layer.group_send)(
                        'players',
                        {
                            'type': 'category.send',
                            'categories': categories,
                            'to': send_team
                        }
                    )
                else:
                    print(categories_removed)
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
                session = game.session
                questions_removed.append(selected_question.id)
                session.questions_removed = json.dumps(questions_removed)
                session.save()
                # Send the data
                if game.is_final:
                    async_to_sync(self.channel_layer.group_send)(
                        'game_master',
                        {
                            'type': 'send.question',
                            'question_text': selected_question.question_text,
                            'question_id': selected_question.id,
                            'answers': {answer.number: answer.answer_text for answer in
                                        Answer.objects.filter(question=selected_question)},
                            'team': 'all'
                        }
                    )
                    time.sleep(0.2)
                    async_to_sync(self.channel_layer.group_send)(
                        'players',
                        {
                            'type': 'question.send',
                            'question': selected_question.question_text,
                            'questionID': selected_question.id,
                            'answers': {answer.number: answer.answer_text for answer in
                                        Answer.objects.filter(question=selected_question)},
                            'team': 'all'
                        }
                    )
                    print("Sending question to all (final)")
                    return

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
                time.sleep(0.2)
                async_to_sync(self.channel_layer.group_send)(
                    'players',
                    {
                        'type': 'question.send',
                        'question': selected_question.question_text,
                        'questionID': selected_question.id,
                        'answers': {answer.number: answer.answer_text for answer in Answer.objects.filter(question=selected_question)},
                        'team': game.first_team.team.name if game.first_player_turn else game.second_team.team.name
                    }
                )

            elif game.state == 3:
                # Must send the question
                # First get the available questions
                questions_removed = json.loads(game.session.questions_removed)
                categories_removed = list({q.category for q in Question.objects.filter(id__in=questions_removed)})

                category = Question.objects.exclude(id__in=questions_removed).exclude(category__in=categories_removed).first().category

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
                        'team': 'all'
                    }
                )
                time.sleep(0.2)
                async_to_sync(self.channel_layer.group_send)(
                    'players',
                    {
                        'type': 'question.send',
                        'question': selected_question.question_text,
                        'questionID': selected_question.id,
                        'answers': {answer.number: answer.answer_text for answer in Answer.objects.filter(question=selected_question)},
                        'team': 'all'
                    }
                )
            elif game.state == 5:
                event = {"type": "unregistered",
                         "device_id": "all"}

                async_to_sync(self.channel_layer.group_send)('players', event)

                event2 = {"type": "ranking",
                          "first_team_score": game.first_team_score,
                          "first_team_name": game.first_team.team.name,
                          "second_team_score": game.second_team_score,
                          "second_team_name": game.second_team.team.name}
                async_to_sync(self.channel_layer.group_send)('game_master', event2)

    def ranking(self, event):
        self.send(json.dumps(event))

    def answer_receive(self, event):
        self.send(json.dumps(event))

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
        self.send(json.dumps(event))

    def send_categories(self, event):
        self.send(json.dumps(event))

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
