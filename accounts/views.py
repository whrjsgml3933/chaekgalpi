from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
    get_user_model,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
)
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import CustomUserCreationForm, CustomUserChangeForm

User = get_user_model()


@require_http_methods(["GET", "POST"])
def login(request):
    if request.user.is_authenticated:
        return redirect("books:index")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect("books:index")
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("books:index")


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("books:index")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("books:index")
    else:
        form = CustomUserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})


@require_GET
def profile(request, pk):
    user = get_object_or_404(User, pk=pk)
    return render(request, "accounts/profile.html", {"profile_user": user})


@login_required
@require_http_methods(["GET", "POST"])
def update(request):
    if request.method == "POST":
        form = CustomUserChangeForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("books:index")
    else:
        form = CustomUserChangeForm(instance=request.user)

    return render(request, "accounts/update.html", {"form": form})


@login_required
@require_POST
def delete(request):
    request.user.delete()
    auth_logout(request)
    return redirect("books:index")


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect("books:index")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "accounts/change_password.html", {"form": form})


@login_required
@require_POST
def follow(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person != request.user:
        if request.user.followings.filter(pk=person.pk).exists():
            request.user.followings.remove(person)
        else:
            request.user.followings.add(person)
    return redirect("accounts:profile", person.pk)
