from django import forms, template

register = template.Library()
LABELS = {
    "username": "아이디",
    "password": "비밀번호",
    "password1": "비밀번호",
    "password2": "비밀번호 확인",
    "old_password": "현재 비밀번호",
    "new_password1": "새 비밀번호",
    "new_password2": "새 비밀번호 확인",
    "email": "이메일",
    "first_name": "이름",
    "last_name": "성",
    "gender": "성별",
    "birth_date": "생년월일",
    "age": "나이",
    "weekly_reading_time": "주간 평균 독서 시간",
    "yearly_reading_count": "연간 독서량",
    "profile_image": "프로필 사진",
    "title": "제목",
    "description": "도서 설명",
    "review_score": "회원 리뷰 평점",
    "author": "저자",
    "content": "본문",
    "reading_date": "독서일",
    "category": "장르",
    "preferred_categories": "선호 장르",
}


@register.filter
def field_label(field):
    return LABELS.get(field.name, field.label)


@register.filter
def bootstrap_field(field):
    widget = field.field.widget
    css = "form-select" if isinstance(widget, forms.Select) else "form-control"
    if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
        css = "form-check-input"
    attrs = {"class": css + (" is-invalid" if field.errors else "")}
    descriptions = []
    if field.help_text:
        descriptions.append(field.auto_id + "_helptext")
    if field.errors:
        descriptions.append(field.auto_id + "_errors")
        attrs["aria-invalid"] = "true"
    if descriptions:
        attrs["aria-describedby"] = " ".join(descriptions)
    if isinstance(widget, forms.Textarea):
        attrs["rows"] = 6
    if field.name in ("birth_date", "reading_date"):
        widget = forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    if field.name == "username":
        attrs["autocomplete"] = "username"
    if isinstance(widget, forms.PasswordInput):
        attrs["autocomplete"] = (
            "current-password" if field.name in ("password", "old_password") else "new-password"
        )
    return field.as_widget(widget=widget, attrs=attrs)


@register.filter
def is_checkbox_group(field):
    return isinstance(field.field.widget, forms.CheckboxSelectMultiple)


@register.filter
def is_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxInput)
