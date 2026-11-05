from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    gender = models.CharField(
        "성별", max_length=10, blank=True, choices=[("female", "여성"), ("male", "남성")]
    )
    preferred_categories = models.ManyToManyField(
        "books.Category", blank=True, related_name="readers", verbose_name="선호 장르"
    )
    birth_date = models.DateField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    weekly_reading_time = models.PositiveIntegerField(default=0)
    yearly_reading_count = models.PositiveIntegerField(default=0)
    profile_image = models.ImageField(upload_to="profiles/", null=True, blank=True)

    followings = models.ManyToManyField(
        "self", symmetrical=False, related_name="followers", blank=True
    )
