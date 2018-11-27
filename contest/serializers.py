from rest_framework import serializers

from contest.models import Question, Answer, Quiz


class SimpleAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ('number', 'answer_text')


class AnswerSerializer(serializers.HyperlinkedModelSerializer):
    question_id = serializers.PrimaryKeyRelatedField(
        read_only=False, many=False, source='question', queryset=Question.objects.all()
    )

    class Meta:
        model = Answer
        fields = ('id', 'url', 'number', 'answer_text', 'question_id', 'is_correct')
        extra_kwargs = {
            'url': {'view_name': 'answer-detail'}
        }

    def create(self, validated_data):
        question = validated_data.pop('question')

        return Answer.objects.create(
            number=validated_data.get('number'),
            answer_text=validated_data.get('answer_text'),
            question=question,
            is_correct=True if validated_data.get('is_correct') == 1 else None
        )


class QuestionSerializer(serializers.HyperlinkedModelSerializer):
    answer_set = AnswerSerializer(many=True, required=False)

    quiz_id = serializers.PrimaryKeyRelatedField(
        queryset=Quiz.objects.all(),
        source='quiz',
        read_only=False
    )

    class Meta:
        model = Question
        fields = ('id', 'url', 'question_text', 'answer_set', 'quiz_id', 'order')
        extra_kwargs = {
            'url': {'view_name': 'question-detail'}
        }

    def create(self, validated_data):
        quiz = validated_data.pop('quiz')
        return Question.objects.create(
            question_text=validated_data.get('question_text'),
            quiz=quiz,
            order=validated_data.get('order')
        )


class QuizSerializer(serializers.HyperlinkedModelSerializer):
    question_set = QuestionSerializer(many=True, required=False)

    class Meta:
        model = Quiz
        fields = ('id', 'url', 'type', 'question_set', 'name')
        extra_kwargs = {
            'url': {'view_name': 'quiz-detail'}
        }
