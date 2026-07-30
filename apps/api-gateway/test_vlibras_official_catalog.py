from routers import vlibras_reference


def test_builds_complete_catalog_from_official_trie():
    payload = {
        "root": {
            "children": {
                "A": {
                    "end": True,
                    "children": {
                        "J": {
                            "end": False,
                            "children": {
                                "U": {
                                    "end": False,
                                    "children": {
                                        "D": {
                                            "end": False,
                                            "children": {
                                                "A": {
                                                    "end": True,
                                                    "children": {},
                                                }
                                            },
                                        }
                                    },
                                }
                            },
                        }
                    },
                },
                "B": {
                    "end": False,
                    "children": {
                        "O": {
                            "end": False,
                            "children": {
                                "M": {
                                    "end": True,
                                    "children": {},
                                }
                            },
                        }
                    },
                },
            }
        }
    }

    catalog = vlibras_reference._catalog_from_official_dictionary(payload)

    assert catalog["source"] == "VLibras Official Dictionary"
    assert catalog["total"] == 3
    assert [sign["label"] for sign in catalog["signs"]] == [
        "A",
        "AJUDA",
        "BOM",
    ]
    assert all(sign["platforms"] == ["webgl"] for sign in catalog["signs"])
