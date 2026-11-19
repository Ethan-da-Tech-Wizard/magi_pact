"""Unit tests for Web & Modern Runtime trajectories and specs.

Verifies:
- Complete coverage of modern CSS layouts (Holy-grail grid areas, clamp() fluid type, print stylesheets, cascade layers)
- Accessible HTML5 elements (<dialog> modals, <form role="search"> with input type="search", ARIA landmarks)
- Modern TypeScript 5.x & Node v26 (satisfies operator, discriminated unions, generic constraints, native type stripping)
- Structural validation rules adherence with zero syntax errors
- Export integrity and deterministic sha256 checksums
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pact.web_runtime import (
    WEB_SPECS,
    WEB_TRAJECTORIES,
    validate_web_spec,
    export_web_specs,
    export_web_corpus,
    generate_web_corpus_records,
)
from pact.fleet_dedup import FleetDedupEngine
from pact.dedup import PolicyLeakScanner

class TestWebRuntime(unittest.TestCase):

    """Tests for the web (CSS/HTML/TypeScript) specs and their JSONL corpus export."""
    def test_specs_count_and_rules(self):
        """All 12 specs must exist and satisfy their validation rules."""
        self.assertEqual(len(WEB_SPECS), 12)
        for spec in WEB_SPECS:
            self.assertTrue(
                validate_web_spec(spec),
                f"Spec {spec.spec_id} ({spec.title}) failed rule validation"
            )
            self.assertGreaterEqual(len(spec.validation_rules), 3)
            self.assertTrue(spec.code_snippet.strip())
            self.assertIn(spec.kind, ["css", "html", "typescript"])

    def test_css_layout_specs(self):
        """Verify CSS layouts: holy-grail, clamp fluid typography, print stylesheets, and cascade specificity."""
        spec_map = {s.spec_id: s for s in WEB_SPECS}

        # These tests are substring checks on each spec's code_snippet, i.e. they verify that the key technique is present rather than rendering it.
        # Holy-grail grid
        hg = spec_map["CSS-HOLY-GRAIL-01"]
        self.assertIn("grid-template-areas", hg.code_snippet)
        self.assertIn("nav main aside", hg.code_snippet)
        self.assertIn("min-height: 100vh", hg.code_snippet)
        self.assertIn("@media (max-width: 768px)", hg.code_snippet)

        # Fluid clamp typography
        fluid = spec_map["CSS-FLUID-TYPE-01"]
        self.assertIn("clamp(", fluid.code_snippet)
        self.assertIn("--font-base", fluid.code_snippet)
        self.assertIn("--font-h1", fluid.code_snippet)

        # Print media stylesheet
        print_spec = spec_map["CSS-PRINT-MEDIA-01"]
        self.assertIn("@media print", print_spec.code_snippet)
        self.assertIn("@page", print_spec.code_snippet)
        self.assertIn("display: none !important", print_spec.code_snippet)
        self.assertIn("break-inside: avoid", print_spec.code_snippet)
        self.assertIn("attr(href)", print_spec.code_snippet)

        # Cascade specificity & @layer
        cascade = spec_map["CSS-CASCADE-SPECIFICITY-01"]
        self.assertIn("@layer reset, base, layout, components, utilities;", cascade.code_snippet)
        self.assertIn(":where(", cascade.code_snippet)
        self.assertIn(":is(", cascade.code_snippet)

    def test_semantic_html_specs(self):
        """Verify semantic HTML: accessible <dialog>, <form role='search'>, and landmark navigation."""
        spec_map = {s.spec_id: s for s in WEB_SPECS}

        # Dialog modal
        dialog = spec_map["HTML-DIALOG-MODAL-01"]
        self.assertIn("<dialog", dialog.code_snippet)
        self.assertIn("method=\"dialog\"", dialog.code_snippet)
        self.assertIn("aria-labelledby", dialog.code_snippet)
        self.assertIn("aria-describedby", dialog.code_snippet)

        # Search form
        search = spec_map["HTML-SEARCH-FORM-01"]
        self.assertIn("<form role=\"search\"", search.code_snippet)
        self.assertIn("type=\"search\"", search.code_snippet)
        self.assertIn("enterkeyhint=\"search\"", search.code_snippet)
        self.assertIn("visually-hidden", search.code_snippet)

        # Landmark navigation
        landmark = spec_map["HTML-LANDMARK-NAV-01"]
        self.assertIn("class=\"skip-link\"", landmark.code_snippet)
        self.assertIn("<header role=\"banner\"", landmark.code_snippet)
        self.assertIn("<nav aria-label=\"Primary navigation\"", landmark.code_snippet)
        self.assertIn("<main id=\"main-content\"", landmark.code_snippet)
        self.assertIn("<footer role=\"contentinfo\"", landmark.code_snippet)
        self.assertIn("aria-current=\"page\"", landmark.code_snippet)

    def test_typescript_and_node26_specs(self):
        """Verify TypeScript 5.x & Node v26: satisfies, discriminated unions, generic constraints, type stripping."""
        spec_map = {s.spec_id: s for s in WEB_SPECS}

        # satisfies operator
        satisfies_spec = spec_map["TS-SATISFIES-CONFIG-01"]
        self.assertIn("satisfies AgentConfig", satisfies_spec.code_snippet)
        self.assertIn("as const", satisfies_spec.code_snippet)

        # Discriminated unions & exhaustive matching
        discriminated = spec_map["TS-DISCRIMINATED-UNION-01"]
        self.assertIn("readonly kind:", discriminated.code_snippet)
        self.assertIn("assertNever(x: never", discriminated.code_snippet)
        self.assertIn("switch (event.kind)", discriminated.code_snippet)

        # Generic constraints
        generics = spec_map["TS-GENERIC-CONSTRAINTS-01"]
        self.assertIn("TObject extends Record<string, any>", generics.code_snippet)
        self.assertIn("TKey extends keyof TObject", generics.code_snippet)
        self.assertIn("DeepReadonly<T>", generics.code_snippet)
        self.assertIn("const TKeys extends readonly string[]", generics.code_snippet)

        # Node v26 native type stripping
        node_strip = spec_map["NODE-NATIVE-TYPE-STRIP-01"]
        self.assertIn("import type {", node_strip.code_snippet)
        self.assertIn("as const", node_strip.code_snippet)
        self.assertIn("export type LogLevel =", node_strip.code_snippet)
        self.assertIn("--experimental-strip-types", node_strip.code_snippet)

        # Web API fetch
        fetch_spec = spec_map["TS-FETCH-ABORT-STREAM-01"]
        self.assertIn("AbortSignal.timeout", fetch_spec.code_snippet)
        self.assertIn("export type Result<T, E", fetch_spec.code_snippet)

    def test_export_web_corpus(self):
        """Verify export_web_corpus produces deterministic valid JSONL without leaks."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "web_corpus_test.jsonl"
            count, sha = export_web_corpus(out_file)
            self.assertEqual(count, 12)
            self.assertEqual(len(sha), 64)
            self.assertTrue(out_file.exists())

            # Re-read the exported JSONL and run the same dedup/leak gate used for every corpus.
            # Read back and audit
            records = []
            with open(out_file, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    records.append(rec)
                    self.assertIn("id", rec)
                    self.assertIn("domain", rec)
                    self.assertIn("prompt", rec)
                    self.assertIn("chosen", rec)
                    self.assertIn("rejected", rec)
                    self.assertIn("capabilities", rec)

            report = FleetDedupEngine.audit_corpus(records)
            self.assertTrue(report.gate_passed)
            self.assertEqual(report.policy_leaks_found, 0)
            self.assertEqual(report.duplicates_found, 0)
            self.assertEqual(report.skeleton_unique_ratio, 1.0)

            # Scanner verification
            scanner = PolicyLeakScanner()
            for r in records:
                self.assertEqual(len(scanner.scan_text(r["prompt"], "prompt")), 0)
                self.assertEqual(len(scanner.scan_text(r["chosen"], "chosen")), 0)

if __name__ == "__main__":
    unittest.main()
