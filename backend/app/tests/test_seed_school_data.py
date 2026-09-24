from scripts.seed_school_data import parse_class_name, slugify_username


def test_parse_class_name_dash_separated():
    assert parse_class_name("1-Blue") == (1, "Blue")
    assert parse_class_name("10huquq") == (10, "huquq")
    assert parse_class_name("8med rus") == (8, "med rus")
    assert parse_class_name("5B") == (5, "B")


def test_slugify_username_strips_apostrophes_and_spaces():
    assert slugify_username("Toshpo'latov Jaloliddin") == "toshpolatov.jaloliddin"
    assert slugify_username("Abdullayev R") == "abdullayev.r"
