from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/<int:pk>/follow/", views.follow, name="follow"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("signup/", views.signup, name="signup"),
    path("profile/<int:pk>/", views.profile, name="profile"),
    path("update/", views.update, name="update"),
    path("delete/", views.delete, name="delete"),
    path("change-password/", views.change_password, name="change_password"),
]
