"""Unit tests for LoRA Dataset Splitter, Qwen3.5 ChatML Formatter, and Loss Masking."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pact.splits import (
    DatasetSplitter,
    QwenChatMLFormatter,
    DEFAULT_SYSTEM_PROMPT,
    IM_START,
    IM_END,
)


class TestDatasetSplits(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.corpus_path = self.root_dir / "exchange" / "consolidated" / "golden_master_corpus.jsonl"
        self.splitter = DatasetSplitter(root_dir=self.root_dir)

    def test_qwen_chatml_sft_formatter(self):
        record = {
            "id": "TEST_SFT_01",
            "prompt": "Write a thread-safe counter in C.",
            "completion": "int counter = 0;\npthread_mutex_t lock;",
            "kind": "sft",
            "domain": "c",
        }
        res = QwenChatMLFormatter.format_sft_record(record)
        self.assertIn("text", res)
        self.assertIn("messages", res)
        self.assertIn("loss_mask_metadata", res)

        # Check special tokens
        text = res["text"]
        self.assertTrue(text.startswith(f"{IM_START}system\n"))
        self.assertIn(f"{IM_START}user\nWrite a thread-safe counter in C.{IM_END}\n", text)
        self.assertIn(f"{IM_START}assistant\nint counter = 0;\npthread_mutex_t lock;{IM_END}", text)

        # Check messages loss flags
        msgs = res["messages"]
        self.assertEqual(len(msgs), 3)
        self.assertFalse(msgs[0]["loss"])
        self.assertFalse(msgs[1]["loss"])
        self.assertTrue(msgs[2]["loss"])

        # Check assistant span
        meta = res["loss_mask_metadata"]
        self.assertTrue(meta["assistant_only_loss"])
        spans = meta["assistant_spans"]
        self.assertEqual(len(spans), 1)
        s, e = spans[0]["start"], spans[0]["end"]
        self.assertEqual(text[s:e], f"int counter = 0;\npthread_mutex_t lock;{IM_END}")

    def test_qwen_chatml_dpo_formatter(self):
        record = {
            "id": "TEST_DPO_01",
            "prompt": "Safely increment shared state in Go.",
            "chosen": "atomic.AddInt64(&state, 1)",
            "rejected": "state++",
            "kind": "dpo",
            "domain": "go",
        }
        res = QwenChatMLFormatter.format_dpo_record(record)
        self.assertIn("text_chosen", res)
        self.assertIn("text_rejected", res)
        self.assertIn("chosen_messages", res)
        self.assertIn("rejected_messages", res)

        meta = res["loss_mask_metadata"]
        self.assertTrue(meta["assistant_only_loss"])
        c_spans = meta["chosen_assistant_spans"]
        self.assertEqual(res["text_chosen"][c_spans[0]["start"]:c_spans[0]["end"]], f"atomic.AddInt64(&state, 1){IM_END}")
        r_spans = meta["rejected_assistant_spans"]
        self.assertEqual(res["text_rejected"][r_spans[0]["start"]:r_spans[0]["end"]], f"state++{IM_END}")

    def test_qwen_chatml_multiturn_formatter(self):
        record = {
            "id": "TEST_MULTI_01",
            "prompt": "Multi-turn task",
            "domain": "rust",
            "kind": "sft",
        }
        turns = [
            {"user": "Define threadpool struct", "assistant": "struct ThreadPool { workers: Vec<Worker> }"},
            {"user": "Implement Drop", "assistant": "impl Drop for ThreadPool { ... }"},
        ]
        res = QwenChatMLFormatter.format_multiturn_record(record, turns)
        self.assertEqual(res["num_turns"], 2)
        self.assertEqual(len(res["messages"]), 5)  # 1 system + 2 * (1 user + 1 asst)

        meta = res["loss_mask_metadata"]
        spans = meta["assistant_spans"]
        self.assertEqual(len(spans), 2)
        self.assertEqual(res["text"][spans[0]["start"]:spans[0]["end"]], f"struct ThreadPool {{ workers: Vec<Worker> }}{IM_END}")
        self.assertEqual(res["text"][spans[1]["start"]:spans[1]["end"]], f"impl Drop for ThreadPool {{ ... }}{IM_END}")

    def test_corpus_partition_and_splits_counts(self):
        records = self.splitter.load_corpus(self.corpus_path)
        self.assertEqual(len(records), 124)

        res = self.splitter.partition_records(records)
        self.assertEqual(res.total_records, 124)
        self.assertEqual(len(res.sft_train), 24)
        self.assertEqual(len(res.dpo_train), 68)
        self.assertEqual(len(res.dev), 19)
        self.assertEqual(len(res.eval_heldout), 13)

        # Sum of splits must be exactly 124
        total_split = len(res.sft_train) + len(res.dpo_train) + len(res.dev) + len(res.eval_heldout)
        self.assertEqual(total_split, 124)

        # Dev split ratio ~15%
        self.assertAlmostEqual(res.dev_ratio, 0.1532, places=3)
        self.assertTrue(0.14 <= res.dev_ratio <= 0.16)

    def test_task_family_domain_coverage(self):
        records = self.splitter.load_corpus(self.corpus_path)
        res = self.splitter.partition_records(records)

        expected_domains = {
            "c", "cpp", "csharp", "java", "rust", "go",
            "bash_posix", "arch_linux", "fedora_linux", "bios_uefi",
            "git_internals", "html_css", "typescript"
        }
        self.assertEqual(len(expected_domains), 13)

        # 100% domain coverage in dev split
        dev_domains = {r["domain"] for r in res.dev}
        self.assertEqual(dev_domains, expected_domains)

        # 100% domain coverage in eval_heldout split
        eval_domains = {r["domain"] for r in res.eval_heldout}
        self.assertEqual(eval_domains, expected_domains)

        # 100% domain coverage in training overall
        train_domains = {r["domain"] for r in res.sft_train} | {r["domain"] for r in res.dpo_train}
        self.assertEqual(train_domains, expected_domains)

    def test_zero_cross_split_contamination(self):
        records = self.splitter.load_corpus(self.corpus_path)
        res = self.splitter.partition_records(records)

        train_prompts = {r["prompt"].strip() for r in res.sft_train} | {r["prompt"].strip() for r in res.dpo_train}
        dev_prompts = {r["prompt"].strip() for r in res.dev}
        eval_prompts = {r["prompt"].strip() for r in res.eval_heldout}

        # Prompt overlap assertions
        self.assertEqual(len(train_prompts & dev_prompts), 0, "Train and Dev prompts must have 0 overlap")
        self.assertEqual(len(train_prompts & eval_prompts), 0, "Train and Eval prompts must have 0 overlap")
        self.assertEqual(len(dev_prompts & eval_prompts), 0, "Dev and Eval prompts must have 0 overlap")

        # ID disjointness
        train_ids = {r["id"] for r in res.sft_train} | {r["id"] for r in res.dpo_train}
        dev_ids = {r["id"] for r in res.dev}
        eval_ids = {r["id"] for r in res.eval_heldout}

        self.assertEqual(len(train_ids & dev_ids), 0)
        self.assertEqual(len(train_ids & eval_ids), 0)
        self.assertEqual(len(dev_ids & eval_ids), 0)

    def test_export_splits_and_checksum_verification(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            records = self.splitter.load_corpus(self.corpus_path)
            res = self.splitter.partition_records(records)
            checksums = self.splitter.write_splits(res, output_dir=out_path)

            for split_file in ["sft_train.jsonl", "dpo_train.jsonl", "dev.jsonl", "eval_heldout.jsonl", "split_manifest.json", "CHECKSUMS.sha256"]:
                f = out_path / split_file
                self.assertTrue(f.exists(), f"File {split_file} must exist")
                self.assertGreater(f.stat().st_size, 0)

            # Verify checksums in CHECKSUMS.sha256
            chk_file = out_path / "CHECKSUMS.sha256"
            lines = chk_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 5)  # 4 jsonl files + split_manifest.json

            for line in lines:
                exp_sha, fname = line.split(None, 1)
                act_sha = hashlib.sha256((out_path / fname).read_bytes()).hexdigest()
                self.assertEqual(exp_sha, act_sha, f"Checksum mismatch for {fname}")

    def test_production_splits_exist_and_verified(self):
        datasets_dir = self.root_dir / "data" / "datasets"
        manifest_path = datasets_dir / "split_manifest.json"
        chk_path = datasets_dir / "CHECKSUMS.sha256"

        self.assertTrue(manifest_path.exists())
        self.assertTrue(chk_path.exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_split_rows"], 124)
        self.assertEqual(manifest["splits"]["sft_train"]["row_count"], 24)
        self.assertEqual(manifest["splits"]["dpo_train"]["row_count"], 68)
        self.assertEqual(manifest["splits"]["dev"]["row_count"], 19)
        self.assertEqual(manifest["splits"]["eval_heldout"]["row_count"], 13)
        self.assertTrue(manifest["cross_split_contamination"]["contamination_free"])

        # Check actual files match manifest
        for split_key, meta in manifest["splits"].items():
            fname = f"{split_key}.jsonl"
            file_path = datasets_dir / fname
            self.assertTrue(file_path.exists())
            act_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
            self.assertEqual(act_sha, meta["sha256"])


if __name__ == "__main__":
    unittest.main()
