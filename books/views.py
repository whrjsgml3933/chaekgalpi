from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Book, Thread, Category, Comment, AIStatus
from .forms import BookForm, ThreadForm, CommentForm
from .services import AIServiceError, populate_author, populate_cover


def _author_feedback(request, book):
    try:
        if populate_author(book):
            messages.success(request, "작가 정보를 생성했습니다.")
        else:
            messages.info(request, "작가 정보를 생성 중입니다. 잠시 후 확인해 주세요.")
    except AIServiceError as exc:
        messages.warning(request, "도서는 저장됐습니다. " + str(exc))


def _cover_feedback(request, thread):
    try:
        if populate_cover(thread):
            messages.success(request, "커버 이미지를 생성했습니다.")
        else:
            messages.info(request, "커버 이미지를 생성 중입니다. 잠시 후 확인해 주세요.")
    except AIServiceError as exc:
        messages.warning(request, str(exc))


@require_GET
def index(request):
    categories = Category.objects.all()
    category_id = request.GET.get("category", "")
    selected_category = None
    if category_id.isdecimal() and len(category_id) <= 18:
        selected_category = categories.filter(pk=int(category_id)).first()
    books = Book.objects.select_related("user", "category").annotate(thread_count=Count("threads"))
    if selected_category:
        books = books.filter(category=selected_category)
    return render(
        request,
        "books/index.html",
        {"books": books, "categories": categories, "selected_category": selected_category},
    )


@login_required
@require_http_methods(["GET", "POST"])
def create(request):
    if request.method == "POST":
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            if form.cleaned_data["generate_author_info"]:
                _author_feedback(request, book)
            return redirect("books:detail", book.pk)
    else:
        form = BookForm()
    return render(request, "books/create.html", {"form": form})


@require_GET
def detail(request, book_pk):
    book = get_object_or_404(
        Book.objects.select_related("user", "category").prefetch_related("threads__user"),
        pk=book_pk,
    )
    return render(request, "books/detail.html", {"book": book})


@login_required
@require_http_methods(["GET", "POST"])
def update(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)
    if book.user != request.user:
        return redirect("books:detail", book.pk)
    old_author = book.author
    if request.method == "POST":
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            if book.author != old_author:
                book.author_info = ""
                book.author_works = []
                book.author_image_url = ""
                book.author_source_url = ""
                book.author_ai_status = AIStatus.NOT_REQUESTED
            book.save()
            if form.cleaned_data["generate_author_info"]:
                _author_feedback(request, book)
            return redirect("books:detail", book.pk)
    else:
        form = BookForm(instance=book)
    return render(request, "books/update.html", {"form": form, "book": book})


@login_required
@require_POST
def delete(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)
    if book.user == request.user:
        book.delete()
    return redirect("books:index")


@login_required
@require_POST
def author_generate(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)
    if book.user != request.user:
        return HttpResponseForbidden("도서를 등록한 사용자만 작가 정보를 생성할 수 있습니다.")
    _author_feedback(request, book)
    return redirect("books:detail", book.pk)


@login_required
@require_http_methods(["GET", "POST"])
def thread_create(request, book_pk):
    book = get_object_or_404(Book, pk=book_pk)
    if request.method == "POST":
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.book = book
            thread.user = request.user
            thread.save()
            if form.cleaned_data["generate_cover_image"]:
                _cover_feedback(request, thread)
            return redirect("books:thread_detail", thread.pk)
    else:
        form = ThreadForm()
    return render(request, "books/thread_create.html", {"form": form, "book": book})


def _thread_context(thread, comment_form=None):
    return {
        "thread": thread,
        "comment_form": comment_form if comment_form is not None else CommentForm(),
        "comments": thread.comments.select_related("user"),
    }


@require_GET
def thread_detail(request, thread_pk):
    thread = get_object_or_404(Thread.objects.select_related("book", "user"), pk=thread_pk)
    return render(request, "books/thread_detail.html", _thread_context(thread))


@login_required
@require_http_methods(["GET", "POST"])
def thread_update(request, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)
    if thread.user != request.user:
        return redirect("books:thread_detail", thread.pk)
    if request.method == "POST":
        form = ThreadForm(request.POST, instance=thread)
        if form.is_valid():
            thread = form.save()
            if form.cleaned_data["generate_cover_image"]:
                _cover_feedback(request, thread)
            return redirect("books:thread_detail", thread.pk)
    else:
        form = ThreadForm(instance=thread)
    return render(request, "books/thread_update.html", {"form": form, "thread": thread})


@login_required
@require_POST
def thread_delete(request, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)
    if thread.user == request.user:
        book_pk = thread.book_id
        thread.delete()
        return redirect("books:detail", book_pk)
    return redirect("books:thread_detail", thread.pk)


@login_required
@require_POST
def cover_generate(request, thread_pk):
    thread = get_object_or_404(Thread.objects.select_related("book"), pk=thread_pk)
    if thread.user != request.user:
        return HttpResponseForbidden(
            "독서 기록을 작성한 사용자만 커버 이미지를 생성할 수 있습니다."
        )
    _cover_feedback(request, thread)
    return redirect("books:thread_detail", thread.pk)


@login_required
@require_POST
def like(request, thread_pk):
    thread = get_object_or_404(Thread, pk=thread_pk)
    if thread.likes.filter(pk=request.user.pk).exists():
        thread.likes.remove(request.user)
    else:
        thread.likes.add(request.user)
    return redirect("books:thread_detail", thread.pk)


@login_required
@require_POST
def comment_create(request, thread_pk):
    thread = get_object_or_404(Thread.objects.select_related("book", "user"), pk=thread_pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.thread = thread
        comment.user = request.user
        comment.save()
        return redirect("books:thread_detail", thread.pk)
    return render(request, "books/thread_detail.html", _thread_context(thread, form))


@login_required
@require_POST
def comment_delete(request, thread_pk, comment_pk):
    comment = get_object_or_404(Comment, pk=comment_pk, thread_id=thread_pk)
    if comment.user != request.user:
        return HttpResponseForbidden("댓글을 작성한 사용자만 삭제할 수 있습니다.")
    comment.delete()
    return redirect("books:thread_detail", thread_pk)
