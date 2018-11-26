from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView

from contest.models import Question, Answer, Quiz
from contest.serializers import QuestionSerializer, AnswerSerializer, QuizSerializer, SimpleAnswerSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404


class QuizzesList(APIView):

    def get(self, request, format=None):
        quizzes = Quiz.objects.all()
        serializer = QuizSerializer(quizzes, many=True, context={
            'request': request
        })
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = QuizSerializer(data=request.data, context={
            'request': request
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuizDetail(APIView):

    def get_object(self, pk):
        try:
            return Quiz.objects.get(id=pk)
        except Quiz.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        quiz = self.get_object(pk)
        serializer = QuizSerializer(quiz, context={
            'request': request
        })
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        quiz = self.get_object(pk)
        serializer = QuizSerializer(quiz, data=request.data, context={
            'request': request
        })

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, **kwargs):
        quiz = self.get_object(pk)
        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuestionsList(APIView):

    def get(self, request, format=None):
        questions = Question.objects.all()
        serializer = QuestionSerializer(questions, many=True, context={
            'request': request
        })
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = QuestionSerializer(data=request.data, context={
            'request': request
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuestionDetail(APIView):

    def get_object(self, pk):
        try:
            return Question.objects.get(id=pk)
        except Question.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        question = self.get_object(pk)
        serializer = QuestionSerializer(question, context={
            'request': request
        })
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        question = self.get_object(pk)
        serializer = QuestionSerializer(question, data=request.data, context={
            'request': request
        })

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, **kwargs):
        question = self.get_object(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnswersList(ListAPIView):

    queryset = Answer.objects.all()
    serializer_class = AnswerSerializer
    filter_fields = ('id', 'number', 'question_id', 'is_correct')

    # def get(self, request, format=None):
    #     answers = Answer.objects.all()
    #     serializer = AnswerSerializer(answers, many=True, context={
    #         'request': request
    #     })
    #     return Response(serializer.data)
    #
    def post(self, request, format=None):
        serializer = AnswerSerializer(data=request.data, context={
            'request': request
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnswerDetail(APIView):

    def get_object(self, pk):
        try:
            return Answer.objects.get(id=pk)
        except Question.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        answer = self.get_object(pk)
        serializer = AnswerSerializer(answer, context={
            'request': request
        })
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        answer = self.get_object(pk)
        serializer = AnswerSerializer(answer, data=request.data, context={
            'request': request
        })

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, **kwargs):
        answer = self.get_object(pk)
        answer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
def start_game_session(request):
    quiz_id = request.data.get('session_id')
    channel_layer = get_channel_layer()

    try:
        quiz = Quiz.objects.get(id=quiz_id)
    except Quiz.DoesNotExist:
        raise Http404

    question = Question.objects.filter(quiz=quiz).order_by('order').first()
    quiz.question_order = question.order

    if quiz.type == 1:
        # Only send to one team, at a time
        quiz.team_order = 1
        quiz.save()

    answers = SimpleAnswerSerializer(question.answer_set, many=True)

    async_to_sync(channel_layer.group_send)(
        'game_master',
        {
            'type': 'send.question',
            'question_text': question.question_text,
            'answers': answers.data,
            'to': quiz.team_order
        }
    )

    return Response('ok')
