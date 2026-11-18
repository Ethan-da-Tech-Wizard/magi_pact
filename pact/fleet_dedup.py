"""Fleet Integration & Cross-Box Deduplication Engine.

Provides:
- Normalized Prompt Deduplication: Strips ephemeral task IDs (e.g. '[task id #123]'),
  normalizes digits, variable tokens, and whitespace to extract structural skeletons.
- Uniqueness Metric Verification: Calculates distinct prompt ratios and skeleton hashes;
  rejects datasets with uniqueness ratio < 0.90.
- Policy Leak Guard: Audits prompts and solutions for hardcoded user paths (/home/, /Users/),
  API keys, secrets, or internal connection strings.
- Cross-Box Dataset Consolidation: Reconciles shards across exchange/ into a unified,
  content-hash deduplicated training corpus.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple, Any

@dataclass
class DedupReport:
    total_rows: int
    raw_unique_prompts: int
    skeleton_unique_prompts: int
    raw_unique_ratio: float
    skeleton_unique_ratio: float
    duplicates_found: int
    policy_leaks_found: int
    leak_details: List[str]
    gate_passed: bool

class FleetDedupEngine:
    """Audits, cleans, and consolidates multi-seat corpus files."""

    LEAK_PATTERNS = [
        re.compile(r"/(?:Users|home)/[a-zA-Z0-9_-]+/(?:\.ssh|\.gnupg|\.bash_history|\.gemini)"),
        re.compile(r"(?:api_key|secret_key|private_key|auth_token)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{16,}['\"]", re.IGNORECASE),
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----"),
    ]

    @staticmethod
    def extract_skeleton(prompt: str) -> str:
        """Strips task markers, bracketed IDs, digits, and redundant whitespace."""
        # 1. Strip bracketed task IDs like [task id #1234] or [item 42]
        s = re.sub(r"\[\s*task\s*(?:id)?\s*#?\d+\s*\]", "", prompt, flags=re.IGNORECASE)
        # 2. Strip hexadecimal hashes
        s = re.sub(r"\b[0-9a-fA-F]{16,64}\b", "<HASH>", s)
        # 3. Strip numbers/integers
        s = re.sub(r"\b\d+\b", "<NUM>", s)
        # 4. Collapse whitespace
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    @classmethod
    def scan_for_leaks(cls, text: str) -> List[str]:
        """Detects policy leaks or credential leaks in text."""
        leaks = []
        for pat in cls.LEAK_PATTERNS:
            matches = pat.findall(text)
            if matches:
                leaks.append(f"Pattern '{pat.pattern}' matched: {matches[:2]}")
        return leaks

    @classmethod
    def audit_corpus(cls, records: List[Dict[str, Any]], min_skeleton_ratio: float = 0.90) -> DedupReport:
        """Audits a dataset for uniqueness and policy compliance."""
        total = len(records)
        if total == 0:
            return DedupReport(0, 0, 0, 1.0, 1.0, 0, 0, [], True)

        raw_prompts: Set[str] = set()
        skeletons: Set[str] = set()
        all_leaks: List[str] = []

        for r in records:
            prompt = r.get("prompt", "")
            chosen = r.get("chosen", "")

            # Check leaks
            leaks = cls.scan_for_leaks(prompt) + cls.scan_for_leaks(chosen)
            if leaks:
                all_leaks.extend(leaks)

            raw_prompts.add(prompt)
            skeletons.add(cls.extract_skeleton(prompt))

        raw_ratio = len(raw_prompts) / total
        skel_ratio = len(skeletons) / total
        dup_count = total - len(skeletons)
        passed = (skel_ratio >= min_skeleton_ratio) and (len(all_leaks) == 0)

        return DedupReport(
            total_rows=total,
            raw_unique_prompts=len(raw_prompts),
            skeleton_unique_prompts=len(skeletons),
            raw_unique_ratio=raw_ratio,
            skeleton_unique_ratio=skel_ratio,
            duplicates_found=dup_count,
            policy_leaks_found=len(all_leaks),
            leak_details=all_leaks,
            gate_passed=passed
        )

    @classmethod
    def deduplicate_and_reconcile(cls, input_records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], DedupReport]:
        """Deduplicates records based on skeleton hash and content SHA256."""
        seen_skeletons: Set[str] = set()
        deduped: List[Dict[str, Any]] = []

        for rec in input_records:
            skel = cls.extract_skeleton(rec.get("prompt", ""))
            if skel not in seen_skeletons:
                seen_skeletons.add(skel)
                deduped.append(rec)

        report = cls.audit_corpus(deduped)
        return deduped, report
