"""CFB shortlex/simple-uppercase regressions, including full-uppercase expansions."""

import pytest

from filerepack.cfb_name_compare import cfb_name_key


@pytest.mark.parametrize(
    "lower,upper",
    [("abc", "ABC"), ("ёж", "ЁЖ"), ("é", "É"), ("ı", "I"), ("ᾀ", "ᾈ"), ("ᾳ", "ᾼ")],
)
def test_simple_uppercase_equivalence(lower, upper):
    assert cfb_name_key(lower) == cfb_name_key(upper)


@pytest.mark.parametrize("name", ["ß", "ﬃ", "ΐ", "ŉ"])
def test_expansions_without_simple_mapping_remain_unchanged(name):
    assert len(name.upper()) > 1
    assert cfb_name_key(name) == (2, (ord(name),))


def test_length_precedes_case_mapping_and_lexical_order():
    assert cfb_name_key("Z") < cfb_name_key("AA")
    assert cfb_name_key("ß") != cfb_name_key("SS")
    assert cfb_name_key("ß") != cfb_name_key("ẞ")
    assert cfb_name_key("T") < cfb_name_key("ß")
    assert cfb_name_key("ſ") == cfb_name_key("S")


def test_compare_utf16_units_without_uppercasing_surrogates():
    # Deseret lowercase/capital pairs have scalar uppercase mappings, but CFB
    # leaves each surrogate unit unchanged. Ordering also differs from scalar order.
    assert cfb_name_key("\U00010428") == (4, (0xD801, 0xDC28))
    assert cfb_name_key("\U00010428") != cfb_name_key("\U00010400")
    assert cfb_name_key("\ud801\udc28") == cfb_name_key("\U00010428")
    assert cfb_name_key("\U00010428") < cfb_name_key("\ue000A")


def test_names_are_not_unicode_normalized():
    assert cfb_name_key("é") != cfb_name_key("e\u0301")
