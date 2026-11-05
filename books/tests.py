from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Book, Thread

User = get_user_model()


class BookThreadFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="writer", password="WriterPass739!")
        self.other = User.objects.create_user(username="visitor", password="VisitorPass739!")
        self.book = Book.objects.create(
            title="Original book",
            description="Description",
            review_score=4.5,
            author="Author",
            user=self.owner,
        )
        self.thread = Thread.objects.create(
            book=self.book,
            user=self.owner,
            title="Original thread",
            content="Reading notes",
            reading_date="2026-11-05",
        )

    def book_data(self, **extra):
        data = dict(
            title="New book", description="New description", review_score=4.0, author="New author"
        )
        data.update(extra)
        return data

    def thread_data(self, **extra):
        data = dict(title="New thread", content="New notes", reading_date="2026-11-04")
        data.update(extra)
        return data

    def test_public_reads_and_navigation(self):
        for url, text in [
            (reverse("books:index"), "Original book"),
            (reverse("books:detail", args=[self.book.pk]), "Original thread"),
            (reverse("books:thread_detail", args=[self.thread.pk]), "Reading notes"),
            (reverse("accounts:profile", args=[self.owner.pk]), "Original thread"),
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), text)
        self.assertNotContains(self.client.get(reverse("books:index")), "도서 등록")
        self.assertNotContains(
            self.client.get(reverse("books:detail", args=[self.book.pk])), "도서 삭제"
        )

    def test_book_create_update_delete(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("books:create")).status_code, 200)
        response = self.client.post(reverse("books:create"), self.book_data(user=self.other.pk))
        book = Book.objects.get(title="New book")
        self.assertEqual(book.user, self.owner)
        self.assertRedirects(response, reverse("books:detail", args=[book.pk]))
        url = reverse("books:update", args=[book.pk])
        self.assertEqual(self.client.get(url).context["form"].instance.pk, book.pk)
        self.assertRedirects(
            self.client.post(url, self.book_data(title="Edited book")),
            reverse("books:detail", args=[book.pk]),
        )
        book.refresh_from_db()
        self.assertEqual(book.title, "Edited book")
        self.assertRedirects(
            self.client.post(reverse("books:delete", args=[book.pk])), reverse("books:index")
        )
        self.assertFalse(Book.objects.filter(pk=book.pk).exists())

    def test_thread_create_update_delete(self):
        self.client.force_login(self.owner)
        url = reverse("books:thread_create", args=[self.book.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, self.thread_data(user=self.other.pk))
        thread = Thread.objects.get(title="New thread")
        self.assertEqual(thread.user, self.owner)
        self.assertEqual(thread.book, self.book)
        detail = reverse("books:thread_detail", args=[thread.pk])
        self.assertRedirects(response, detail)
        url = reverse("books:thread_update", args=[thread.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertRedirects(self.client.post(url, self.thread_data(title="Edited thread")), detail)
        thread.refresh_from_db()
        self.assertEqual(thread.title, "Edited thread")
        self.assertRedirects(
            self.client.post(reverse("books:thread_delete", args=[thread.pk])),
            reverse("books:detail", args=[self.book.pk]),
        )
        self.assertFalse(Thread.objects.filter(pk=thread.pk).exists())

    def test_invalid_book_and_thread_data(self):
        self.client.force_login(self.owner)
        for name, args, data in [
            ("create", [], self.book_data(title="")),
            ("create", [], self.book_data(review_score="bad")),
            ("update", [self.book.pk], self.book_data(title="")),
            ("thread_create", [self.book.pk], self.thread_data(reading_date="bad")),
            ("thread_create", [self.book.pk], self.thread_data(content="")),
            ("thread_update", [self.thread.pk], self.thread_data(reading_date="bad")),
        ]:
            with self.subTest(name=name, data=data):
                response = self.client.post(reverse("books:" + name, args=args), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Thread.objects.count(), 1)
        self.book.refresh_from_db()
        self.thread.refresh_from_db()
        self.assertEqual(self.book.title, "Original book")
        self.assertEqual(self.thread.title, "Original thread")

    def test_other_user_cannot_edit_or_delete(self):
        self.client.force_login(self.other)
        for name, pk, data in [
            ("update", self.book.pk, self.book_data()),
            ("thread_update", self.thread.pk, self.thread_data()),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse("books:" + name, args=[pk])).status_code, 302
                )
                self.assertEqual(
                    self.client.post(reverse("books:" + name, args=[pk]), data).status_code, 302
                )
        self.client.post(reverse("books:delete", args=[self.book.pk]))
        self.client.post(reverse("books:thread_delete", args=[self.thread.pk]))
        self.book.refresh_from_db()
        self.thread.refresh_from_db()
        self.assertEqual(self.book.title, "Original book")
        self.assertEqual(self.thread.title, "Original thread")
        self.assertNotContains(
            self.client.get(reverse("books:thread_detail", args=[self.thread.pk])), "독서 기록 삭제"
        )

    def test_anonymous_writes_require_login(self):
        for name, args, data in [
            ("create", [], self.book_data()),
            ("update", [self.book.pk], self.book_data()),
            ("delete", [self.book.pk], {}),
            ("thread_create", [self.book.pk], self.thread_data()),
            ("thread_update", [self.thread.pk], self.thread_data()),
            ("thread_delete", [self.thread.pk], {}),
            ("like", [self.thread.pk], {}),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.post(reverse("books:" + name, args=args), data).status_code, 302
                )
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Thread.objects.count(), 1)
        self.assertEqual(self.thread.likes.count(), 0)

    def test_like_toggle(self):
        self.client.force_login(self.other)
        url = reverse("books:like", args=[self.thread.pk])
        detail = reverse("books:thread_detail", args=[self.thread.pk])
        self.assertRedirects(self.client.post(url), detail)
        self.assertTrue(self.thread.likes.filter(pk=self.other.pk).exists())
        self.assertContains(self.client.get(detail), "좋아요 취소")
        self.assertRedirects(self.client.post(url), detail)
        self.assertFalse(self.thread.likes.exists())

    def test_http_methods_and_missing_records(self):
        self.client.force_login(self.owner)
        for name, pk in [
            ("delete", self.book.pk),
            ("thread_delete", self.thread.pk),
            ("like", self.thread.pk),
        ]:
            self.assertEqual(self.client.get(reverse("books:" + name, args=[pk])).status_code, 405)
        for name, args in [
            ("index", []),
            ("detail", [self.book.pk]),
            ("thread_detail", [self.thread.pk]),
        ]:
            self.assertEqual(self.client.post(reverse("books:" + name, args=args)).status_code, 405)
        for name in ["detail", "update", "thread_create", "thread_detail", "thread_update"]:
            self.assertEqual(
                self.client.get(reverse("books:" + name, args=[99999])).status_code, 404
            )
        for name in ["delete", "thread_delete", "like"]:
            self.assertEqual(
                self.client.post(reverse("books:" + name, args=[99999])).status_code, 404
            )

    def test_book_deletion_cascades_threads_and_likes(self):
        self.thread.likes.add(self.other)
        self.client.force_login(self.owner)
        self.client.post(reverse("books:delete", args=[self.book.pk]))
        self.assertFalse(Thread.objects.filter(pk=self.thread.pk).exists())
        self.assertEqual(Thread.likes.through.objects.count(), 0)

    def test_user_deletion_cascades_owned_content(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("accounts:delete"))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())
        self.assertFalse(Thread.objects.filter(pk=self.thread.pk).exists())

    def test_csrf_blocks_writes_without_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for name, pk in [
            ("delete", self.book.pk),
            ("thread_delete", self.thread.pk),
            ("like", self.thread.pk),
        ]:
            self.assertEqual(client.post(reverse("books:" + name, args=[pk])).status_code, 403)
        client.get(reverse("books:thread_detail", args=[self.thread.pk]))
        self.assertEqual(
            client.post(
                reverse("books:like", args=[self.thread.pk]),
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            ).status_code,
            302,
        )

    def test_review_score_limit_is_enforced_for_create_and_update(self):
        self.client.force_login(self.owner)
        for name, args in [("create", []), ("update", [self.book.pk])]:
            for score in [-0.1, 10.1, "NaN", "Infinity"]:
                with self.subTest(name=name, score=score):
                    response = self.client.post(
                        reverse("books:" + name, args=args), self.book_data(review_score=score)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("review_score", response.context["form"].errors)
        self.assertEqual(Book.objects.count(), 1)
        self.book.refresh_from_db()
        self.assertEqual(self.book.review_score, 4.5)
        response = self.client.post(
            reverse("books:update", args=[self.book.pk]), self.book_data(review_score=10)
        )
        self.assertRedirects(response, reverse("books:detail", args=[self.book.pk]))
        self.book.refresh_from_db()
        self.assertEqual(self.book.review_score, 10)
