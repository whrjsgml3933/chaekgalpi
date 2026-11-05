from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    UserChangeForm,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class CategoryCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    template_name = "widgets/category_options.html"
    option_template_name = "widgets/category_option.html"


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "gender",
            "birth_date",
            "age",
            "weekly_reading_time",
            "yearly_reading_count",
            "profile_image",
            "preferred_categories",
        )
        widgets = {"preferred_categories": CategoryCheckboxSelectMultiple}


class CustomUserChangeForm(UserChangeForm):
    password = None

    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "gender",
            "birth_date",
            "age",
            "weekly_reading_time",
            "yearly_reading_count",
            "profile_image",
            "preferred_categories",
        )
        widgets = {"preferred_categories": CategoryCheckboxSelectMultiple}
