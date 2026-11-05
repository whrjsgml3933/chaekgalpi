from django.urls import path
from . import views

app_name = "books"

urlpatterns = [
    path("<int:book_pk>/author/generate/", views.author_generate, name="author_generate"),
    path("threads/<int:thread_pk>/cover/generate/", views.cover_generate, name="cover_generate"),
    path("threads/<int:thread_pk>/comments/", views.comment_create, name="comment_create"),
    path(
        "threads/<int:thread_pk>/comments/<int:comment_pk>/delete/",
        views.comment_delete,
        name="comment_delete",
    ),
    path("threads/<int:thread_pk>/like/", views.like, name="like"),
    path("", views.index, name="index"),
    path("create/", views.create, name="create"),
    path("<int:book_pk>/", views.detail, name="detail"),
    path("<int:book_pk>/update/", views.update, name="update"),
    path("<int:book_pk>/delete/", views.delete, name="delete"),
    path("<int:book_pk>/threads/create/", views.thread_create, name="thread_create"),
    path("threads/<int:thread_pk>/", views.thread_detail, name="thread_detail"),
    path("threads/<int:thread_pk>/update/", views.thread_update, name="thread_update"),
    path("threads/<int:thread_pk>/delete/", views.thread_delete, name="thread_delete"),
]
