import base64
import tempfile
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .forms import BookForm
from .models import Book, Thread, Category, Comment, AIStatus
from .services import (
    AIServiceError,
    _request_json,
    _structured_json,
    generate_author_data,
    generate_cover_data,
    lookup_author,
    populate_author,
    populate_cover,
)

User = get_user_model()


def image_bytes():
    buf = BytesIO()
    Image.new("RGB", (4, 4), "#21635d").save(buf, format="PNG")
    return buf.getvalue()


def author_data():
    return dict(
        author_info="검증된 작가 소개",
        author_works=["대표작"],
        author_image_url="",
        author_source_url="https://ko.wikipedia.org/wiki/Author",
    )


class OptionalFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="optionalowner", password="OptionalPass739!")
        cls.other = User.objects.create_user(username="optionalother", password="OptionalPass739!")
        cls.category = Category.objects.first()
        cls.book = Book.objects.create(
            title="Test book",
            description="Description",
            review_score=4,
            author="Author",
            user=cls.owner,
            category=cls.category,
        )
        cls.thread = Thread.objects.create(
            book=cls.book,
            user=cls.owner,
            title="Thread",
            content="Notes",
            reading_date="2026-11-05",
        )

    def test_seeded_categories_and_filter(self):
        self.assertEqual(Category.objects.count(), 7)
        other_category = Category.objects.exclude(pk=self.category.pk).first()
        Book.objects.create(
            title="Other genre",
            description="Description",
            review_score=3,
            author="Other author",
            user=self.owner,
            category=other_category,
        )
        response = self.client.get(reverse("books:index"), {"category": self.category.pk})
        self.assertContains(response, "Test book")
        self.assertNotContains(response, "Other genre")
        for value in ["invalid", "9" * 60, "-1"]:
            self.assertEqual(
                self.client.get(reverse("books:index"), {"category": value}).status_code, 200
            )

    def test_category_form_validation(self):
        form = BookForm(
            {"title": "B", "description": "D", "review_score": 4, "author": "A", "category": 99999}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_preferred_categories_signup_update_and_profile(self):
        selected = list(Category.objects.values_list("pk", flat=True)[:2])
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "genreuser",
                "password1": "GenrePass739!",
                "password2": "GenrePass739!",
                "weekly_reading_time": 2,
                "yearly_reading_count": 5,
                "preferred_categories": selected,
            },
        )
        self.assertRedirects(response, reverse("books:index"))
        user = User.objects.get(username="genreuser")
        self.assertEqual(set(user.preferred_categories.values_list("pk", flat=True)), set(selected))
        profile = self.client.get(reverse("accounts:profile", args=[user.pk]))
        for category in user.preferred_categories.all():
            self.assertContains(profile, category.name)
        response = self.client.post(
            reverse("accounts:update"),
            {
                "email": "genre@example.com",
                "weekly_reading_time": 1,
                "yearly_reading_count": 3,
                "preferred_categories": [selected[0]],
            },
        )
        self.assertRedirects(response, reverse("books:index"))
        self.assertEqual(
            list(user.preferred_categories.values_list("pk", flat=True)), [selected[0]]
        )
        response = self.client.post(
            reverse("accounts:update"), {"weekly_reading_time": 1, "yearly_reading_count": 3}
        )
        self.assertRedirects(response, reverse("books:index"))
        self.assertFalse(user.preferred_categories.exists())

    def test_comment_create_validate_and_escape(self):
        self.client.force_login(self.other)
        url = reverse("books:comment_create", args=[self.thread.pk])
        for text in ["", "   ", "x" * 2001]:
            response = self.client.post(url, {"content": text})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["comment_form"].errors)
        self.assertEqual(Comment.objects.count(), 0)
        self.assertRedirects(
            self.client.post(url, {"content": "<script>alert(1)</script>", "user": self.owner.pk}),
            reverse("books:thread_detail", args=[self.thread.pk]),
        )
        comment = Comment.objects.get()
        self.assertEqual(comment.user, self.other)
        self.assertEqual(comment.thread, self.thread)
        response = self.client.get(reverse("books:thread_detail", args=[self.thread.pk]))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_comment_delete_author_only_and_scoped_to_thread(self):
        comment = Comment.objects.create(thread=self.thread, user=self.other, content="Comment")
        url = reverse("books:comment_delete", args=[self.thread.pk, comment.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
        self.assertNotContains(
            self.client.get(reverse("books:thread_detail", args=[self.thread.pk])),
            "optionalother님의 댓글 삭제",
        )
        self.client.force_login(self.other)
        other_thread = Thread.objects.create(
            book=self.book, user=self.other, title="Other", content="D", reading_date="2026-11-05"
        )
        self.assertEqual(
            self.client.post(
                reverse("books:comment_delete", args=[other_thread.pk, comment.pk])
            ).status_code,
            404,
        )
        self.assertRedirects(
            self.client.post(url), reverse("books:thread_detail", args=[self.thread.pk])
        )
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_new_endpoints_require_login_post_and_csrf(self):
        comment = Comment.objects.create(thread=self.thread, user=self.owner, content="C")
        endpoints = [
            ("author_generate", [self.book.pk]),
            ("cover_generate", [self.thread.pk]),
            ("comment_create", [self.thread.pk]),
            ("comment_delete", [self.thread.pk, comment.pk]),
        ]
        for name, args in endpoints:
            url = reverse("books:" + name, args=args)
            self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.owner)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        for name, args in endpoints:
            url = reverse("books:" + name, args=args)
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(csrf_client.post(url).status_code, 403)

    @patch("books.services.generate_author_data", return_value=author_data())
    def test_author_retry_saves_and_enforces_ownership(self, generate):
        url = reverse("books:author_generate", args=[self.book.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        generate.assert_not_called()
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(url), reverse("books:detail", args=[self.book.pk]))
        self.book.refresh_from_db()
        self.assertEqual(self.book.author_info, "검증된 작가 소개")
        self.assertEqual(self.book.author_ai_status, AIStatus.READY)
        self.assertContains(
            self.client.get(reverse("books:detail", args=[self.book.pk])),
            "작가 대표작과 작가 정보는 AI가 생성한 정보로, 정확하지 않을 수 있습니다.",
        )

    @patch("books.services.generate_author_data", side_effect=AIServiceError("일시적 연결 실패"))
    def test_ai_failure_keeps_book_and_allows_retry(self, generate):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("books:create"),
            {
                "title": "Saved despite failure",
                "description": "D",
                "review_score": 4,
                "author": "A",
                "generate_author_info": "on",
            },
        )
        book = Book.objects.get(title="Saved despite failure")
        self.assertRedirects(response, reverse("books:detail", args=[book.pk]))
        self.assertEqual(book.author_ai_status, AIStatus.FAILED)
        with patch("books.services.generate_author_data", return_value=author_data()):
            self.client.post(reverse("books:author_generate", args=[book.pk]))
        book.refresh_from_db()
        self.assertEqual(book.author_ai_status, AIStatus.READY)

    def test_changing_author_clears_stale_profile(self):
        Book.objects.filter(pk=self.book.pk).update(
            author_info="Old biography", author_works=["Old work"], author_ai_status=AIStatus.READY
        )
        self.client.force_login(self.owner)
        self.client.post(
            reverse("books:update", args=[self.book.pk]),
            {
                "title": "Test book",
                "description": "D",
                "review_score": 4,
                "author": "Different author",
            },
        )
        self.book.refresh_from_db()
        self.assertEqual(self.book.author_info, "")
        self.assertEqual(self.book.author_works, [])
        self.assertEqual(self.book.author_ai_status, AIStatus.NOT_REQUESTED)

    @patch("books.services.generate_cover_data")
    def test_cover_file_storage_replacement_and_delete_cleanup(self, generate):
        generate.return_value = {
            "bytes": image_bytes(),
            "extension": "png",
            "keywords": ["하나", "둘", "셋", "넷", "다섯"],
            "prompt": "original illustration",
        }
        self.client.force_login(self.owner)
        url = reverse("books:cover_generate", args=[self.thread.pk])
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.assertRedirects(
                self.client.post(url), reverse("books:thread_detail", args=[self.thread.pk])
            )
            self.thread.refresh_from_db()
            first = self.thread.cover_image.name
            self.assertTrue(self.thread.cover_image.storage.exists(first))
            self.assertEqual(len(self.thread.cover_keywords), 5)
            self.assertContains(
                self.client.get(reverse("books:thread_detail", args=[self.thread.pk])),
                self.thread.cover_image.url,
            )
            self.client.post(url)
            self.thread.refresh_from_db()
            second = self.thread.cover_image.name
            self.assertNotEqual(first, second)
            self.assertFalse(self.thread.cover_image.storage.exists(first))
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(reverse("books:thread_delete", args=[self.thread.pk]))
            self.assertFalse(self.thread.cover_image.storage.exists(second))

    @patch("books.services.generate_cover_data", side_effect=AIServiceError("Unavailable model"))
    def test_cover_failure_keeps_thread_and_checks_ownership(self, generate):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.post(reverse("books:cover_generate", args=[self.thread.pk])).status_code,
            403,
        )
        generate.assert_not_called()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("books:thread_create", args=[self.book.pk]),
            {
                "title": "Saved notes",
                "content": "C",
                "reading_date": "2026-11-05",
                "generate_cover_image": "on",
            },
        )
        thread = Thread.objects.get(title="Saved notes")
        self.assertRedirects(response, reverse("books:thread_detail", args=[thread.pk]))
        self.assertEqual(thread.cover_ai_status, AIStatus.FAILED)
        self.assertFalse(thread.cover_image)

    @patch("books.services.generate_author_data")
    @patch("books.services.generate_cover_data")
    def test_generation_in_progress_does_not_repeat_paid_request(self, cover, author):
        Book.objects.filter(pk=self.book.pk).update(author_ai_status=AIStatus.PROCESSING)
        Thread.objects.filter(pk=self.thread.pk).update(cover_ai_status=AIStatus.PROCESSING)
        self.book.refresh_from_db()
        self.thread.refresh_from_db()
        self.assertFalse(populate_author(self.book))
        self.assertFalse(populate_cover(self.thread))
        cover.assert_not_called()
        author.assert_not_called()

    def test_thread_deletion_cascades_comments(self):
        Comment.objects.create(thread=self.thread, user=self.other, content="C")
        self.thread.delete()
        self.assertFalse(Comment.objects.exists())


@override_settings(
    AI_ENABLED=True,
    AI_API_KEY="test-key-only",
    AI_BASE_URL="https://gms.ssafy.io/gmsapi/api.openai.com/v1",
)
class AIServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @patch("books.services.urlopen")
    def test_authenticated_request_and_key_never_in_errors(self, opening):
        opening.side_effect = HTTPError(
            "https://example.invalid", 401, "error", {}, BytesIO(b"test-key-only")
        )
        with self.assertRaises(AIServiceError) as caught:
            _request_json("https://example.invalid", payload={"test": True}, authenticated=True)
        self.assertNotIn("test-key-only", str(caught.exception))
        self.assertEqual(caught.exception.status_code, 401)
        request = opening.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key-only")
        for status in [429, 500]:
            opening.side_effect = HTTPError(
                "https://example.invalid", status, "error", {}, BytesIO()
            )
            with self.assertRaises(AIServiceError):
                _request_json("https://example.invalid", authenticated=True)

    @patch("books.services.urlopen")
    def test_transport_and_json_errors_are_safe(self, opening):
        opening.side_effect = URLError("test-key-only")
        with self.assertRaises(AIServiceError) as caught:
            _request_json("https://example.invalid")
        self.assertNotIn("test-key-only", str(caught.exception))
        opening.side_effect = None
        opening.return_value = BytesIO(b"not json")
        with self.assertRaises(AIServiceError):
            _request_json("https://example.invalid")

    @patch("books.services._request_json")
    def test_structured_output_uses_assignment_text_model(self, request):
        request.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": '{"answer":true}'}}]
        }
        result = _structured_json("test", {"type": "object"}, "System", {"data": "D"})
        self.assertTrue(result["answer"])
        payload = request.call_args.args[1]
        self.assertEqual(payload["model"], "gpt-5-nano")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        for response in [
            {"choices": []},
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            {"choices": [{"finish_reason": "stop", "message": {"refusal": "No"}}]},
        ]:
            request.return_value = response
            with self.assertRaises(AIServiceError):
                _structured_json("t", {}, "S", {})

    @patch("books.services._request_json")
    def test_wikipedia_selects_author_not_river_and_rejects_external_image(self, request):
        request.return_value = {
            "query": {
                "pages": [
                    {"title": "한강", "extract": "대한민국의 강입니다."},
                    {
                        "title": "한강 (작가)",
                        "extract": "대한민국의 소설가이다.",
                        "fullurl": "https://ko.wikipedia.org/wiki/Han",
                        "thumbnail": {"source": "http://evil.invalid/x.png"},
                    },
                ]
            }
        }
        result = lookup_author("한강")
        self.assertEqual(result["title"], "한강 (작가)")
        self.assertEqual(result["image_url"], "")
        self.assertTrue(result["source_url"].startswith("https://ko.wikipedia.org/"))

    @patch("books.services._structured_json")
    @patch("books.services.lookup_author")
    def test_author_schema_validation(self, wiki, structured):
        wiki.return_value = {
            "extract": "Biography",
            "source_url": "https://ko.wikipedia.org/wiki/A",
            "image_url": "",
        }
        structured.return_value = {"author_info": "Biography", "author_works": ["Book"]}
        self.assertEqual(generate_author_data("A", "B")["author_works"], ["Book"])
        for value in [
            {"author_info": "", "author_works": []},
            {"author_info": "X", "author_works": "wrong"},
            {"author_info": "X", "author_works": [1]},
        ]:
            structured.return_value = value
            with self.assertRaises(AIServiceError):
                generate_author_data("A", "B")

    @override_settings(AI_IMAGE_MODEL="gpt-image-2")
    @patch("books.services._request_json")
    @patch("books.services._structured_json")
    def test_cover_pipeline_uses_five_keywords_and_gpt_image_payload(self, structured, request):
        structured.return_value = {
            "keywords": ["기억", "위로", "슬픔", "고요", "희망"],
            "prompt": "Original artwork",
        }
        request.return_value = {"data": [{"b64_json": base64.b64encode(image_bytes()).decode()}]}
        result = generate_cover_data("Book", "Author", "Title", "Notes")
        self.assertEqual(len(result["keywords"]), 5)
        self.assertEqual(result["extension"], "png")
        payload = request.call_args.args[1]
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["quality"], "low")
        self.assertNotIn("response_format", payload)
        self.assertEqual(payload["prompt"], "Original artwork")

    @patch("books.services._request_json")
    @patch("books.services._structured_json")
    def test_invalid_keywords_stop_before_paid_image_call(self, structured, request):
        for keys in [["only one"], ["same"] * 5]:
            structured.return_value = {"keywords": keys, "prompt": "Art"}
            with self.assertRaises(AIServiceError):
                generate_cover_data("B", "A", "T", "C")
        request.assert_not_called()

    @patch("books.services._request_json")
    @patch("books.services._structured_json")
    def test_invalid_image_bytes_rejected(self, structured, request):
        structured.return_value = {"keywords": ["1", "2", "3", "4", "5"], "prompt": "Art"}
        for value in ["not base64", base64.b64encode(b"not an image").decode()]:
            request.return_value = {"data": [{"b64_json": value}]}
            with self.assertRaises(AIServiceError):
                generate_cover_data("B", "A", "T", "C")

    @override_settings(AI_ENABLED=False, AI_API_KEY="")
    @patch("books.services._request_json")
    def test_missing_credentials_fail_before_network(self, request):
        with self.assertRaises(AIServiceError):
            generate_author_data("A", "B")
        with self.assertRaises(AIServiceError):
            generate_cover_data("B", "A", "T", "C")
        request.assert_not_called()

    @patch("books.services._request_json")
    def test_wikipedia_portrait_fallback_uses_trusted_english_source(self, request):
        request.side_effect = [
            {
                "query": {
                    "pages": [
                        {
                            "title": "한강 (작가)",
                            "extract": "대한민국의 소설가이다.",
                            "fullurl": "https://ko.wikipedia.org/wiki/Han",
                            "langlinks": [{"lang": "en", "title": "Han Kang"}],
                        }
                    ]
                }
            },
            {
                "query": {
                    "pages": [
                        {
                            "thumbnail": {
                                "source": "https://upload.wikimedia.org/wikipedia/commons/a/a0/Portrait.jpg"
                            }
                        }
                    ]
                }
            },
        ]
        result = lookup_author("한강")
        self.assertTrue(result["image_url"].startswith("https://upload.wikimedia.org/"))


class AuthorSearchRegressionTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def page(self, title="데일 카네기", **extra):
        result = {
            "title": title,
            "extract": title + "는 작가이자 저술가이다.",
            "fullurl": "https://ko.wikipedia.org/wiki/Dale_Carnegie",
            "_search_snippet": "대표 저서 인간관계론을 집필했다.",
        }
        result.update(extra)
        return result

    @patch("books.services._search_author_pages")
    def test_reported_carnegie_surname_typo_uses_book_evidence(self, search):
        search.return_value = [self.page()]
        self.assertEqual(lookup_author("카네키", "인간관계론")["title"], "데일 카네기")
        self.assertEqual(lookup_author("카네키", "인간 관계 론")["title"], "데일 카네기")

    @patch("books.services._search_author_pages")
    def test_typo_without_book_evidence_is_not_guessed(self, search):
        search.return_value = [self.page(_search_snippet="")]
        with self.assertRaises(AIServiceError):
            lookup_author("카네키", "알 수 없는 책")

    @patch("books.services._search_author_pages")
    def test_punctuation_unicode_and_aliases(self, search):
        search.return_value = [
            self.page(
                title="조앤 롤링", redirects=[{"title": "J. K. 롤링"}, {"title": "J.K. Rowling"}]
            )
        ]
        self.assertEqual(lookup_author("Ｊ．Ｋ．Rowling")["title"], "조앤 롤링")
        self.assertEqual(lookup_author("J.K. 롤링")["title"], "조앤 롤링")

    @patch("books.services._search_author_pages")
    def test_spaces_and_author_suffix(self, search):
        search.return_value = [self.page(title="한강 (작가)")]
        self.assertEqual(lookup_author("한 강 지음", "소년이온다")["title"], "한강 (작가)")
        self.assertEqual(lookup_author("한강 (작가)")["title"], "한강 (작가)")

    @patch("books.services._search_author_pages")
    def test_translated_name_and_latin_name_order(self, search):
        search.return_value = [
            self.page(
                title="무라카미 하루키",
                langlinks=[{"lang": "en", "title": "Haruki Murakami"}],
                thumbnail={"source": "https://upload.wikimedia.org/a.jpg"},
            )
        ]
        self.assertEqual(lookup_author("Murakami Haruki")["title"], "무라카미 하루키")

    @patch("books.services._search_author_pages")
    def test_book_distinguishes_same_name_people(self, search):
        search.return_value = [
            self.page(title="김영하 (소설가)"),
            self.page(title="김영하 (시인)", _search_snippet="다른 작품을 집필했다."),
        ]
        self.assertEqual(lookup_author("김영하", "인간관계론")["title"], "김영하 (소설가)")

    @patch("books.services._search_author_pages")
    def test_ambiguous_matches_are_not_selected_by_search_order(self, search):
        search.return_value = [self.page(title="김영하 (소설가)"), self.page(title="김영하 (시인)")]
        with self.assertRaises(AIServiceError):
            lookup_author("김영하", "인간관계론")

    @patch("books.services._search_author_pages")
    def test_book_query_is_fallback_when_name_search_is_empty(self, search):
        def results(lang, query):
            return [self.page()] if query == "인간관계론" else []

        search.side_effect = results
        self.assertEqual(lookup_author("카네키", "인간관계론")["title"], "데일 카네기")

    @patch("books.services._search_author_pages")
    def test_short_fragment_and_disambiguation_do_not_match(self, search):
        search.return_value = [
            self.page(title="김영하"),
            self.page(title="김", pageprops={"disambiguation": ""}),
        ]
        with self.assertRaises(AIServiceError):
            lookup_author("김", "인간관계론")

    @patch("books.services._search_author_pages")
    def test_rate_limit_is_not_misreported_as_missing_author(self, search):
        search.side_effect = AIServiceError("rate limited", status_code=429)
        with self.assertRaises(AIServiceError) as caught:
            lookup_author("카네키", "인간관계론")
        self.assertEqual(caught.exception.status_code, 429)
        self.assertIn("제한", str(caught.exception))
        self.assertEqual(search.call_count, 1)

    @patch("books.services._request_json")
    def test_search_suggestions_and_snippets_are_used(self, request):
        from .services import _search_author_pages
        from urllib.parse import parse_qs, urlsplit

        page = self.page(pageid=1)
        request.side_effect = [
            {"query": {"searchinfo": {"suggestion": "카네기"}}},
            {
                "query": {
                    "pages": [page],
                    "search": [
                        {
                            "pageid": 1,
                            "snippet": "<span>인간관계론</span> 저자",
                            "redirecttitle": "카네기",
                        }
                    ],
                }
            },
        ]
        found = _search_author_pages("ko", "카네키")
        self.assertEqual(found[0]["_search_snippet"], "인간관계론 저자")
        self.assertEqual(found[0]["_matched_redirects"], ["카네기"])
        self.assertEqual(
            parse_qs(urlsplit(request.call_args.args[0]).query)["gsrsearch"], ["카네기"]
        )

    @patch("books.services._search_author_pages")
    def test_repeated_normalized_search_uses_cached_verified_author(self, search):
        search.return_value = [self.page()]
        lookup_author("카네키", "인간관계론")
        calls = search.call_count
        self.assertEqual(lookup_author("카네키", "인간 관계론")["title"], "데일 카네기")
        self.assertEqual(search.call_count, calls)
