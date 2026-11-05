from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    name = models.CharField("장르", max_length=40, unique=True)

    class Meta:
        ordering = ["pk"]
        verbose_name = "카테고리"

    def __str__(self):
        return self.name


class AIStatus(models.TextChoices):
    NOT_REQUESTED = "not_requested", "미생성"
    PROCESSING = "processing", "생성 중"
    READY = "ready", "생성 완료"
    FAILED = "failed", "생성 실패"


class Book(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    review_score = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(10)])
    author = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="books"
    )
    author_info = models.TextField(blank=True)
    author_works = models.JSONField(default=list, blank=True)
    author_image_url = models.URLField(max_length=1000, blank=True)
    author_source_url = models.URLField(max_length=1000, blank=True)
    author_ai_status = models.CharField(
        max_length=16, choices=AIStatus.choices, default=AIStatus.NOT_REQUESTED
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="books"
    )


class Thread(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="threads")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="threads"
    )

    cover_image = models.ImageField(upload_to="thread_covers/", blank=True)
    cover_keywords = models.JSONField(default=list, blank=True)
    cover_prompt = models.TextField(blank=True)
    cover_ai_status = models.CharField(
        max_length=16, choices=AIStatus.choices, default=AIStatus.NOT_REQUESTED
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    reading_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="liked_threads", blank=True
    )


class Comment(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField("댓글", max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
