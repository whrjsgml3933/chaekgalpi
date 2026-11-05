from django.db import migrations

NAMES = ["소설/시/희곡", "경제/경영", "자기계발", "인문/교양", "취미/실용", "어린이/청소년", "과학"]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("books", "Category")
    for name in NAMES:
        Category.objects.using(schema_editor.connection.alias).get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("books", "0002_optional_features")]
    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
