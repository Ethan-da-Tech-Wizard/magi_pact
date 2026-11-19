# ==============================================================================
# Program: dataset.py
# Programmer: Ethan-da-Tech-Wizard
# Last Modified: November 18, 2026
# Purpose: Multi-language Golden Training Dataset & Non-Overwrite Sharding Engine.
#          Curates verified SFT/DPO pairs across systems domains (C, C++, Rust,
#          Bash, Linux, Git) and implements federated shard reconciliation
#          across the 32-seat mesh using cryptographic content hashing.
# ==============================================================================

"""Multi-language Golden Training Dataset & Non-Overwrite Sharding Engine.

================================================================================
DISTRIBUTED SYSTEMS EDUCATIONAL OVERVIEW: FEDERATED DATASET SHARDING
================================================================================
How Do Distributed Agents Build Training Datasets Without Collisions?
--------------------------------------------------------------------
In centralized AI data pipelines, workers push records into a central database.
However, in a decentralized, serverless P2P mesh (operating over Syncthing or
Git), concurrent writes to a shared dataset file cause merge conflicts, data
loss, and corrupt lines.

Magi Pact solves this through Sharded Exchange & Deterministic Reconciliation:
1. Isolated Seat Shards (`exchange/seat_XX_corpus.jsonl`):
   Each agent node (Seats 01-31) owns its dedicated shard in the `exchange/`
   directory. Because each seat only writes to its own filename, write collisions
   are mathematically impossible.
2. Cryptographic Content Hashing (SHA-256 Deduplication):
   During reconciliation (`reconcile_mesh_shards`), records from all peer shards
   are ingested. A deterministic hash is computed for each candidate record:
       hash = sha256(f"{domain}:{prompt}:{chosen}")
   Records with identical hashes are cleanly deduplicated, ensuring an idempotent,
   conflict-free master corpus without requiring a central coordinator.
3. Quality Certification:
   Every record is typed as a `TrainingPair`, marked with its domain, quality
   rating, capability tags, and UTC ISO-8601 generation timestamp.
"""

# ------------------------------------------------------------------------------
# Standard Library Imports
# ------------------------------------------------------------------------------
from dataclasses import dataclass, asdict  # Lightweight structured data container
from datetime import datetime, timezone   # Standardized UTC ISO-8601 timestamping
import hashlib                             # Cryptographic SHA-256 hashing for record deduplication
import json                                # JSON and JSONL serialization
import os                                  # Operating system utilities
from pathlib import Path                   # Filesystem path abstraction
from typing import Dict, List, Optional, Any  # Type hinting annotations

# ------------------------------------------------------------------------------
# Target Language and Systems Engineering Domains
# ------------------------------------------------------------------------------
# Standardized domain identifiers across the 14 core competency tracks
# The "domain" of every record must be one of these. dedup.TrainingGate has its own
# REQUIRED_DOMAINS list with the same 14 names; keep the two in sync.
DOMAINS = [
    "c_cpp",          # C99 / C++20 Systems Programming, Concurrency, and Memory Management
    "csharp",         # C# .NET Memory Streams, Tasks, and Concurrency
    "java",           # Java Modern Concurrency, Virtual Threads, and Non-blocking I/O
    "rust",           # Rust Memory Safety, Lifetimes, and Fearless Concurrency
    "typescript",     # TypeScript Strict Typing, Generics, and Async Workflows
    "javascript",     # Modern ECMAScript Event Loops, Promises, and Microtasks
    "ruby",           # Ruby Thread Pools, Ractors, and Metaprogramming
    "html_css",       # Modern Semantic HTML5, CSS Grid, and Flexbox Layouts
    "bash_posix",     # POSIX-compliant Shell Scripting, Traps, and Signal Handling
    "arch_linux",     # Arch Linux Packaging, Pacman, PKGBUILD, and Systemd Services
    "fedora_linux",   # leakguard:allow - Fedora / RHEL RPM Packaging, DNF, and SELinux Policies
    "bios_uefi",      # Low-level UEFI Firmware Protocols, NVRAM, and Boot Sequences
    "git_internals",  # Git DAG Internals, Objects, Trees, and Fast-Forward Merges
    "mesh_protocol",  # Magi Pact 32-Seat Consensus Protocols and Atomic Journaling
]


# ==============================================================================
# Training Pair Representation
# ==============================================================================

@dataclass
class TrainingPair:
    """Represents a validated Direct Preference Optimization (DPO) or SFT training pair.

    Attributes:
        id (str): Unique record identifier (e.g. 'TWU_GOLD_RUST_0003').
        domain (str): Target domain from DOMAINS.
        kind (str): Paradigm kind, typically 'dpo' (chosen vs rejected) or 'sft'.
        prompt (str): Detailed user prompt or task specification.
        chosen (str): Gold-standard, expert verified response/code.
        rejected (str): Plausible but flawed, unsafe, or sub-optimal alternative response.
        quality (str): Certification tier (e.g. 'gold_certified').
        capabilities (List[str]): Semantic tags describing competencies demonstrated.
        created_at (str): ISO-8601 UTC timestamp of creation.
    """
    # Field meanings are documented in the class docstring above. `sha256` below
    # deliberately omits id/created_at/rejected/quality, so two records with the same
    # domain+prompt+chosen are "the same record" regardless of when or by whom they were made.
    id: str
    domain: str
    kind: str  # "dpo" | "sft"
    prompt: str
    chosen: str
    rejected: str
    quality: str
    capabilities: List[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the dataclass instance into a standard Python dictionary."""
        return asdict(self)

    @property
    def sha256(self) -> str:
        """Computes the deterministic SHA-256 fingerprint of the record content."""
        content = f"{self.domain}:{self.prompt}:{self.chosen}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ==============================================================================
# Exemplar Library
# ==============================================================================
# Exemplar library establishing rigorous idiomatic standards across all target domains
# Each entry is a dict with domain, prompt, chosen (gold answer), rejected (plausible
# bad answer) and capabilities. The code/text inside the strings is training DATA,
# not executable project code, and must be kept byte-for-byte (it feeds record hashes).
# Entry order matters: generate_language_matrix() derives each record id from its index.
EXEMPLARS = [
    {
        # Teaches: pthread mutex + two condition variables, caller-supplied storage (no malloc), full init error unwinding. Rejected: unsynchronized, unbounded index.
        "domain": "c_cpp",
        "prompt": "Write a thread-safe circular ring buffer in C99 using POSIX mutex and condition variables with zero dynamic allocation after initialization.",
        "chosen": (
            "typedef struct {\n"
            "    uint8_t *buffer;\n"
            "    size_t capacity;\n"
            "    size_t head;\n"
            "    size_t tail;\n"
            "    size_t count;\n"
            "    pthread_mutex_t lock;\n"
            "    pthread_cond_t not_empty;\n"
            "    pthread_cond_t not_full;\n"
            "} ring_buffer_t;\n\n"
            "int ring_buffer_init(ring_buffer_t *rb, uint8_t *storage, size_t capacity) {\n"
            "    if (!rb || !storage || capacity == 0) return -1;\n"
            "    rb->buffer = storage;\n"
            "    rb->capacity = capacity;\n"
            "    rb->head = rb->tail = rb->count = 0;\n"
            "    if (pthread_mutex_init(&rb->lock, NULL) != 0) return -1;\n"
            "    if (pthread_cond_init(&rb->not_empty, NULL) != 0) {\n"
            "        pthread_mutex_destroy(&rb->lock);\n"
            "        return -1;\n"
            "    }\n"
            "    if (pthread_cond_init(&rb->not_full, NULL) != 0) {\n"
            "        pthread_cond_destroy(&rb->not_empty);\n"
            "        pthread_mutex_destroy(&rb->lock);\n"
            "        return -1;\n"
            "    }\n"
            "    return 0;\n"
            "}"
        ),
        "rejected": (
            "struct Buffer { int arr[100]; int h, t; };\n"
            "void push(struct Buffer *b, int x) { b->arr[b->h++] = x; } // Unsynchronized, buffer overflow"
        ),
        "capabilities": ["concurrency", "posix", "memory_safety"],
    },
    {
        # Teaches: bounded Channel<T> with Wait back-pressure and cancellation flowing through IAsyncEnumerable. Rejected: plain eager LINQ list, no streaming or cancellation.
        "domain": "csharp",
        "prompt": "Create a high-performance .NET 8 IAsyncEnumerable pipeline with Channel<T> bounding and cancellation token propagation.",
        "chosen": (
            "public sealed class EventPipeline<T>\n"
            "{\n"
            "    private readonly Channel<T> _channel;\n"
            "    public EventPipeline(int capacity = 1024)\n"
            "    {\n"
            "        var options = new BoundedChannelOptions(capacity)\n"
            "        {\n"
            "            FullMode = BoundedChannelFullMode.Wait,\n"
            "            SingleWriter = false,\n"
            "            SingleReader = false\n"
            "        };\n"
            "        _channel = Channel.CreateBounded<T>(options);\n"
            "    }\n"
            "    public async ValueTask PublishAsync(T item, CancellationToken ct = default)\n"
            "        => await _channel.Writer.WriteAsync(item, ct).ConfigureAwait(false);\n"
            "    public async IAsyncEnumerable<T> StreamAsync([EnumeratorCancellation] CancellationToken ct = default)\n"
            "    {\n"
            "        while (await _channel.Reader.WaitToReadAsync(ct).ConfigureAwait(false))\n"
            "        {\n"
            "            while (_channel.Reader.TryRead(out var item))\n"
            "                yield return item;\n"
            "        }\n"
            "    }\n"
            "}"
        ),
        "rejected": (
            "public List<T> Process(List<T> list) { return list.Where(x => x != null).ToList(); }"
        ),
        "capabilities": ["async", "channels", "dotnet8"],
    },
    {
        # Teaches: Arc-style refcount ordering (Relaxed increment, Release decrement, Acquire fence before free). Rejected: non-atomic counter.
        "domain": "rust",
        "prompt": "Implement an atomic, lock-free reference counter with relaxed fast-path and acquire/release synchronization in Rust.",
        "chosen": (
            "use std::sync::atomic::{AtomicUsize, Ordering};\n\n"
            "pub struct SharedNode<T> {\n"
            "    data: T,\n"
            "    refs: AtomicUsize,\n"
            "}\n\n"
            "impl<T> SharedNode<T> {\n"
            "    pub fn new(data: T) -> Self {\n"
            "        Self { data, refs: AtomicUsize::new(1) }\n"
            "    }\n"
            "    pub fn acquire(&self) {\n"
            "        self.refs.fetch_add(1, Ordering::Relaxed);\n"
            "    }\n"
            "    pub fn release(&self) -> bool {\n"
            "        if self.refs.fetch_sub(1, Ordering::Release) == 1 {\n"
            "            std::sync::atomic::fence(Ordering::Acquire);\n"
            "            true // Last reference dropped; trigger deallocation\n"
            "        } else {\n"
            "            false\n"
            "        }\n"
            "    }\n"
            "}"
        ),
        "rejected": (
            "pub struct Node { count: usize } // Not thread-safe, no atomics"
        ),
        "capabilities": ["lock_free", "atomics", "memory_model"],
    },
    {
        # Teaches: Java 21 StructuredTaskScope (fail-fast, timeout, no leaked subtasks). Rejected: unbounded raw platform threads.
        "domain": "java",
        "prompt": "Implement a high-throughput bounded worker pool using Java 21 Virtual Threads (Project Loom) with structured concurrency.",
        "chosen": (
            "import java.util.concurrent.*;\n\n"
            "public final class LoomWorkerPool {\n"
            "    public static <T> List<T> executeAll(List<Callable<T>> tasks, Duration timeout) throws Exception {\n"
            "        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {\n"
            "            var subtasks = tasks.stream()\n"
            "                .map(scope::fork)\n"
            "                .toList();\n"
            "            scope.joinUntil(Instant.now().plus(timeout));\n"
            "            scope.throwIfFailed();\n"
            "            return subtasks.stream().map(StructuredTaskScope.Subtask::get).toList();\n"
            "        }\n"
            "    }\n"
            "}"
        ),
        "rejected": (
            "for (Runnable r : tasks) { new Thread(r).start(); } // Spawns unbound platform threads"
        ),
        "capabilities": ["virtual_threads", "structured_concurrency", "java21"],
    },
    {
        # Teaches: a PKGBUILD that installs only into $pkgdir and builds a release binary. The sha256sums value is the well-known hash of empty input, i.e. a placeholder, not a real checksum.
        "domain": "arch_linux",
        "prompt": "Construct a compliant Arch Linux PKGBUILD for a native Rust binary package with reproducible LTO builds, checksums, and package() directories.",
        "chosen": (
            "# Maintainer: Node-01 <maintainer@magi-mesh.org>\n"
            "pkgname=magi-agent\n"
            "pkgver=1.0.0\n"
            "pkgrel=1\n"
            "pkgdesc=\"Sovereign autonomous multi-agent mesh coordinator\"\n"
            "arch=('x86_64' 'aarch64')\n"
            "url=\"https://github.com/magi-pact/magi_pact\"\n"
            "license=('MIT')\n"
            "depends=('gcc-libs')\n"
            "makedepends=('cargo')\n"
            "source=(\"$pkgname-$pkgver.tar.gz::$url/archive/v$pkgver.tar.gz\")\n"
            "sha256sums=('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')\n\n"
            "build() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    export RUSTFLAGS=\"-C opt-level=3 -C lto=thin\"\n"
            "    cargo build --frozen --release --all-features\n"
            "}\n\n"
            "package() {\n"
            "    cd \"$pkgname-$pkgver\"\n"
            "    install -Dm755 \"target/release/$pkgname\" \"$pkgdir/usr/bin/$pkgname\"\n"
            "    install -Dm644 LICENSE \"$pkgdir/usr/share/licenses/$pkgname/LICENSE\"\n"
            "}"
        ),
        "rejected": (
            "build() { cargo build; cp target/debug/app /usr/bin/app; } # Mutates host outside pkgdir, unoptimized"
        ),
        "capabilities": ["packaging", "arch", "pkgbuild", "cargo"],
    },
    {
        # Teaches: RPM spec with systemd scriptlet macros and buildroot-relative installs. Rejected: copying straight into the live filesystem.
        "domain": "fedora_linux",
        "prompt": "Write an RPM spec file with hardened compilation flags, systemd service installation, and SELinux context restoration for Fedora 40.",
        "chosen": (
            "Name:           magi-herder\n"
            "Version:        1.0.0\n"
            "Release:        1%{?dist}\n"
            "Summary:        Magi Pact Federated Herder Service\n"
            "License:        Proprietary\n"
            "Source0:        %{name}-%{version}.tar.gz\n"
            "BuildRequires:  python3-devel, systemd-rpm-macros\n"
            "Requires:       python3\n"
            "%{?systemd_requires}\n\n"
            "%description\n"
            "Production federated multi-agent concurrency manager.\n\n"
            "%install\n"
            "install -D -p -m 0644 systemd/magi-herder.service %{buildroot}%{_unitdir}/magi-herder.service\n"
            "install -D -p -m 0755 bin/herder %{buildroot}%{_bindir}/magi-herder\n\n"
            "%post\n"
            "%systemd_post magi-herder.service\n\n"
            "%preun\n"
            "%systemd_preun magi-herder.service\n\n"
            "%postun\n"
            "%systemd_postun_with_restart magi-herder.service\n\n"
            "%files\n"
            "%{_bindir}/magi-herder\n"
            "%{_unitdir}/magi-herder.service\n"
        ),
        "rejected": (
            "cp binary /bin/binary; echo done # Violates RPM buildroot constraints"
        ),
        "capabilities": ["packaging", "rpm", "fedora", "systemd"],
    },
    {
        # Teaches: read-only inspection, backup, then targeted efibootmgr edits. Rejected: wiping efivars, which the destructive-pattern scanner in dedup.py also flags.
        "domain": "bios_uefi",
        "prompt": "Show how to safely inspect, backup, and modify UEFI boot order using efibootmgr on a dual-boot Arch/Fedora system without corrupting NVRAM.",
        "chosen": (
            "# 1. Read existing boot entries non-destructively\n"
            "sudo efibootmgr -v\n\n"
            "# 2. Backup full NVRAM efivars state\n"
            "sudo cp -a /sys/firmware/efi/efivars /root/efivars_backup_$(date +%F)\n\n"
            "# 3. Add explicit Arch Linux entry with verified disk UUID and kernel params\n"
            "sudo efibootmgr --create \\\n"
            "    --disk /dev/nvme0n1 --part 1 \\\n"
            "    --label \"Arch Linux (Magi Node)\" \\\n"
            "    --loader /vmlinuz-linux \\\n"
            "    --unicode \"root=UUID=4f38a1c2-9e0a-428d-9321-eb36d934bb18 rw initrd=\\initramfs-linux.img quiet loglevel=3\"\n\n"
            "# 4. Safely set active boot priority order (e.g. 0001 Arch first, 0000 Fedora second)\n"
            "sudo efibootmgr --bootorder 0001,0000\n"
        ),
        "rejected": (
            "rm -rf /sys/firmware/efi/efivars/* # Bricks motherboards by deleting required firmware variables"
        ),
        "capabilities": ["uefi", "bootloader", "nvram", "kernel"],
    },
    {
        # Teaches: cherry-pick -x with signing and patch export for peer review. Rejected: force-pushing main (also caught by dedup.py destructive patterns).
        "domain": "git_internals",
        "prompt": "Resolve a divergent branch with interactive cherry-picking, preserving GPG signatures, and exporting clean patches for peer review.",
        "chosen": (
            "# 1. Ensure working directory is clean and isolated on a scoped topic branch\n"
            "git status --porcelain\n"
            "git checkout -b topic/patch-exchange main\n\n"
            "# 2. Replay specific commits with original author dates preserved\n"
            "git cherry-pick -x --gpg-sign 71fb1c2\n\n"
            "# 3. Export formatted patch receipt into exchange directory\n"
            "git format-patch -1 HEAD --output-directory=exchange/\n\n"
            "# 4. Verify patch applies cleanly without fuzzy hunk corruption\n"
            "git apply --check exchange/0001-*.patch\n"
        ),
        "rejected": (
            "git push --force origin main # Overwrites upstream history and destroys team commits"
        ),
        "capabilities": ["git", "patch_exchange", "gpg", "atomic_history"],
    },
    {
        # Teaches: building a typed envelope with pact.protocol.make_envelope instead of ad-hoc strings.
        "domain": "mesh_protocol",
        "prompt": "Demonstrate how the Magi CLI formats and signs an envelope to dispatch tasks across the 32-seat Magi Pact mesh.",
        "chosen": (
            "from pact.protocol import make_envelope, KIND_TASK_DISPATCH\n\n"
            "payload = {\n"
            "    'title': 'Compile Multi-Language Corpus',\n"
            "    'target_seat': 3,\n"
            "    'shards': ['c_cpp', 'rust', 'arch_linux'],\n"
            "    'output_path': 'exchange/seat_03_corpus.jsonl'\n"
            "}\n"
            "envelope = make_envelope(\n"
            "    from_seat=0,\n"
            "    to_seat=3,\n"
            "    kind=KIND_TASK_DISPATCH,\n"
            "    payload=payload\n"
            ")\n"
            "print(envelope.to_json())\n"
        ),
        "rejected": (
            "print('send task') # Untyped, unformatted string, drops correlation IDs"
        ),
        "capabilities": ["magi_mesh", "protocol", "envelope", "ipc"],
    },
    {
        # Teaches: discriminated unions with an exhaustive `never` check in the default branch.
        "domain": "typescript",
        "prompt": "Implement a compile-time validated state machine with exhaustive pattern matching and discriminated unions in TypeScript.",
        "chosen": (
            "type State =\n"
            "  | { status: 'idle' }\n"
            "  | { status: 'connecting'; host: string; attempts: number }\n"
            "  | { status: 'connected'; socketId: string }\n"
            "  | { status: 'failed'; error: Error };\n\n"
            "type Action =\n"
            "  | { type: 'CONNECT'; host: string }\n"
            "  | { type: 'SUCCESS'; socketId: string }\n"
            "  | { type: 'RETRY' }\n"
            "  | { type: 'FAIL'; error: Error };\n\n"
            "function transition(state: State, action: Action): State {\n"
            "  switch (state.status) {\n"
            "    case 'idle':\n"
            "      return action.type === 'CONNECT'\n"
            "        ? { status: 'connecting', host: action.host, attempts: 1 }\n"
            "        : state;\n"
            "    case 'connecting':\n"
            "      if (action.type === 'SUCCESS') return { status: 'connected', socketId: action.socketId };\n"
            "      if (action.type === 'RETRY') return { ...state, attempts: state.attempts + 1 };\n"
            "      if (action.type === 'FAIL') return { status: 'failed', error: action.error };\n"
            "      return state;\n"
            "    case 'connected':\n"
            "    case 'failed':\n"
            "      return state;\n"
            "    default:\n"
            "      const _exhaustive: never = state;\n"
            "      return _exhaustive;\n"
            "  }\n"
            "}"
        ),
        "rejected": (
            "function transition(s, a) { if (a == 'connect') s.status = 'connecting'; } // Any types, mutable bugs"
        ),
        "capabilities": ["types", "state_machine", "discriminated_unions"],
    },
    {
        # Teaches: dependency-free SSE with keep-alive pings and a padding comment to defeat proxy buffering. Rejected: pulling in a framework.
        "domain": "javascript",
        "prompt": "Create a zero-npm-dependency Node.js 24 Server-Sent Events (SSE) server with ping keep-alives and proxy buffer bypass headers.",
        "chosen": (
            "import http from 'node:http';\n\n"
            "export function startSseServer(port = 8080) {\n"
            "  const clients = new Set();\n"
            "  const server = http.createServer((req, res) => {\n"
            "    if (req.url === '/events') {\n"
            "      res.writeHead(200, {\n"
            "        'Content-Type': 'text/event-stream',\n"
            "        'Cache-Control': 'no-cache, no-store, no-transform',\n"
            "        'Connection': 'keep-alive',\n"
            "        'X-Accel-Buffering': 'no',\n"
            "      });\n"
            "      res.write(': ' + ' '.repeat(2048) + '\\n\\n'); // Flush reverse-proxy buffers\n"
            "      clients.add(res);\n"
            "      req.on('close', () => clients.delete(res));\n"
            "    }\n"
            "  });\n"
            "  const ping = setInterval(() => {\n"
            "    for (const res of clients) res.write(': ping\\n\\n');\n"
            "  }, 15000);\n"
            "  return server.listen(port);\n"
            "}"
        ),
        "rejected": (
            "import express from 'express'; // Pulls in 50 external npm dependencies for simple SSE"
        ),
        "capabilities": ["node24", "sse", "zero_dependency", "networking"],
    },
    {
        # Teaches: MonitorMixin + condition variable pool with a monotonic-clock deadline. Rejected: a global connection variable.
        "domain": "ruby",
        "prompt": "Implement a thread-safe connection pool with health check ping and automatic reconnection in modern Ruby 3.3.",
        "chosen": (
            "require 'monitor'\n"
            "require 'timeout'\n\n"
            "class ConnectionPool\n"
            "  include MonitorMixin\n\n"
            "  def initialize(size: 5, timeout: 3.0, &factory)\n"
            "    super()\n"
            "    @size = size\n"
            "    @timeout = timeout\n"
            "    @factory = factory\n"
            "    @available = []\n"
            "    @cond = new_cond\n"
            "    @size.times { @available << @factory.call }\n"
            "  end\n\n"
            "  def with_connection\n"
            "    conn = nil\n"
            "    synchronize do\n"
            "      deadline = Process.clock_gettime(Process::CLOCK_MONOTONIC) + @timeout\n"
            "      while @available.empty?\n"
            "        remaining = deadline - Process.clock_gettime(Process::CLOCK_MONOTONIC)\n"
            "        raise Timeout::Error, 'Pool connection timeout' if remaining <= 0\n"
            "        @cond.wait(remaining)\n"
            "      end\n"
            "      conn = @available.pop\n"
            "    end\n"
            "    yield conn\n"
            "  ensure\n"
            "    synchronize do\n"
            "      @available.push(conn) if conn\n"
            "      @cond.signal\n"
            "    end\n"
            "  end\n"
            "end"
        ),
        "rejected": (
            "class Pool; def get; $conn; end; end # Global state, race conditions"
        ),
        "capabilities": ["ruby3", "concurrency", "connection_pool", "monitor"],
    },
    {
        # Teaches: container queries, semantic landmarks and ARIA labelling, light-dark() theming. Rejected: inline handlers and deprecated <font>.
        "domain": "html_css",
        "prompt": "Create an accessible, modern, fluid component using CSS Container Queries and semantic HTML5.",
        "chosen": (
            "<article class=\"card-container\">\n"
            "  <div class=\"card\" role=\"region\" aria-labelledby=\"card-title\">\n"
            "    <header class=\"card-header\">\n"
            "      <h2 id=\"card-title\">Magi Task Shard</h2>\n"
            "      <span class=\"badge\" data-state=\"active\">Active</span>\n"
            "    </header>\n"
            "    <p class=\"card-body\">Autonomous coordination shard.</p>\n"
            "  </div>\n"
            "</article>\n"
            "<style>\n"
            "  .card-container {\n"
            "    container-type: inline-size;\n"
            "    container-name: card;\n"
            "  }\n"
            "  .card {\n"
            "    display: grid;\n"
            "    gap: clamp(0.5rem, 2cqw, 1.5rem);\n"
            "    padding: 1rem;\n"
            "    border-radius: 0.75rem;\n"
            "    background: light-dark(#ffffff, #121814);\n"
            "    color: light-dark(#111827, #f3f4f6);\n"
            "  }\n"
            "  @container card (min-width: 480px) {\n"
            "    .card { grid-template-columns: 1fr auto; align-items: center; }\n"
            "  }\n"
            "</style>"
        ),
        "rejected": (
            "<div onclick=\"alert('hi')\"><font size=4>Old non-semantic markup</font></div>"
        ),
        "capabilities": ["container_queries", "semantic_html", "a11y", "modern_css"],
    },
    {
        # Teaches: strict mode, trap-based cleanup, and atomic publish via temp file + mv. Rejected: in-place truncating write.
        "domain": "bash_posix",
        "prompt": "Write a robust, safe POSIX-compliant bash wrapper with exit traps, atomic replacement, and strict error handling.",
        "chosen": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "IFS=$'\\n\\t'\n\n"
            "TMP_DIR=\"$(mktemp -d 2>/dev/null || mktemp -d -t 'magi')\"\n"
            "cleanup() {\n"
            "    local exit_code=$?\n"
            "    rm -rf \"$TMP_DIR\"\n"
            "    exit \"$exit_code\"\n"
            "}\n"
            "trap cleanup EXIT INT TERM HUP\n\n"
            "TARGET_FILE=\"${1:-output.json}\"\n"
            "TEMP_PAYLOAD=\"$TMP_DIR/payload.tmp\"\n\n"
            "cat << 'EOF' > \"$TEMP_PAYLOAD\"\n"
            "{\"status\": \"certified\", \"node\": \"example-host-9\"}\n"
            "EOF\n\n"
            "# Atomic replacement via move: avoids partial reads by concurrent processes\n"
            "mv -f \"$TEMP_PAYLOAD\" \"$TARGET_FILE\"\n"
            "echo \"Published $TARGET_FILE atomically.\"\n"
        ),
        "rejected": (
            "echo data > file # Truncates file while readers are active, no cleanup traps"
        ),
        "capabilities": ["bash", "safe_scripting", "traps", "atomic_io"],
    },
]


# ==============================================================================
# Matrix Generation and Sharding Operations
# ==============================================================================

def generate_language_matrix() -> List[TrainingPair]:
    """Compiles the core verified dataset across all required language domains.

    Educational Note on Dataset Construction:
    -----------------------------------------
    This function instantiates a typed `TrainingPair` for each exemplar in
    `EXEMPLARS`. Every pair is assigned a standardized deterministic identifier
    (`TWU_GOLD_<DOMAIN>_<INDEX>`), tagged with capability labels, given a
    UTC ISO-8601 generation timestamp, and classified as 'gold_certified'.

    Inputs:
        None.

    Outputs:
        List[TrainingPair]: The complete collection of verified exemplar pairs.

    Step-by-Step Logic:
        1. Capture current UTC timestamp string via `datetime.now(timezone.utc).isoformat()`.
        2. Initialize empty accumulator list `pairs`.
        3. Enumerate through each raw exemplar dictionary in `EXEMPLARS`.
        4. Synthesize a unique, uppercase domain-prefixed identifier string.
        5. Construct a `TrainingPair` dataclass instance with full metadata.
        6. Append to `pairs` list and return.
    """
    # One shared timestamp for the whole batch (not per record).
    pairs: List[TrainingPair] = []
    now: str = datetime.now(timezone.utc).isoformat()

    for idx, ex in enumerate(EXEMPLARS):
        # Deterministic, easily sortable ID scheme: TWU_GOLD_<DOMAIN>_<0000>
        pair_id = f"TWU_GOLD_{ex['domain'].upper()}_{idx:04d}"
        pairs.append(
            TrainingPair(
                id=pair_id,
                domain=ex["domain"],
                kind="dpo",
                prompt=ex["prompt"],
                chosen=ex["chosen"],
                rejected=ex["rejected"],
                quality="gold_certified",
                capabilities=ex["capabilities"],
                created_at=now,
            )
        )
    return pairs


def export_seat_shard(seat_id: int, root_dir: Optional[Path] = None) -> Path:
    """Exports a dedicated, collision-free shard for a specific seat in exchange/.

    Educational Note on Partitioned Peer Sharding:
    ----------------------------------------------
    In decentralized multi-agent architectures, allowing multiple agents to write
    directly to a single file causes race conditions and file corruptions.
    By partitioning export targets into `exchange/seat_<XX>_corpus.jsonl`:
    1. Each agent writes exclusively to its own assigned filename.
    2. Write collisions are completely eliminated at the filesystem layer.
    3. An accompanying `.sha256` manifest checksum is generated to allow peers
       to verify shard integrity before ingesting.

    Inputs:
        seat_id (int): Numeric seat index [0, 31] owning this shard.
        root_dir (Optional[Path]): Workspace root path (defaults to current directory).

    Outputs:
        Path: Filesystem Path pointing to the exported `.jsonl` shard file.

    Step-by-Step Logic:
        1. Resolve workspace root and ensure `exchange/` directory exists.
        2. Compute target output path: `exchange/seat_<XX>_corpus.jsonl`.
        3. Generate full language matrix using `generate_language_matrix()`.
        4. Open shard file for writing with UTF-8 encoding.
        5. Serialize each `TrainingPair` dictionary as a newline-delimited JSON line.
        6. Compute the cryptographic SHA-256 hash of the generated shard file.
        7. Write checksum manifest to `exchange/seat_<XX>_corpus.sha256`.
        8. Return the shard `Path`.
    """
    # Note: the shard content is the same exemplar set for every seat; only the
    # filename differs, which is what keeps seats from colliding on write.
    # 1. Resolve workspace root and target directory
    root = Path(root_dir or ".").resolve()
    exchange = root / "exchange"
    exchange.mkdir(parents=True, exist_ok=True)
    shard_path = exchange / f"seat_{seat_id:02d}_corpus.jsonl"

    # 2. Generate training pairs
    pairs = generate_language_matrix()

    # 3. Stream records to JSONL file
    with open(shard_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_dict()) + "\n")

    # Manifest format matches `sha256sum -c`: "<hex>  <filename>" (two spaces).
    # 4. Compute and write SHA-256 integrity manifest
    checksum = hashlib.sha256(shard_path.read_bytes()).hexdigest()
    manifest_path = exchange / f"seat_{seat_id:02d}_corpus.sha256"
    manifest_path.write_text(f"{checksum}  {shard_path.name}\n", encoding="utf-8")

    return shard_path


def reconcile_mesh_shards(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Merges all peer shards without overwrites; deduplicates on content SHA-256.

    Educational Note on Non-Overwrite Reconciliation:
    -------------------------------------------------
    This function implements a distributed consensus pattern for data artifacts:
    1. It discovers all peer shards (`exchange/seat_*_corpus.jsonl`).
    2. It parses each JSON record line by line.
    3. It computes a content-addressed SHA-256 hash of `domain:prompt:chosen`.
    4. Records with duplicate hashes are skipped, ensuring idempotency.
    5. The unified, non-conflicting dataset is compiled to
       `data/datasets/golden_multilang_corpus.jsonl`.

    Inputs:
        root_dir (Optional[Path]): Workspace root path (defaults to current directory).

    Outputs:
        Dict[str, Any]: Summary dictionary containing:
            - 'master_path': Absolute path to the unified compiled corpus.
            - 'total_records': Count of deduplicated records retained.
            - 'shards_processed': Number of peer shard files ingested.
            - 'domains_covered': Count of distinct domain categories represented.

    Step-by-Step Logic:
        1. Resolve workspace root and verify existence of `exchange/`.
        2. If `exchange/` is absent, return empty summary dictionary.
        3. Initialize deduplication tracking set `seen_hashes` and `unified_records` list.
        4. Iterate through all `seat_*_corpus.jsonl` files in lexicographical order.
        5. Read each file line by line; decode JSON safely.
        6. Calculate content hash: `sha256(domain:prompt:chosen)`.
        7. If hash is new, record in `seen_hashes` and append row to `unified_records`.
        8. Create `data/datasets/` directory if missing.
        9. Write compiled records to `data/datasets/golden_multilang_corpus.jsonl`.
        10. Return summary statistics dictionary.
    """
    root = Path(root_dir or ".").resolve()
    exchange = root / "exchange"
    if not exchange.is_dir():
        # Nothing to merge. Return the same keys as the normal result so callers can
        # index the summary without checking which path ran; no master file is written.
        return {"master_path": None, "total_records": 0, "shards_processed": 0, "domains_covered": 0}

    # seen_hashes implements first-writer-wins dedup in sorted shard order, so the
    # merge result is the same on every box that sees the same shard files.
    seen_hashes: set = set()
    unified_records: list = []
    shards_processed: int = 0

    # Process all peer shards in sorted order for determinism
    for shard in sorted(exchange.glob("seat_*_corpus.jsonl")):
        shards_processed += 1
        with open(shard, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # Same formula as TrainingPair.sha256; .get() tolerates records missing a field.
                    # Content-addressed hashing for strict deduplication
                    h = hashlib.sha256(
                        f"{data.get('domain')}:{data.get('prompt')}:{data.get('chosen')}".encode("utf-8")
                    ).hexdigest()
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        unified_records.append(data)
                except json.JSONDecodeError:
                    # Ignore malformed lines to prevent corrupted peer records from breaking the merge
                    continue

    # Note the master file itself is rewritten each run (it is derived output, fully
    # rebuildable from the immutable per-seat shards in exchange/).
    # Publish compiled non-overwrite dataset
    data_dir = root / "data" / "datasets"
    data_dir.mkdir(parents=True, exist_ok=True)
    master_path = data_dir / "golden_multilang_corpus.jsonl"
    with open(master_path, "w", encoding="utf-8") as f:
        for r in unified_records:
            f.write(json.dumps(r) + "\n")

    return {
        "master_path": str(master_path),
        "total_records": len(unified_records),
        "shards_processed": shards_processed,
        "domains_covered": len(set(r.get("domain") for r in unified_records)),
    }
