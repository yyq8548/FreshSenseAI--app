from training.expanded_dataset import CLASS_ORDER, _assign_groups, _padded_box


def test_expanded_class_order_contains_six_fruits_and_states():
    assert len(CLASS_ORDER) == 12
    assert CLASS_ORDER[:6] == (
        "freshapples",
        "freshbanana",
        "freshoranges",
        "freshmango",
        "freshtomato",
        "freshpear",
    )
    assert CLASS_ORDER[-3:] == ("rottenmango", "rottentomato", "rottenpear")


def test_group_assignment_is_deterministic_and_complete():
    groups = [f"group-{index}" for index in range(100)]
    first = _assign_groups(groups, "seed")
    second = _assign_groups(reversed(groups), "seed")

    assert first == second
    assert set(first) == set(groups)
    assert set(first.values()) == {"train", "validation", "test"}


def test_padded_box_is_clamped_to_image_bounds():
    assert _padded_box([0, 0, 50, 50], 100, 100, 0.10) == (0, 0, 55, 55)
    assert _padded_box([10, 10, 1, 1], 100, 100, 0.10) is None
