"""Structural tests for the docs generator (no golden files).

The generated pages are build artifacts that exist only on the GitHub Pages
deployment, so these tests assert *structural invariants* against in-memory
output rather than diffing against committed files.
"""

from scripts import generate_docs


def test_catalog_matches_command_lister():
    catalog = generate_docs.collect_catalog()
    assert catalog == generate_docs.CommandLister.to_groups()
    assert len(catalog) > 0
    for group in catalog:
        assert group["commands"], f"empty section for module {group['module']}"


def test_validate_passes():
    errors = generate_docs.validate(
        generate_docs.collect_catalog(),
        generate_docs.collect_area_prefs(),
        generate_docs.collect_hub_prefs(),
    )
    assert errors == []


def test_area_pref_metadata_is_bijective_with_live_attrs():
    names = {name for name, _, _ in generate_docs.collect_area_prefs()}
    assert set(generate_docs.AREA_PREFS_META) == names


def test_hub_pref_metadata_is_bijective_with_live_attrs():
    names = {name for name, _, _ in generate_docs.collect_hub_prefs()}
    assert set(generate_docs.HUB_PREFS_META) == names


def test_every_pref_has_a_description():
    all_meta = generate_docs.AREA_PREFS_META.values()
    all_meta = (*all_meta, *generate_docs.HUB_PREFS_META.values())
    for meta in all_meta:
        assert meta["description"]


def test_pages_are_idempotent_and_start_with_banner():
    first = {name: fn() for name, fn in generate_docs.PAGES.items()}
    second = {name: fn() for name, fn in generate_docs.PAGES.items()}
    assert second == first
    for name, page in first.items():
        assert page.startswith("<!-- AUTO-GENERATED"), name
        assert page.endswith("\n"), name
        assert "do not edit" in page.splitlines()[0], name


def test_commands_page_covers_every_module():
    page = generate_docs.render_commands()
    for group in generate_docs.collect_catalog():
        title = group["module"].replace("_", " ").title()
        assert f"## {title}" in page


def test_switch_check_accepts_fresh_output(tmp_path):
    ok, message = generate_docs.check(str(tmp_path))
    assert ok, message
