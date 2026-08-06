"""会社名单测试。"""

from __future__ import annotations

from galgame_box import companies


def test_catalog_contains_expected_companies() -> None:
    expected = {
        "yuzusoft",
        "madosoft",
        "smee",
        "favorite",
        "purplesoftware",
        "key",
        "palette",
        "sagaplanets",
        "toneworks",
        "lumpofsugar",
        "asaproject",
        "whirlpool",
        "laplacian",
        "clochette",
        "august",
        "sprite",
        "navel",
        "frontwing",
        "typemoon",
        "aquaplusleaf",
        "nitroplus",
        "circus",
        "minatosoft",
        "nekoworks",
        "lose",
        "hooksoft",
        "cuffs",
        "azarashisoft",
    }
    assert set(companies.COMPANIES) == expected


def test_catalog_includes_subsidiary_search_names() -> None:
    assert "Yuzusoft SOUR" in companies.COMPANIES["yuzusoft"]["search"]
    assert "SMEE" in companies.COMPANIES["hooksoft"]["search"]
    assert "CUBE" in companies.COMPANIES["cuffs"]["search"]
    assert "Lime" in companies.COMPANIES["navel"]["search"]


def test_display_names_joins_selected_keys() -> None:
    text = companies.display_names(["yuzusoft", "smee"])
    assert "Yuzusoft（柚子社）" in text
    assert "SMEE" in text
