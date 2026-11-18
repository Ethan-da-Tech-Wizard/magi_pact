# Program: magi_pact - dedup.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Normalized prompt deduplication, policy leak scanning and the multi-check training gate for datasets.

"""Normalized Prompt Deduplication, Policy Leak Scanner, and Training Gate Engine.

Ensures cross-box multi-language and hardware compiled datasets have:
1. Zero duplicate prompts (normalized deduplication via task ID stripping, digit normalisation, skeleton structure hashing).
2. Strict 0% policy leak (zero credentials, zero private fleet identity leaks, zero destructive payloads in chosen responses).
3. Clean verification against the multi-point Training Gate.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Any, Set

# Regex patterns for stripping task ID tags
TASK_ID_PATTERNS = [
    re.compile(r"\[TASK-[0-9a-zA-Z_-]+\]", re.IGNORECASE),
    re.compile(r"\[ID:\s*[0-9a-zA-Z_-]+\]", re.IGNORECASE),
    re.compile(r"\[TWU_GOLD_[0-9a-zA-Z_-]+\]", re.IGNORECASE),
    re.compile(r"\[SEAT-[0-9]+\]", re.IGNORECASE),
    re.compile(r"Task\s*#?\d+\s*:\s*", re.IGNORECASE),
    re.compile(r"ID:\s*TWU_GOLD_[A-Z_]+_\d+\s*[-:]?\s*", re.IGNORECASE),
    re.compile(r"<task_id>[^<]+</task_id>", re.IGNORECASE),
    re.compile(r"^#\s*TASK:\s*.*$", re.MULTILINE | re.IGNORECASE),
]

# Regex patterns for policy leak detection
CREDENTIAL_PATTERNS = {
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "anthropic-key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{30,}"),
    "openai-key": re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{40,}"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{20,}"),
    "stripe-live-key": re.compile(r"\b[sr]k_live_[0-9A-Za-z]{20,}"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    "wireguard-private-key": re.compile(r"(?i)\bPrivateKey\s*=\s*([A-Za-z0-9+/]{43}=)"),
}

# Real private hostnames and hardware identifiers to block (0% leak tolerance)
PRIVATE_HOSTS = {
    "internal-node-01",
    "workstation-macbook",
    "internal-node-03",
    "internal-node-04",
    "internal-node-05",
    "internal-node-06",
    "internal-node-07",
}

MAC_RX = re.compile(r"(?<![0-9A-Fa-f:-])(?:[0-9A-Fa-f]{2}([:-]))(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:-])")
MAC_IGNORE = re.compile(r"(?i)^(?:00[:-]00[:-]00[:-]00[:-]00[:-]00|ff[:-]ff[:-]ff[:-]ff[:-]ff[:-]ff)$")
LOCAL_HOST_RX = re.compile(r"(?i)\b[a-z0-9][a-z0-9-]{1,40}\.local\b")
LOCAL_HOST_ALLOWED = {"localhost.local"}

# Dangerous / destructive commands that must never be presented as chosen positive training targets
DESTRUCTIVE_CHOSEN_PATTERNS = {
    "wipe-root": re.compile(r"rm\s+-rf\s+(/|/\*)\b"),
    "wipe-nvram-efivars": re.compile(r"rm\s+-rf\s+/sys/firmware/efi/efivars"),
    "fork-bomb": re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),
    "force-push-trunk": re.compile(r"git\s+push\s+--force\s+origin\s+main\b"),
    "disable-sip": re.compile(r"\bcsrutil\s+disable\b"),
    "disable-gatekeeper": re.compile(r"\bspctl\s+--master-disable\b"),
    "reverse-shell": re.compile(r"/bin/(?:ba)?sh\s+-i\s+>&?\s+/dev/tcp/"),
}


def normalize_prompt(prompt: str) -> str:
    """Performs normalized deduplication transformation on a prompt.
    
    1. Strips task ID tags and metadata prefixes.
    2. Performs digit normalisation (replacing digits with <NUM>).
    3. Normalizes whitespace and case.
    """
    text = prompt.strip()
    
    # 1. Strip task ID tags
    for pat in TASK_ID_PATTERNS:
        text = pat.sub("", text).strip()
        
    # 2. Digit normalisation (tokens of digits replaced with <NUM>)
    text = re.sub(r"\b\d+\b", "<NUM>", text)
    
    # 3. Collapse multiple whitespace and normalize case
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def skeleton_structure_hash(text: str) -> str:
    """Computes a structural skeleton hash of prompt or code.
    
    Strips comments, code fence markers, punctuation, and returns
    a SHA-256 hash of the normalized structural essence.
    """
    # Remove markdown code fences
    cleaned = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", text)
    cleaned = cleaned.replace("```", "")
    
    # Remove line comments (#, //, --)
    cleaned = re.sub(r"(#|//|--).*?$", "", cleaned, flags=re.MULTILINE)
    
    # Remove block comments (/* ... */)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    
    # Normalize digits
    cleaned = re.sub(r"\b\d+\b", "<NUM>", cleaned)
    
    # Remove punctuation
    cleaned = re.sub(r"[^\w\s<>]", "", cleaned)
    
    # Normalize whitespace & lowercase
    normalized = re.sub(r"\s+", " ", cleaned).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_prompt_fingerprint(prompt: str) -> Dict[str, str]:
    """Generates a complete fingerprint dict for prompt duplication analysis."""
    norm = normalize_prompt(prompt)
    return {
        "raw_sha256": hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest(),
        "normalized_text": norm,
        "normalized_sha256": hashlib.sha256(norm.encode("utf-8")).hexdigest(),
        "skeleton_sha256": skeleton_structure_hash(prompt),
    }


class PolicyLeakScanner:
    """Scans dataset records with zero-tolerance policy leak rules."""
    
    def __init__(self, private_hosts: Optional[Set[str]] = None):
        """Store the set of private host names to flag, defaulting to the module-level list."""
        self.private_hosts = set(private_hosts or PRIVATE_HOSTS)
        
    def scan_text(self, text: str, field_name: str, is_chosen: bool = False) -> List[Dict[str, Any]]:
        """Scan one text field for credentials, private identity, filesystem path and destructive-payload patterns and return a list of findings."""
        findings = []
        
        # 1. Check for real credentials
        for kind, rx in CREDENTIAL_PATTERNS.items():
            for m in rx.finditer(text):
                findings.append({
                    "field": field_name,
                    "type": f"credential:{kind}",
                    "match": m.group(0)[:12] + "...",
                    "fingerprint": hashlib.sha256(m.group(0).encode("utf-8")).hexdigest()[:10],
                    "severity": "CRITICAL",
                })
                
        # 2. Check for MAC addresses
        for m in MAC_RX.finditer(text):
            mac = m.group(0)
            if not MAC_IGNORE.match(mac):
                findings.append({
                    "field": field_name,
                    "type": "identity:mac_address",
                    "match": mac,
                    "fingerprint": hashlib.sha256(mac.lower().encode("utf-8")).hexdigest()[:10],
                    "severity": "CRITICAL",
                })
                
        # 3. Check for .local private hostnames
        for m in LOCAL_HOST_RX.finditer(text):
            h = m.group(0).lower()
            if h not in LOCAL_HOST_ALLOWED:
                findings.append({
                    "field": field_name,
                    "type": "identity:local_hostname",
                    "match": h,
                    "fingerprint": hashlib.sha256(h.encode("utf-8")).hexdigest()[:10],
                    "severity": "CRITICAL",
                })
                
        # 4. Check for fleet private hostnames
        low = text.lower()
        for host in self.private_hosts:
            if re.search(r"\b" + re.escape(host) + r"\b", low):
                findings.append({
                    "field": field_name,
                    "type": "identity:private_fleet_host",
                    "match": host,
                    "fingerprint": hashlib.sha256(host.encode("utf-8")).hexdigest()[:10],
                    "severity": "CRITICAL",
                })
                
        # 5. Check for destructive payloads in chosen responses
        if is_chosen:
            for kind, rx in DESTRUCTIVE_CHOSEN_PATTERNS.items():
                m = rx.search(text)
                if m:
                    findings.append({
                        "field": field_name,
                        "type": f"policy:destructive_chosen_{kind}",
                        "match": m.group(0),
                        "fingerprint": hashlib.sha256(m.group(0).encode("utf-8")).hexdigest()[:10],
                        "severity": "CRITICAL",
                    })
                    
        return findings

    def scan_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scans a single training pair for policy leaks."""
        findings = []
        # Scan prompt
        if "prompt" in record:
            findings.extend(self.scan_text(record["prompt"], "prompt", is_chosen=False))
            
        # Scan chosen response (strict destructive check)
        if "chosen" in record:
            findings.extend(self.scan_text(record["chosen"], "chosen", is_chosen=True))
            
        # Scan rejected response (credentials / identity only, not destructive since rejected demonstrates bad behavior)
        if "rejected" in record:
            findings.extend(self.scan_text(record["rejected"], "rejected", is_chosen=False))
            
        return findings

    def scan_dataset(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Scans an entire dataset collection and returns comprehensive audit."""
        all_findings = []
        records_with_findings = 0
        
        for idx, rec in enumerate(records):
            f = self.scan_record(rec)
            if f:
                records_with_findings += 1
                for item in f:
                    item["record_id"] = rec.get("id", f"row_{idx}")
                    all_findings.append(item)
                    
        leak_rate = (records_with_findings / len(records)) if records else 0.0
        return {
            "total_records_scanned": len(records),
            "records_with_leaks": records_with_findings,
            "leak_count": len(all_findings),
            "policy_leak_rate": leak_rate,
            "leak_free": (len(all_findings) == 0),
            "findings": all_findings,
        }


def deduplicate_dataset(
    records: List[Dict[str, Any]],
    scanner: Optional[PolicyLeakScanner] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Performs normalized deduplication and content-hash deduplication across records.
    
    1. Exact content hash deduplication: domain + prompt + chosen SHA-256.
    2. Normalized prompt skeleton deduplication: prevents prompt repetition across
       task variations, digit swaps, and ID tag formatting.
    3. Guarantees 0 duplicate prompts and 100% unique prompt ratio.
    """
    if scanner is None:
        scanner = PolicyLeakScanner()
        
    seen_content_hashes: Set[str] = set()
    seen_skeleton_hashes: Set[str] = set()
    seen_normalized_prompts: Set[str] = set()
    
    deduped_records: List[Dict[str, Any]] = []
    dropped_records: List[Dict[str, Any]] = []
    
    for idx, rec in enumerate(records):
        prompt = rec.get("prompt", "")
        chosen = rec.get("chosen", "")
        domain = rec.get("domain", "")
        rec_id = rec.get("id", f"rec_{idx}")
        
        # 1. Exact content hash
        content_key = f"{domain}:{prompt}:{chosen}"
        c_hash = hashlib.sha256(content_key.encode("utf-8")).hexdigest()
        if c_hash in seen_content_hashes:
            dropped_records.append({
                "id": rec_id,
                "reason": "exact_content_duplicate",
                "content_hash": c_hash,
            })
            continue
            
        # 2. Normalized prompt & skeleton hash
        norm_prompt = normalize_prompt(prompt)
        skel_hash = skeleton_structure_hash(prompt)
        
        if norm_prompt in seen_normalized_prompts or skel_hash in seen_skeleton_hashes:
            dropped_records.append({
                "id": rec_id,
                "reason": "normalized_prompt_skeleton_duplicate",
                "normalized_prompt": norm_prompt[:60] + "...",
                "skeleton_hash": skel_hash,
            })
            continue
            
        seen_content_hashes.add(c_hash)
        seen_normalized_prompts.add(norm_prompt)
        seen_skeleton_hashes.add(skel_hash)
        deduped_records.append(rec)
        
    raw_count = len(records)
    deduped_count = len(deduped_records)
    dropped_count = len(dropped_records)
    unique_ratio = (deduped_count / raw_count) if raw_count > 0 else 1.0
    
    metrics = {
        "raw_record_count": raw_count,
        "deduplicated_record_count": deduped_count,
        "duplicates_removed": dropped_count,
        "unique_prompt_ratio": 1.0 if deduped_count > 0 else 0.0,
        "input_unique_prompt_ratio": round(unique_ratio, 4),
        "dropped_details": dropped_records,
    }
    return deduped_records, metrics


@dataclass
class TrainingGateResult:
    """Outcome of the training gate: overall pass flag, per-check results and any violations found."""
    passed: bool
    status: str  # "PASSED" | "FAILED"
    gate_checks: Dict[str, bool]
    metrics: Dict[str, Any]
    violations: List[str]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Return the result as a plain dictionary."""
        return asdict(self)


class TrainingGate:
    """Strict Gatekeeper validating candidate datasets before training admission."""
    
    REQUIRED_FIELDS = ["id", "domain", "kind", "prompt", "chosen", "rejected", "quality", "capabilities", "created_at"]
    REQUIRED_DOMAINS = [
        "c_cpp", "csharp", "java", "rust", "typescript", "javascript",
        "ruby", "html_css", "bash_posix", "arch_linux", "fedora_linux",
        "bios_uefi", "git_internals", "mesh_protocol"
    ]
    
    def __init__(self, scanner: Optional[PolicyLeakScanner] = None):
        """Use the supplied leak scanner, or build a default one."""
        self.scanner = scanner or PolicyLeakScanner()
        
    def evaluate(
        self,
        records: List[Dict[str, Any]],
        manifest_checksum: Optional[str] = None,
        expected_checksum: Optional[str] = None,
    ) -> TrainingGateResult:
        """Run every training-gate check (leaks, duplicate prompts and content, schema, domain coverage, manifest checksum) over the records and return a TrainingGateResult."""
        violations: List[str] = []
        checks: Dict[str, bool] = {
            "policy_leak_gate": True,
            "zero_duplicate_prompts_gate": True,
            "zero_duplicate_content_gate": True,
            "schema_compliance_gate": True,
            "domain_coverage_gate": True,
            "checksum_manifest_gate": True,
        }
        
        # 1. Policy Leak Gate
        scan_res = self.scanner.scan_dataset(records)
        if not scan_res["leak_free"]:
            checks["policy_leak_gate"] = False
            for f in scan_res["findings"]:
                violations.append(f"Policy leak ({f['type']}) in {f['record_id']} [{f['field']}]: {f['match']}")
                
        # 2. Duplicate Check Gate
        seen_prompts: Set[str] = set()
        seen_skeletons: Set[str] = set()
        seen_content: Set[str] = set()
        
        dup_prompt_count = 0
        dup_content_count = 0
        
        for idx, rec in enumerate(records):
            p = rec.get("prompt", "")
            c = rec.get("chosen", "")
            d = rec.get("domain", "")
            
            c_hash = hashlib.sha256(f"{d}:{p}:{c}".encode("utf-8")).hexdigest()
            if c_hash in seen_content:
                dup_content_count += 1
            seen_content.add(c_hash)
            
            norm_p = normalize_prompt(p)
            skel_h = skeleton_structure_hash(p)
            if norm_p in seen_prompts or skel_h in seen_skeletons:
                dup_prompt_count += 1
            seen_prompts.add(norm_p)
            seen_skeletons.add(skel_h)
            
        if dup_content_count > 0:
            checks["zero_duplicate_content_gate"] = False
            violations.append(f"Found {dup_content_count} duplicate content records.")
            
        if dup_prompt_count > 0:
            checks["zero_duplicate_prompts_gate"] = False
            violations.append(f"Found {dup_prompt_count} duplicate normalized prompt skeletons.")
            
        # 3. Schema Compliance Gate
        for idx, rec in enumerate(records):
            rec_id = rec.get("id", f"row_{idx}")
            for field in self.REQUIRED_FIELDS:
                if field not in rec:
                    checks["schema_compliance_gate"] = False
                    violations.append(f"Missing required field '{field}' in record {rec_id}")
            if len(rec.get("prompt", "")) < 10:
                checks["schema_compliance_gate"] = False
                violations.append(f"Prompt too short (<10 chars) in {rec_id}")
            if len(rec.get("chosen", "")) < 10:
                checks["schema_compliance_gate"] = False
                violations.append(f"Chosen too short (<10 chars) in {rec_id}")
            if len(rec.get("rejected", "")) < 5:
                checks["schema_compliance_gate"] = False
                violations.append(f"Rejected too short (<5 chars) in {rec_id}")
            if not isinstance(rec.get("capabilities"), list) or len(rec.get("capabilities")) == 0:
                checks["schema_compliance_gate"] = False
                violations.append(f"Missing or empty capabilities list in {rec_id}")
                
        # 4. Domain Coverage Gate
        present_domains = {rec.get("domain") for rec in records if "domain" in rec}
        missing_domains = [d for d in self.REQUIRED_DOMAINS if d not in present_domains]
        if missing_domains:
            checks["domain_coverage_gate"] = False
            violations.append(f"Missing required training domains: {missing_domains}")
            
        # 5. Checksum Manifest Gate
        if manifest_checksum and expected_checksum:
            if manifest_checksum != expected_checksum:
                checks["checksum_manifest_gate"] = False
                violations.append(f"Checksum mismatch: manifest {manifest_checksum} != expected {expected_checksum}")
                
        passed = all(checks.values())
        status = "PASSED" if passed else "FAILED"
        now = datetime.now(timezone.utc).isoformat()
        
        metrics = {
            "total_records": len(records),
            "unique_prompts": len(seen_prompts),
            "unique_prompt_ratio": (len(seen_prompts) / len(records)) if records else 1.0,
            "policy_leak_rate": scan_res["policy_leak_rate"],
            "domains_covered": len(present_domains),
            "domains_present": sorted(list(present_domains)),
            "duplicate_content_count": dup_content_count,
            "duplicate_prompt_count": dup_prompt_count,
        }
        
        return TrainingGateResult(
            passed=passed,
            status=status,
            gate_checks=checks,
            metrics=metrics,
            violations=violations,
            timestamp=now,
        )
