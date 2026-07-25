import tempfile
import unittest
from pathlib import Path

from build_catalog import build_catalog, search_key, stable_id


class CatalogTests(unittest.TestCase):
    def test_search_key_removes_accents_without_losing_words(self):
        self.assertEqual(search_key("BOA_NOITE"), "BOA_NOITE")
        self.assertEqual(search_key("AÇÃO"), "ACAO")

    def test_stable_id_is_deterministic(self):
        self.assertEqual(stable_id("BOM"), stable_id("BOM"))
        self.assertEqual(len(stable_id("BOM")), 16)

    def test_catalog_merges_platform_variants(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for platform in ("ANDROID", "IOS"):
                directory = root / "vlibras-translate" / "bundles" / platform
                directory.mkdir(parents=True)
                (directory / "BOA_NOITE").write_bytes(b"UnityFS")

            catalog = build_catalog(root)

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]["platforms"], ["android", "ios"])
        self.assertTrue(catalog[0]["is_compound"])


if __name__ == "__main__":
    unittest.main()
