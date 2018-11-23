from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
import json


class QuizConsumer(WebsocketConsumer):

    def connect(self):
        self.accept()
        async_to_sync(self.channel_layer.group_add)("players", self.channel_name)

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("players", self.channel_name)

    def receive(self, text_data):
        data = json.loads(text_data)

        answer = data.get('answer')
        async_to_sync(self.channel_layer.group_send)(
            'game_master',
            {
                'type': 'answer.receive',
                'team': data.get('name'),
                'answer': answer
            }
        )

    def question_send(self, event):
        self.send(json.dumps({
            'question': event.get('question'),
            'anwers': event.get('answers')
        }))


class GameMasterConsumer(WebsocketConsumer):

    def connect(self):
        async_to_sync(self.channel_layer.group_add)("game_master", self.channel_name)
        self.accept()

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)("game_master", self.channel_name)

    def receive(self, text_data):

        async_to_sync(self.channel_layer.group_send)(
            'players',
            {
                'type': 'question.send',
                'question': 'Ce faci?',
                'answers': {
                    'a': 'bine',
                    'b': 'rau',
                    'c': 'nu stiu',
                    'd': 'pas'
                }
            }
        )

    def answer_receive(self, event):
        self.send(json.dumps({
            'team': event.get('team'),
            'answer': event.get('answer')
        }))

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
