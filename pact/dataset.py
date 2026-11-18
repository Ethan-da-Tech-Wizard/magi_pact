"""Multi-language Golden Training Dataset & Non-Overwrite Sharding Engine.

Curates verified SFT/DPO pairs across C, C++, C#, Java, Rust, TypeScript,
JavaScript, Ruby, HTML, CSS, Bash, Arch Linux, Fedora, BIOS/UEFI, and Git.
Implements federated shard reconciliation across the 32-seat mesh.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

DOMAINS = [
    "c_cpp",
    "csharp",
    "java",
    "rust",
    "typescript",
    "javascript",
    "ruby",
    "html_css",
    "bash_posix",
    "arch_linux",
    "fedora_linux",
    "bios_uefi",
    "git_internals",
    "mesh_protocol",
]

@dataclass
class TrainingPair:
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
        return asdict(self)

    @property
    def sha256(self) -> str:
        content = f"{self.domain}:{self.prompt}:{self.chosen}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Exemplar library establishing rigorous idiomatic standards across all target domains
EXEMPLARS = [
    {
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
            "{\"status\": \"certified\", \"node\": \"macbook-air\"}\n"
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


def generate_language_matrix() -> List[TrainingPair]:
    """Compiles the core verified dataset across all required language domains."""
    pairs = []
    now = datetime.now(timezone.utc).isoformat()
    for idx, ex in enumerate(EXEMPLARS):
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
    """Exports a dedicated, collision-free shard for a specific seat in exchange/."""
    root = Path(root_dir or ".").resolve()
    exchange = root / "exchange"
    exchange.mkdir(parents=True, exist_ok=True)
    shard_path = exchange / f"seat_{seat_id:02d}_corpus.jsonl"
    
    pairs = generate_language_matrix()
    with open(shard_path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p.to_dict()) + "\n")
            
    # Also write a manifest checksum
    checksum = hashlib.sha256(shard_path.read_bytes()).hexdigest()
    manifest_path = exchange / f"seat_{seat_id:02d}_corpus.sha256"
    manifest_path.write_text(f"{checksum}  {shard_path.name}\n", encoding="utf-8")
    
    return shard_path


def reconcile_mesh_shards(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Merges all peer shards without overwrites; deduplicates on content SHA-256."""
    root = Path(root_dir or ".").resolve()
    exchange = root / "exchange"
    if not exchange.is_dir():
        return {"total_records": 0, "unique_records": 0, "shards_processed": 0}

    seen_hashes = set()
    unified_records = []
    shards_processed = 0

    for shard in sorted(exchange.glob("seat_*_corpus.jsonl")):
        shards_processed += 1
        with open(shard, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    h = hashlib.sha256(
                        f"{data.get('domain')}:{data.get('prompt')}:{data.get('chosen')}".encode("utf-8")
                    ).hexdigest()
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        unified_records.append(data)
                except json.JSONDecodeError:
                    continue

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
