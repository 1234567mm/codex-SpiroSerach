"""Tests for V32 frontend enhancements: Paper Diagnostics, Device Evidence, CSV records, loading state, sessionStorage, URL params, export."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


FIXTURE_DIR = Path("tests/fixtures/artifact_viewer/v32_paper_enhanced_run")


def _element_factory():
    elements = {}

    def element(id):
        if id not in elements:
            elements[id] = {
                "id": id,
                "textContent": "",
                "innerHTML": "",
                "style": {"display": ""},
                "classList": {"add": lambda *a: None, "remove": lambda *a: None},
                "addEventListener": lambda *a: None,
            }
        return elements[id]

    return element


class V32PaperDiagnosticsTests(unittest.TestCase):
    def _run_render_paper_diagnostics(self, fixture_dir=FIXTURE_DIR):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {id, textContent: "", innerHTML: "", style: {}, classList: {add: () => {}, remove: () => {}}, addEventListener: () => {}});
  }
  return elements.get(id);
}
const context = {
  console, JSON, Map, Set, Object, Array, String, Number, Error,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("frontend/artifact-viewer/viewer.js", "utf8"), context);
const manifest = JSON.parse(fs.readFileSync(process.argv[2] + "/run-manifest.json", "utf8"));
const artifacts = {};
for (const meta of manifest.artifacts) {
  const p = process.argv[2] + "/" + meta.path;
  const text = fs.readFileSync(p, "utf8");
  artifacts[meta.kind] = meta.format === "jsonl" ? text.split(/\r?\n/).filter(Boolean).map(JSON.parse) : JSON.parse(text);
}
const artifactsJson = JSON.stringify(artifacts);
vm.runInContext(`state.artifacts = new Map(Object.entries(${artifactsJson}).map(([k, v]) => [k, v]));`, context);
context.renderPaperDiagnostics(
  artifacts["source_assets"],
  artifacts["literature_claims"],
  artifacts["paper_vault_summary"],
  {},
  artifacts["extraction_journal"]
);
process.stdout.write(JSON.stringify({
  html: element("paperDiagnosticsList").innerHTML,
  count: element("paperDiagnosticsCount").textContent,
  filterOptions: element("paperDoiFilter").innerHTML,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), str(fixture_dir)],
                check=True, capture_output=True, text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        return json.loads(result.stdout)

    def test_paper_diagnostics_groups_by_doi(self):
        observed = self._run_render_paper_diagnostics()
        self.assertIn("3 source assets / 6 claims", observed["count"])
        self.assertIn("paper-doi-group", observed["html"])
        self.assertIn("10.1234/example.a", observed["html"])
        self.assertIn("10.1234/example.b", observed["html"])

    def test_paper_diagnostics_filter_options_populated(self):
        observed = self._run_render_paper_diagnostics()
        self.assertIn("10.1234/example.a", observed["filterOptions"])
        self.assertIn("10.1234/example.b", observed["filterOptions"])

    def test_paper_diagnostics_escapes_raw_span(self):
        observed = self._run_render_paper_diagnostics()
        self.assertIn("&lt;script&gt;alert(&#039;xss&#039;)&lt;/script&gt;", observed["html"])
        self.assertNotIn("<script>alert('xss')</script>", observed["html"])


class V32LoadingStateTests(unittest.TestCase):
    def test_loading_overlay_and_export_buttons_exist(self):
        html = Path("frontend/artifact-viewer/index.html").read_text(encoding="utf-8")
        self.assertIn('id="loadingState"', html)
        self.assertIn('id="errorPanel"', html)
        self.assertIn('id="exportSnapshot"', html)
        self.assertIn('id="printView"', html)


class V32SchemaTests(unittest.TestCase):
    def test_external_dataset_records_kind_registered(self):
        schema = json.loads(Path("schemas/run-artifact.schema.json").read_text(encoding="utf-8"))
        kinds = schema["properties"]["kind"]["enum"]
        self.assertIn("external_dataset_records", kinds)

    def test_external_dataset_records_schema_exists(self):
        self.assertTrue(Path("schemas/external-dataset-records.schema.json").exists())


class V32ResponsiveTests(unittest.TestCase):
    def test_multiple_breakpoints_exist(self):
        css = Path("frontend/artifact-viewer/styles.css").read_text(encoding="utf-8")
        for width in ("1200px", "960px", "640px", "414px"):
            self.assertIn(f"max-width: {width}", css)


class V32SessionStorageTests(unittest.TestCase):
    def test_run_data_store_has_commit_and_restore(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for run-data-store test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {
  console, JSON, Map, Set, Object, Array, String, Number, Error,
  sessionStorage: {getItem: () => null, setItem: () => {}, removeItem: () => {}},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("frontend/artifact-viewer/run-data-store.js", "utf8"), context);
const result = context.SpiroRunData.RunDataStore.commit({manifest: {run_id: "test"}, artifacts: {}});
process.stdout.write(JSON.stringify({hasCommit: typeof result === "object"}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path)],
                check=True, capture_output=True, text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        observed = json.loads(result.stdout)
        self.assertTrue(observed["hasCommit"])


if __name__ == "__main__":
    unittest.main()
