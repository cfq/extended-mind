from datetime import date

from django.core.management import call_command

from apps.items.models import Item, ItemStepRun

EDEN = "01a1a42b-07df-70aa-81c9-8eb4c9cc7688"


def test_reextract_fills_metadata_from_saved_html(item_sources_dir, data, capsys, app):
    item = Item.objects.get(id=EDEN)
    assert item.page.author == ""

    call_command("reextract")

    item = Item.objects.get(id=EDEN)
    assert item.page.author == "Terence Eden"
    assert item.site_name == "Terence Eden’s Blog"
    assert item.published_at == date(2026, 11, 3)
    assert item.page.markdown
    runs = ItemStepRun.objects.filter(step__item=item, step__name="extract")
    assert [r.outcome for r in runs] == ["ok", "ok"]
    assert "Re-extracted 5, skipped 0, failed 0." in capsys.readouterr().out
    jobs = {j["task_name"] for j in app.connector.jobs.values()}
    assert jobs == {"apps.items.tasks.save_images"}


def test_reextract_skips_items_without_source(item_sources_dir, user, capsys, app):
    Item.objects.create(user=user, url="https://x.test", url_submitted="x")

    call_command("reextract")

    assert "skipped 1" in capsys.readouterr().out


def test_reextract_reports_missing_file(item_sources_dir, data, capsys, app):
    for path in item_sources_dir.glob(f"{EDEN}/*.html"):
        path.unlink()

    call_command("reextract")

    out = capsys.readouterr()
    assert "Re-extracted 4, skipped 0, failed 1." in out.out
    assert EDEN in out.err
