import unittest
from pathlib import Path


class ArtifactViewerTests(unittest.TestCase):
    def test_static_viewer_exposes_manifest_and_artifact_file_inputs(self):
        html = Path("frontend/artifact-viewer/index.html").read_text(encoding="utf-8")

        self.assertIn('id="manifestFile"', html)
        self.assertIn('id="artifactFiles"', html)
        self.assertIn('id="artifactTable"', html)
        self.assertIn('id="recommendationList"', html)
        self.assertIn('id="timeline"', html)
        self.assertNotIn("landing", html.casefold())

    def test_viewer_script_parses_jsonl_and_renders_manifest_artifacts(self):
        script = Path("frontend/artifact-viewer/viewer.js").read_text(encoding="utf-8")

        self.assertIn("function parseJsonl", script)
        self.assertIn("function renderManifest", script)
        self.assertIn("function renderRecommendations", script)
        self.assertIn("function renderTimeline", script)
        self.assertIn("safeCount(event.candidate_count)", script)
        self.assertIn("function safeCount", script)


if __name__ == "__main__":
    unittest.main()
