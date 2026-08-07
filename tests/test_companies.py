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
        "alicesoft",
        "keroq",
        "makura",
        "cabbagesoft",
    }
    assert set(companies.COMPANIES) == expected


def test_waifu_pool_keys_cover_requested_companies() -> None:
    pool = companies.WAIFU_POOL_KEYS
    assert "yuzusoft" in pool
    assert "key" in pool
    assert "august" in pool
    assert "alicesoft" in pool
    assert "aquaplusleaf" in pool
    assert "frontwing" in pool
    assert "palette" in pool
    assert "sagaplanets" in pool
    assert "favorite" in pool
    assert "purplesoftware" in pool
    assert "navel" in pool
    assert "circus" in pool
    assert "keroq" in pool
    assert "makura" in pool
    assert "cabbagesoft" in pool


def test_catalog_includes_subsidiary_search_names() -> None:
    assert "Yuzusoft SOUR" in companies.COMPANIES["yuzusoft"]["search"]
    assert "SMEE" in companies.COMPANIES["hooksoft"]["search"]
    assert "CUBE" in companies.COMPANIES["cuffs"]["search"]
    assert "Lime" in companies.COMPANIES["navel"]["search"]


def test_display_names_joins_selected_keys() -> None:
    text = companies.display_names(["yuzusoft", "smee"])
    assert "Yuzusoft（柚子社）" in text
    assert "SMEE" in text
