import tempfile
import unittest
from pathlib import Path

from proxy_forge.storage.files import atomic_write_text
from proxy_forge.storage.paths import list_token_files, token_file_path


class StoragePathsTest(unittest.TestCase):
    def test_token_file_path_sanitizes_token_and_extension(self):
        path = token_file_path("/tmp/data", "Demo_Token", ".json")

        self.assertEqual(path, "/tmp/data/Demo_Token.json")

    def test_token_file_path_falls_back_for_unsafe_token(self):
        path = token_file_path("/tmp/data", "../Demo Token", ".json")

        self.assertEqual(path, "/tmp/data/default.json")

    def test_list_token_files_returns_sorted_sanitized_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "beta.json").write_text("{}", encoding="utf-8")
            (root / "alpha.json").write_text("{}", encoding="utf-8")
            (root / "ignore.txt").write_text("", encoding="utf-8")

            self.assertEqual(list_token_files(directory, "json"), ["alpha", "beta"])

    def test_list_token_files_missing_directory_returns_empty_list(self):
        self.assertEqual(list_token_files("/tmp/proxy-forge-missing-dir", "json"), [])

    def test_atomic_write_text_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "data.txt"

            atomic_write_text(str(path), "ok")

            self.assertEqual(path.read_text(encoding="utf-8"), "ok")


if __name__ == "__main__":
    unittest.main()
