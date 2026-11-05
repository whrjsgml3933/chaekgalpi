from django.contrib import admin
from .models import Book, Thread, Comment, Category

admin.site.register([Book, Thread, Comment, Category])
