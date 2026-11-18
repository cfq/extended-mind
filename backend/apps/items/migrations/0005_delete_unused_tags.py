from django.db import migrations


def delete_unused(apps, schema_editor):
    Tag = apps.get_model("items", "Tag")
    Tag.objects.filter(item_tags__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0004_kebab_tag_names"),
    ]

    operations = [migrations.RunPython(delete_unused, migrations.RunPython.noop)]
