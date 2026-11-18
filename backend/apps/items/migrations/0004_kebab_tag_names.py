import re
import unicodedata

from django.db import migrations


# Frozen copy of tagging.normalize at the time of this migration.
def normalize(name):
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c)).lower()
    name = re.sub(r"[\s_\u2010-\u2015\u2212-]+", "-", name)
    name = re.sub(r"[^a-z0-9+#-]", "", name)
    name = re.sub(r"-{2,}", "-", name).strip("-").lstrip("#").strip("-")
    if len(name) > 50 or not re.search(r"[a-z0-9]", name):
        return ""
    return name


def kebab(apps, schema_editor):
    """'open source' → 'open-source', 'família' → 'familia'. Tags that end
    up equal are merged; unusable names are dropped."""
    Tag = apps.get_model("items", "Tag")
    ItemTag = apps.get_model("items", "ItemTag")
    ItemTagRemoval = apps.get_model("items", "ItemTagRemoval")

    for tag in Tag.objects.order_by("created_at"):
        name = normalize(tag.name)
        if name == tag.name:
            continue
        keep = Tag.objects.filter(user=tag.user_id, name=name).first() if name else None
        if not name:
            tag.delete()
        elif keep:
            for link in ItemTag.objects.filter(tag=tag):
                if not ItemTag.objects.filter(item=link.item_id, tag=keep).exists():
                    link.tag = keep
                    link.save(update_fields=["tag"])
            tag.delete()
        else:
            tag.name = name
            tag.save(update_fields=["name"])

    for removal in ItemTagRemoval.objects.all():
        name = normalize(removal.name)
        if name == removal.name:
            continue
        duplicate = ItemTagRemoval.objects.filter(item=removal.item_id, name=name)
        if not name or duplicate.exists():
            removal.delete()
        else:
            removal.name = name
            removal.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0003_tag_itemtag_itemtagremoval_tag_tag_user_name_and_more"),
    ]

    operations = [migrations.RunPython(kebab, migrations.RunPython.noop)]
