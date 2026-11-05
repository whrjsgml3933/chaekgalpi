"""Create idempotent, isolated local demo content without external API calls."""

import secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from books.models import Book, Category, Comment, Thread


class Command(BaseCommand):
    help = "Create local demo users and reading content; never calls AI services."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is available only with DJANGO_DEBUG=true.")
        User = get_user_model()
        group, _ = Group.objects.get_or_create(name="portfolio-demo-accounts")
        accounts = []
        for username in ("demo_reader", "demo_neighbor"):
            user, created = User.objects.get_or_create(username=username)
            if not created and not user.groups.filter(pk=group.pk).exists():
                raise CommandError(f"{username} already exists and is not a demo account.")
            if created:
                user.groups.add(group)
                user.weekly_reading_time = 4
                user.yearly_reading_count = 12
                if username == "demo_reader":
                    password = secrets.token_urlsafe(12)
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                user.save()
            accounts.append((user, created))
        reader, created = accounts[0]
        neighbor = accounts[1][0]
        genres = [Category.objects.get(name=name) for name in ("소설/시/희곡", "자기계발", "과학")]
        reader.preferred_categories.set(genres[:2])
        samples = [
            (
                "데모: 함께 읽는 소설",
                "시연 저자",
                "도서와 독서 기록을 둘러보기 위한 시연 데이터입니다.",
                genres[0],
            ),
            (
                "데모: 일상 속 관계",
                "시연 저자",
                "좋아요와 댓글로 다른 독자의 생각을 나눠보세요.",
                genres[1],
            ),
            (
                "데모: 과학 산책",
                "시연 저자",
                "장르 필터와 선호 장르를 확인하는 시연 데이터입니다.",
                genres[2],
            ),
        ]
        first = None
        for title, author, description, genre in samples:
            book, _ = Book.objects.get_or_create(
                user=reader,
                title=title,
                defaults={
                    "author": author,
                    "description": description,
                    "review_score": 9.0,
                    "category": genre,
                },
            )
            first = first or book
        thread, _ = Thread.objects.get_or_create(
            user=reader,
            book=first,
            title="책을 읽고 남긴 첫 생각",
            defaults={
                "content": "이 기록은 로컬 시연용입니다. 수정·좋아요·댓글 기능을 직접 확인해 보세요.",
                "reading_date": "2026-11-05",
            },
        )
        Comment.objects.get_or_create(
            user=neighbor, thread=thread, content="서로 다른 독서 경험을 함께 나눠요."
        )
        self.stdout.write(
            self.style.SUCCESS("Demo ready: demo_reader (3 books, 1 thread, 1 comment).")
        )
        if created:
            self.stdout.write("Temporary local password: " + password)
        else:
            self.stdout.write("Existing demo account retained; its password was not reset.")
