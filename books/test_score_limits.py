from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from .forms import BookForm
from .models import Book


class ReviewScoreTests(SimpleTestCase):
    def test_zero_ten_and_decimal_scores_are_valid(self):
        for score in [0, 10, 9.75]:
            with self.subTest(score=score):
                form = BookForm(
                    {
                        "title": "Book",
                        "description": "Description",
                        "review_score": score,
                        "author": "Author",
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)
        html = str(BookForm()["review_score"])
        self.assertIn('max="10"', html)
        self.assertIn('min="0"', html)

    def test_model_validation_rejects_scores_outside_range(self):
        for score in [-0.01, 10.01]:
            with self.subTest(score=score):
                book = Book(title="B", description="D", review_score=score, author="A")
                with self.assertRaises(ValidationError) as caught:
                    book.full_clean(exclude=["user", "category"])
                self.assertIn("review_score", caught.exception.message_dict)
