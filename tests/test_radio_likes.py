import importlib.util
import tempfile
import unittest
from pathlib import Path


SERVER_PATH = Path(__file__).parents[1] / "backend" / "allmusic_server.py"
SPEC = importlib.util.spec_from_file_location("allmusic_server", SERVER_PATH)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class RadioLikesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        server.RADIO_FILE = str(Path(self.temp_dir.name) / "radio_state.json")
        self.client = server.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_like_is_counted_once_per_visitor_and_can_be_removed(self):
        payload = {
            "video_id": "abcdefghijk",
            "title": "Track One",
            "artist": "Artist",
            "voter_id": "visitor-1",
            "liked": True,
        }

        first = self.client.post("/radio/like", json=payload)
        duplicate = self.client.post("/radio/like", json=payload)
        ranked = self.client.get("/radio/now").get_json()["most_liked"]

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(ranked[0]["like_count"], 1)

        payload["liked"] = False
        removed = self.client.post("/radio/like", json=payload)
        ranked = self.client.get("/radio/now").get_json()["most_liked"]
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(ranked, [])

    def test_like_rejects_invalid_video_id_or_visitor(self):
        response = self.client.post(
            "/radio/like",
            json={"video_id": "not-valid", "voter_id": "", "liked": True},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
