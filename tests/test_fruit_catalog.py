import json

import pytest

from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import FruitCatalogError, load_fruit_catalog, parse_fruit_catalog


def _catalog_payload(*fruit_ids: str) -> dict:
    classes = []
    fruits = []
    for fruit_id in fruit_ids:
        classes.append(
            {"label": f"fresh_{fruit_id}", "fruit": fruit_id, "freshness": "fresh"}
        )
        classes.append(
            {"label": f"rotten_{fruit_id}", "fruit": fruit_id, "freshness": "rotten"}
        )
        fruits.append(
            {
                "id": fruit_id,
                "display_name": fruit_id.title(),
                "fresh_shelf_life": f"Configured shelf life for {fruit_id}",
                "fresh_storage_advice": f"Configured storage for {fruit_id}.",
            }
        )
    return {"schema_version": 1, "classes": classes, "fruits": fruits}


def test_default_catalog_preserves_trained_model_order():
    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)

    assert catalog.class_names == (
        "freshapples",
        "freshbanana",
        "freshoranges",
        "freshmango",
        "freshtomato",
        "freshpear",
        "rottenapples",
        "rottenbanana",
        "rottenoranges",
        "rottenmango",
        "rottentomato",
        "rottenpear",
    )
    assert catalog.display_name_for_label("rottenbanana") == "Rotten Banana"


def test_new_fruit_can_be_defined_without_code_changes(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(_catalog_payload("apple", "mango")), encoding="utf-8")

    catalog = load_fruit_catalog(str(path))

    assert catalog.class_names[-2:] == ("fresh_mango", "rotten_mango")
    assert catalog.display_name_for_label("fresh_mango") == "Fresh Mango"
    assert catalog.fruit_for_label("fresh_mango").fresh_storage_advice == (
        "Configured storage for mango."
    )


def test_catalog_rejects_duplicate_class_labels():
    payload = _catalog_payload("apple")
    payload["classes"].append(payload["classes"][0].copy())

    with pytest.raises(FruitCatalogError, match="Duplicate class label"):
        parse_fruit_catalog(payload)


def test_catalog_requires_fresh_and_rotten_class_for_every_fruit():
    payload = _catalog_payload("apple")
    payload["classes"] = payload["classes"][:1]

    with pytest.raises(FruitCatalogError, match="exactly one fresh class and one rotten"):
        parse_fruit_catalog(payload)
