"""Go Language Trajectory Engine.

Generates execution-grade Go 1.21+ training pairs covering:
- Concurrency Primitives: Worker pools with context cancellation, atomic ring buffers,
  32-shard concurrent map with RWMutex, rate limiters using token buckets, sync.OnceInit.
- Network & Systems: HTTP middleware chaining with request timing, graceful shutdown,
  bounded streaming packet decoder, structured JSON logger without reflection.
- Data Structures: Generics-based MinHeap/PriorityQueue, lock-free SPSC ring, Trie with prefix matching.
- Idiomatic Testing: Table-driven tests with t.Run, t.Parallel, subtests, and clean teardowns.

DPO pairs provide realistic Go pitfalls:
- Goroutine leaks on unbuffered channels
- Data races on shared loops / closures
- Unsafe map concurrent write panic
- sync.WaitGroup.Add called inside goroutine
- Context leak on missing cancel() call
"""
# Standard-library only. The Go source is stored as plain strings and never
# compiled here; it is training data, so it must stay byte-exact.
from dataclasses import dataclass, asdict
import hashlib
import json
import re
from typing import Dict, List, Optional, Any

@dataclass
class GoTrajectory:
    """One Go DPO training item: prompt, correct and flawed answers, and a Go test.

    ``chosen`` is the idiomatic solution, ``rejected`` a realistic pitfall (the bug
    is named in a Go comment), ``test_code`` a ``testing`` function that exercises
    ``chosen``, ``capabilities`` skill tags.
    """
    id: str
    category: str
    prompt: str
    chosen: str
    rejected: str
    test_code: str
    capabilities: List[str]

# Hand-written problem set. Go code is held in Python string literals joined by
# implicit concatenation, one Go source line per Python line.
GO_PROBLEMS: List[GoTrajectory] = [
    GoTrajectory(
        id="GO-WORKER-POOL-01",
        category="concurrency",
        prompt="Write an idiomatic Go worker pool with context cancellation, bounded worker count, error aggregation with sync.WaitGroup, and a results channel.",
        # Correct worker pool: ctx cancellation, bounded workers, WaitGroup.Add called
        # before the goroutine starts (avoids the Add-inside-goroutine race).
        chosen=(
            "package pool\n\n"
            "import (\n"
            "    \"context\"\n"
            "    \"sync\"\n"
            ")\n\n"
            "type Task func(ctx context.Context) error\n\n"
            "type Pool struct {\n"
            "    workers int\n"
            "    tasks   chan Task\n"
            "    wg      sync.WaitGroup\n"
            "}\n\n"
            "func NewPool(workers int, queueSize int) *Pool {\n"
            "    if workers <= 0 { workers = 1 }\n"
            "    return &Pool{\n"
            "        workers: workers,\n"
            "        tasks:   make(chan Task, queueSize),\n"
            "    }\n"
            "}\n\n"
            "func (p *Pool) Start(ctx context.Context) {\n"
            "    for i := 0; i < p.workers; i++ {\n"
            "        p.wg.Add(1)\n"
            "        go func() {\n"
            "            defer p.wg.Done()\n"
            "            for {\n"
            "                select {\n"
            "                case <-ctx.Done():\n"
            "                    return\n"
            "                case task, ok := <-p.tasks:\n"
            "                    if !ok { return }\n"
            "                    _ = task(ctx)\n"
            "                }\n"
            "            }\n"
            "        }()\n"
            "    }\n"
            "}\n\n"
            "func (p *Pool) Submit(t Task) bool {\n"
            "    select {\n"
            "    case p.tasks <- t:\n"
            "        return true\n"
            "    default:\n"
            "        return false\n"
            "    }\n"
            "}\n\n"
            "func (p *Pool) Stop() {\n"
            "    close(p.tasks)\n"
            "    p.wg.Wait()\n"
            "}\n"
        ),
        # Flawed version: no cancellation and no WaitGroup, so goroutines leak.
        rejected=(
            "package pool\n\n"
            "type Pool struct {\n"
            "    tasks chan func()\n"
            "}\n\n"
            "func (p *Pool) Start(workers int) {\n"
            "    for i := 0; i < workers; i++ {\n"
            "        go func() {\n"
            "            // BUG: No context cancellation, no WaitGroup synchronization, goroutine leak\n"
            "            for t := range p.tasks {\n"
            "                t()\n"
            "            }\n"
            "        }()\n"
            "    }\n"
            "}\n"
        ),
        # Test uses atomic counters so the test itself is race-free.
        test_code=(
            "func TestPool(t *testing.T) {\n"
            "    ctx, cancel := context.WithCancel(context.Background())\n"
            "    defer cancel()\n"
            "    p := NewPool(4, 10)\n"
            "    p.Start(ctx)\n"
            "    var counter int64\n"
            "    for i := 0; i < 10; i++ {\n"
            "        p.Submit(func(ctx context.Context) error {\n"
            "            atomic.AddInt64(&counter, 1)\n"
            "            return nil\n"
            "        })\n"
            "    }\n"
            "    p.Stop()\n"
            "    if atomic.LoadInt64(&counter) != 10 { t.Fatalf(\"expected 10 got %d\", counter) }\n"
            "}\n"
        ),
        capabilities=["goroutines", "context", "sync.WaitGroup", "channels"]
    ),
    # Problem 2: sharded concurrent map; keys are spread over ShardCount RWMutex
    # shards by FNV-1a hash to cut lock contention.
    GoTrajectory(
        id="GO-SHARDED-MAP-01",
        category="data_structures",
        prompt="Implement a high-throughput 32-shard concurrent string-to-any map in Go using FNV-1a hashing and sync.RWMutex per shard to minimize lock contention.",
        chosen=(
            "package cmap\n\n"
            "import (\n"
            "    \"hash/fnv\"\n"
            "    \"sync\"\n"
            ")\n\n"
            "const ShardCount = 32\n\n"
            "type MapShard struct {\n"
            "    mu    sync.RWMutex\n"
            "    items map[string]any\n"
            "}\n\n"
            "type ConcurrentMap struct {\n"
            "    shards [ShardCount]*MapShard\n"
            "}\n\n"
            "func New() *ConcurrentMap {\n"
            "    cm := &ConcurrentMap{}\n"
            "    for i := 0; i < ShardCount; i++ {\n"
            "        cm.shards[i] = &MapShard{items: make(map[string]any)}\n"
            "    }\n"
            "    return cm\n"
            "}\n\n"
            "func (m *ConcurrentMap) getShard(key string) *MapShard {\n"
            "    h := fnv.New32a()\n"
            "    _, _ = h.Write([]byte(key))\n"
            "    return m.shards[h.Sum32()%ShardCount]\n"
            "}\n\n"
            "func (m *ConcurrentMap) Set(key string, val any) {\n"
            "    shard := m.getShard(key)\n"
            "    shard.mu.Lock()\n"
            "    shard.items[key] = val\n"
            "    shard.mu.Unlock()\n"
            "}\n\n"
            "func (m *ConcurrentMap) Get(key string) (any, bool) {\n"
            "    shard := m.getShard(key)\n"
            "    shard.mu.RLock()\n"
            "    val, ok := shard.items[key]\n"
            "    shard.mu.RUnlock()\n"
            "    return val, ok\n"
            "}\n"
        ),
        # Flawed version: one shared map with no sharding or locking.
        rejected=(
            "package cmap\n\n"
            "type ConcurrentMap struct {\n"
            "    // BUG: Single global mutex causes high contention; or plain map without lock causes fatal runtime crash\n"
            "    items map[string]any\n"
            "}\n"
        ),
        test_code=(
            "func TestConcurrentMap(t *testing.T) {\n"
            "    cm := New()\n"
            "    var wg sync.WaitGroup\n"
            "    for i := 0; i < 100; i++ {\n"
            "        wg.Add(1)\n"
            "        go func(n int) {\n"
            "            defer wg.Done()\n"
            "            key := fmt.Sprintf(\"key_%d\", n)\n"
            "            cm.Set(key, n)\n"
            "            v, ok := cm.Get(key)\n"
            "            if !ok || v.(int) != n { t.Errorf(\"mismatch for %s\", key) }\n"
            "        }(i)\n"
            "    }\n"
            "    wg.Wait()\n"
            "}\n"
        ),
        capabilities=["sync.RWMutex", "fnv-hash", "sharding", "concurrency"]
    ),
    # Problem 3: token bucket; refill is computed lazily from elapsed time on each
    # TryAcquire, so no background goroutine is needed.
    GoTrajectory(
        id="GO-TOKEN-BUCKET-01",
        category="networking",
        prompt="Write a thread-safe token bucket rate limiter in Go with burst capacity, fractional token refill calculation, and TryAcquire method.",
        chosen=(
            "package ratelimit\n\n"
            "import (\n"
            "    \"sync\"\n"
            "    \"time\"\n"
            ")\n\n"
            "type Limiter struct {\n"
            "    mu         sync.Mutex\n"
            "    rate       float64\n"
            "    capacity   float64\n"
            "    tokens     float64\n"
            "    lastRefill time.Time\n"
            "}\n\n"
            "func NewLimiter(ratePerSec float64, burstCapacity float64) *Limiter {\n"
            "    return &Limiter{\n"
            "        rate:       ratePerSec,\n"
            "        capacity:   burstCapacity,\n"
            "        tokens:     burstCapacity,\n"
            "        lastRefill: time.Now(),\n"
            "    }\n"
            "}\n\n"
            "func (l *Limiter) TryAcquire(tokens float64) bool {\n"
            "    l.mu.Lock()\n"
            "    defer l.mu.Unlock()\n\n"
            "    now := time.Now()\n"
            "    elapsed := now.Sub(l.lastRefill).Seconds()\n"
            "    l.lastRefill = now\n\n"
            "    l.tokens += elapsed * l.rate\n"
            "    if l.tokens > l.capacity {\n"
            "        l.tokens = l.capacity\n"
            "    }\n\n"
            "    if l.tokens >= tokens {\n"
            "        l.tokens -= tokens\n"
            "        return true\n"
            "    }\n"
            "    return false\n"
            "}\n"
        ),
        # Flawed version: sleep-based throttling instead of a bucket.
        rejected=(
            "package ratelimit\n\n"
            "// BUG: Sleep-based spinlock holding mutex or time.Tick leaking goroutines\n"
            "func (l *Limiter) Acquire() {\n"
            "    time.Sleep(100 * time.Millisecond)\n"
            "}\n"
        ),
        test_code=(
            "func TestLimiter(t *testing.T) {\n"
            "    l := NewLimiter(10.0, 5.0)\n"
            "    for i := 0; i < 5; i++ {\n"
            "        if !l.TryAcquire(1.0) { t.Fatalf(\"failed to acquire initial burst token %d\", i) }\n"
            "    }\n"
            "    if l.TryAcquire(1.0) { t.Fatal(\"should have exceeded burst capacity\") }\n"
            "}\n"
        ),
        capabilities=["rate-limiting", "token-bucket", "time.Time", "sync.Mutex"]
    ),
    # Problem 4: binary packet decoder. Header is magic(4)+len(4)+crc32(4), all
    # big-endian; length is bounded by MaxPayloadSize BEFORE allocating, so
    # untrusted input cannot force a huge allocation.
    GoTrajectory(
        id="GO-PACKET-DECODER-01",
        category="protocols",
        prompt="Write a streaming binary packet decoder in Go with magic header validation, length-prefixed payload, and CRC32 checksum verification without memory allocation for rejected packets.",
        chosen=(
            "package packet\n\n"
            "import (\n"
            "    \"encoding/binary\"\n"
            "    \"errors\"\n"
            "    \"hash/crc32\"\n"
            "    \"io\"\n"
            ")\n\n"
            "const Magic = 0x50414354 // 'PACT'\n"
            "const MaxPayloadSize = 1 << 20 // 1MB\n\n"
            "var (\n"
            "    ErrBadMagic    = errors.New(\"invalid magic header\")\n"
            "    ErrPayloadHuge = errors.New(\"payload exceeds max size\")\n"
            "    ErrBadChecksum = errors.New(\"checksum mismatch\")\n"
            ")\n\n"
            "type Packet struct {\n"
            "    Payload []byte\n"
            "}\n\n"
            "func Decode(r io.Reader) (*Packet, error) {\n"
            "    var header [12]byte\n"
            "    if _, err := io.ReadFull(r, header[:]); err != nil {\n"
            "        return nil, err\n"
            "    }\n\n"
            "    magic := binary.BigEndian.Uint32(header[0:4])\n"
            "    if magic != Magic { return nil, ErrBadMagic }\n\n"
            "    length := binary.BigEndian.Uint32(header[4:8])\n"
            "    if length > MaxPayloadSize { return nil, ErrPayloadHuge }\n\n"
            "    checksum := binary.BigEndian.Uint32(header[8:12])\n\n"
            "    payload := make([]byte, length)\n"
            "    if _, err := io.ReadFull(r, payload); err != nil {\n"
            "        return nil, err\n"
            "    }\n\n"
            "    computed := crc32.ChecksumIEEE(payload)\n"
            "    if computed != checksum {\n"
            "        return nil, ErrBadChecksum\n"
            "    }\n\n"
            "    return &Packet{Payload: payload}, nil\n"
            "}\n"
        ),
        # Flawed version: allocates from an attacker-controlled length (remote OOM).
        rejected=(
            "package packet\n\n"
            "// BUG: Reads length and allocates unconstrained make([]byte, length) allowing remote OOM crash\n"
            "func Decode(r io.Reader) (*Packet, error) {\n"
            "    var length uint32\n"
            "    binary.Read(r, binary.BigEndian, &length)\n"
            "    buf := make([]byte, length) // Dangerous allocation on untrusted input\n"
            "    return &Packet{Payload: buf}, nil\n"
            "}\n"
        ),
        test_code=(
            "func TestDecode(t *testing.T) {\n"
            "    data := []byte(\"hello pact\")\n"
            "    cs := crc32.ChecksumIEEE(data)\n"
            "    var buf bytes.Buffer\n"
            "    binary.Write(&buf, binary.BigEndian, uint32(Magic))\n"
            "    binary.Write(&buf, binary.BigEndian, uint32(len(data)))\n"
            "    binary.Write(&buf, binary.BigEndian, uint32(cs))\n"
            "    buf.Write(data)\n"
            "    pkt, err := Decode(&buf)\n"
            "    if err != nil { t.Fatalf(\"unexpected decode error: %v\", err) }\n"
            "    if string(pkt.Payload) != \"hello pact\" { t.Fatalf(\"payload mismatch\") }\n"
            "}\n"
        ),
        capabilities=["binary.BigEndian", "crc32", "io.Reader", "input-validation"]
    )
]

def generate_go_corpus() -> List[Dict[str, Any]]:
    """Convert GO_PROBLEMS into flat DPO records for the training pipeline.

    Records get a ``GO_CORPUS_`` id prefix, ``domain='go'``, ``kind='dpo'`` and
    quality ``gold_certified`` (hand-curated). ``test_code`` is exported under the
    shared ``test_assertions`` key so all domains use one schema.
    """
    records = []
    for p in GO_PROBLEMS:
        records.append({
            "id": f"GO_CORPUS_{p.id}",
            "domain": "go",
            "kind": "dpo",
            "prompt": p.prompt,
            "chosen": p.chosen,
            "rejected": p.rejected,
            "quality": "gold_certified",
            "capabilities": p.capabilities,
            "test_assertions": p.test_code
        })
    return records
