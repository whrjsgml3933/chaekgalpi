from django import forms
from django.conf import settings
from .models import Book, Thread, Comment


class BookForm(forms.ModelForm):
    review_score = forms.FloatField(
        label="회원 리뷰 평점",
        min_value=0,
        max_value=10,
        help_text="0~10점 사이로 입력해 주세요. 소수점도 입력할 수 있습니다.",
    )

    generate_author_info = forms.BooleanField(
        label="AI 작가 정보 생성",
        required=False,
        initial=True,
        help_text="저자 이름과 도서 정보를 위키피디아·AI 서비스에 전달해 작가 소개와 대표작을 생성합니다. 실패해도 도서는 저장됩니다.",
    )

    class Meta:
        model = Book
        fields = ("title", "description", "review_score", "author", "category")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["generate_author_info"].initial = settings.AI_ENABLED and not self.instance.pk


class ThreadForm(forms.ModelForm):
    generate_cover_image = forms.BooleanField(
        label="AI 커버 이미지 생성",
        required=False,
        initial=True,
        help_text="도서 제목·저자·독서 기록을 AI 서비스에 전달해 감정 키워드 5개와 커버 이미지를 생성합니다. 잠시 시간이 걸리며 실패해도 기록은 저장됩니다.",
    )

    class Meta:
        model = Thread
        fields = ("title", "content", "reading_date")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["generate_cover_image"].initial = settings.AI_ENABLED and not self.instance.pk


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 2000,
                    "placeholder": "이 독서 기록에 대한 생각을 남겨주세요.",
                }
            )
        }
