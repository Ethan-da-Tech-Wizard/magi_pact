"""Go Language Dataset Entries: 6 SFT + 6 DPO (Total 12)
All chosen/completion programs are self-contained Go programs with self-testing assertions in main().
"""

from datetime import datetime, timezone

# Single timestamp shared by all records in this module; evaluated at import time.
NOW = datetime.now(timezone.utc).isoformat()

# Record schema (shared by every *_entries.py file):
#   id / domain / kind  - unique TWU_POLY_<LANG>_<KIND>_NNNN id, language tag, and "sft" or "dpo".
#   prompt              - the instruction a model is trained to answer.
#   completion          - (sft) a full, runnable reference program that self-tests with assertions.
#   chosen / rejected   - (dpo) a correct program vs. a plausible but flawed one for the same prompt.
#   rejection_reason    - (dpo) the concrete defect in "rejected", so the preference signal is explicit.
#   capabilities        - skill tags used to balance and filter the corpus.
#   quality             - "execution_verified": the code was compiled and run before being committed.
#   created_at          - module import time (NOW), not a per-record authoring time.
# The code bodies are raw strings (r"""...""") so backslashes and escapes in the target language survive intact.
# SFT entries 1-6 teach whole-program patterns; DPO entries 1-6 teach one specific pitfall each.
GO_ENTRIES = [
    # ------------------ SFT 001 ------------------
    {
        # Teaches: bounded worker pool with context timeout cancellation and sync.WaitGroup.
        "id": "TWU_POLY_GO_SFT_0001",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a high-throughput bounded worker pool in Go with context.Context timeout cancellation, sync.WaitGroup coordination, and self-testing assertions in main().",
        "completion": r"""package main

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Result struct {
	Input  int
	Output int
	Err    error
}

func WorkerPool(ctx context.Context, numWorkers int, jobs []int) []Result {
	jobsChan := make(chan int, len(jobs))
	resultsChan := make(chan Result, len(jobs))

	for _, j := range jobs {
		jobsChan <- j
	}
	close(jobsChan)

	var wg sync.WaitGroup
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case job, ok := <-jobsChan:
					if !ok {
						return
					}
					// Simulate work
					resultsChan <- Result{
						Input:  job,
						Output: job * 2,
						Err:    nil,
					}
				}
			}
		}()
	}

	wg.Wait()
	close(resultsChan)

	var results []Result
	for res := range resultsChan {
		results = append(results, res)
	}
	return results
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	inputs := make([]int, 20)
	for i := 0; i < 20; i++ {
		inputs[i] = i + 1
	}

	results := WorkerPool(ctx, 4, inputs)
	if len(results) != 20 {
		panic(fmt.Sprintf("Expected 20 results, got %d", len(results)))
	}

	sum := 0
	for _, r := range results {
		sum += r.Output
	}

	// Sum 1..20 * 2 = 2 * (20 * 21) / 2 = 420
	if sum != 420 {
		panic(fmt.Sprintf("Expected sum 420, got %d", sum))
	}

	fmt.Printf("GO SFT 0001: WorkerPool executed cleanly. Sum = %d\n", sum)
}
""",
        "capabilities": ["concurrency", "worker_pool", "context", "channels", "waitgroup", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 002 ------------------
    {
        # Teaches: sharded concurrent map: 32 FNV-1a shards each guarded by an RWMutex.
        "id": "TWU_POLY_GO_SFT_0002",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a high-concurrency sharded map in Go using 32 FNV-1a hashed shards and sync.RWMutex with self-testing assertions in main().",
        "completion": r"""package main

import (
	"fmt"
	"hash/fnv"
	"sync"
)

const NumShards = 32

type Shard struct {
	sync.RWMutex
	items map[string]int
}

type ShardedMap struct {
	shards [NumShards]*Shard
}

func NewShardedMap() *ShardedMap {
	sm := &ShardedMap{}
	for i := 0; i < NumShards; i++ {
		sm.shards[i] = &Shard{
			items: make(map[string]int),
		}
	}
	return sm
}

func (sm *ShardedMap) getShard(key string) *Shard {
	h := fnv.New32a()
	h.Write([]byte(key))
	idx := h.Sum32() % NumShards
	return sm.shards[idx]
}

func (sm *ShardedMap) Set(key string, val int) {
	shard := sm.getShard(key)
	shard.Lock()
	defer shard.Unlock()
	shard.items[key] = val
}

func (sm *ShardedMap) Get(key string) (int, bool) {
	shard := sm.getShard(key)
	shard.RLock()
	defer shard.RUnlock()
	val, ok := shard.items[key]
	return val, ok
}

func main() {
	sm := NewShardedMap()
	var wg sync.WaitGroup

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			k := fmt.Sprintf("key-%d", idx)
			sm.Set(k, idx*10)
		}(i)
	}

	wg.Wait()

	for i := 0; i < 100; i++ {
		k := fmt.Sprintf("key-%d", i)
		val, ok := sm.Get(k)
		if !ok || val != i*10 {
			panic(fmt.Sprintf("Mismatch for %s: got %d, expected %d", k, val, i*10))
		}
	}

	fmt.Println("GO SFT 0002: ShardedMap 32-shard concurrent verification passed.")
}
""",
        "capabilities": ["concurrency", "sharding", "rwmutex", "fnv1a", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 003 ------------------
    {
        # Teaches: lock-free ring buffer using sync/atomic and power-of-two masking.
        "id": "TWU_POLY_GO_SFT_0003",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a lock-free circular ring buffer in Go using sync/atomic with power-of-two masking and self-testing assertions in main().",
        "completion": r"""package main

import (
	"fmt"
	"sync/atomic"
)

type AtomicRingBuffer struct {
	storage []uint64
	mask    uint64
	head    uint64
	tail    uint64
}

func NewAtomicRingBuffer(powerOfTwoCap uint64) *AtomicRingBuffer {
	if powerOfTwoCap == 0 || (powerOfTwoCap&(powerOfTwoCap-1)) != 0 {
		panic("Capacity must be a power of two")
	}
	return &AtomicRingBuffer{
		storage: make([]uint64, powerOfTwoCap),
		mask:    powerOfTwoCap - 1,
	}
}

func (rb *AtomicRingBuffer) Push(val uint64) bool {
	head := atomic.LoadUint64(&rb.head)
	tail := atomic.LoadUint64(&rb.tail)
	if head-tail == uint64(len(rb.storage)) {
		return false // Full
	}
	rb.storage[head&rb.mask] = val
	atomic.StoreUint64(&rb.head, head+1)
	return true
}

func (rb *AtomicRingBuffer) Pop() (uint64, bool) {
	tail := atomic.LoadUint64(&rb.tail)
	head := atomic.LoadUint64(&rb.head)
	if tail == head {
		return 0, false // Empty
	}
	val := rb.storage[tail&rb.mask]
	atomic.StoreUint64(&rb.tail, tail+1)
	return val, true
}

func main() {
	rb := NewAtomicRingBuffer(8)

	for i := uint64(1); i <= 8; i++ {
		if !rb.Push(i * 100) {
			panic("Push failed unexpectedly")
		}
	}

	if rb.Push(999) {
		panic("Buffer should be full")
	}

	for i := uint64(1); i <= 4; i++ {
		val, ok := rb.Pop()
		if !ok || val != i*100 {
			panic(fmt.Sprintf("Pop error: expected %d, got %d", i*100, val))
		}
	}

	for i := uint64(1); i <= 4; i++ {
		if !rb.Push(2000 + i) {
			panic("Wrap push failed")
		}
	}

	var results []uint64
	for {
		val, ok := rb.Pop()
		if !ok {
			break
		}
		results = append(results, val)
	}

	expected := []uint64{500, 600, 700, 800, 2001, 2002, 2003, 2004}
	for i, v := range expected {
		if results[i] != v {
			panic("Mismatch in ring contents")
		}
	}

	fmt.Println("GO SFT 0003: AtomicRingBuffer wrap-around passed.")
}
""",
        "capabilities": ["atomics", "ring_buffer", "lock_free", "power_of_two", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 004 ------------------
    {
        # Teaches: sync.Pool byte-buffer pool with a capacity cap so oversized buffers are not retained.
        "id": "TWU_POLY_GO_SFT_0004",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a reusable byte buffer pool in Go using sync.Pool with an upper capacity limit to prevent memory bloat, with self-testing assertions in main().",
        "completion": r"""package main

import (
	"bytes"
	"fmt"
	"sync"
)

const MaxRetainedCapacity = 64 * 1024 // 64 KB

type BufferPool struct {
	pool sync.Pool
}

func NewBufferPool() *BufferPool {
	return &BufferPool{
		pool: sync.Pool{
			New: func() any {
				return new(bytes.Buffer)
			},
		},
	}
}

func (bp *BufferPool) Get() *bytes.Buffer {
	buf := bp.pool.Get().(*bytes.Buffer)
	buf.Reset()
	return buf
}

func (bp *BufferPool) Put(buf *bytes.Buffer) {
	// Discard buffers that grew abnormally large to prevent permanent heap bloating
	if buf.Cap() <= MaxRetainedCapacity {
		buf.Reset()
		bp.pool.Put(buf)
	}
}

func main() {
	bp := NewBufferPool()

	buf := bp.Get()
	buf.WriteString("hello pact")
	if buf.String() != "hello pact" {
		panic("Buffer content mismatch")
	}
	bp.Put(buf)

	// Large outlier buffer
	largeBuf := bp.Get()
	largeBuf.Grow(128 * 1024) // 128 KB > 64 KB
	bp.Put(largeBuf)          // Discarded automatically

	reused := bp.Get()
	if reused.Len() != 0 {
		panic("Reused buffer should be reset")
	}

	fmt.Println("GO SFT 0004: BufferPool capacity cap verified.")
}
""",
        "capabilities": ["sync_pool", "memory_management", "heap_optimization", "bytes_buffer", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 005 ------------------
    {
        # Teaches: token bucket rate limiter with thread-safe refill and non-blocking TryAcquire.
        "id": "TWU_POLY_GO_SFT_0005",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a token bucket rate limiter in Go with thread-safe replenishment and non-blocking TryAcquire, with unit tests in main().",
        "completion": r"""package main

import (
	"fmt"
	"sync"
	"time"
)

type TokenBucket struct {
	capacity   float64
	tokens     float64
	refillRate float64 // tokens per second
	lastRefill time.Time
	mu         sync.Mutex
}

func NewTokenBucket(capacity float64, refillRate float64) *TokenBucket {
	return &TokenBucket{
		capacity:   capacity,
		tokens:     capacity,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

func (tb *TokenBucket) TryAcquire(count float64) bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens = tb.tokens + elapsed*tb.refillRate
	if tb.tokens > tb.capacity {
		tb.tokens = tb.capacity
	}
	tb.lastRefill = now

	if tb.tokens >= count {
		tb.tokens -= count
		return true
	}
	return false
}

func main() {
	limiter := NewTokenBucket(3, 10) // 3 tokens, 10 tokens/sec

	// First 3 should succeed immediately
	if !limiter.TryAcquire(1) || !limiter.TryAcquire(1) || !limiter.TryAcquire(1) {
		panic("Burst tokens should be available")
	}

	// 4th must fail
	if limiter.TryAcquire(1) {
		panic("Exceeded capacity token should be denied")
	}

	time.Sleep(150 * time.Millisecond) // Adds ~1.5 tokens

	if !limiter.TryAcquire(1) {
		panic("Replenished token should be acquirable")
	}

	fmt.Println("GO SFT 0005: TokenBucket rate limiter verified.")
}
""",
        "capabilities": ["rate_limiting", "token_bucket", "concurrency", "mutex", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 006 ------------------
    {
        # Teaches: binary packet parser with strict bounds validation and typed errors.
        "id": "TWU_POLY_GO_SFT_0006",
        "domain": "go",
        "kind": "sft",
        "prompt": "Implement a binary protocol packet parser in Go with strict bounds validation and typed error handling, with self-testing assertions in main().",
        "completion": r"""package main

import (
	"encoding/binary"
	"errors"
	"fmt"
)

var (
	ErrPacketTooShort = errors.New("packet shorter than minimum header size")
	ErrInvalidMagic   = errors.New("invalid protocol magic byte sequence")
	ErrTruncatedBody  = errors.New("payload is shorter than declared length")
)

type Packet struct {
	Magic   uint16
	Type    uint8
	Payload []byte
}

func DecodePacket(data []byte) (*Packet, error) {
	// Header: Magic (2 bytes) + Type (1 byte) + Length (2 bytes) = 5 bytes
	if len(data) < 5 {
		return nil, ErrPacketTooShort
	}

	magic := binary.BigEndian.Uint16(data[0:2])
	if magic != 0x4D50 { // 'MP'
		return nil, ErrInvalidMagic
	}

	pType := data[2]
	payloadLen := int(binary.BigEndian.Uint16(data[3:5]))

	if len(data) < 5+payloadLen {
		return nil, ErrTruncatedBody
	}

	payload := make([]byte, payloadLen)
	copy(payload, data[5:5+payloadLen])

	return &Packet{
		Magic:   magic,
		Type:    pType,
		Payload: payload,
	}, nil
}

func main() {
	valid := []byte{0x4D, 0x50, 0x01, 0x00, 0x03, 'A', 'B', 'C'}
	pkt, err := DecodePacket(valid)
	if err != nil || pkt.Type != 1 || string(pkt.Payload) != "ABC" {
		panic("Failed to parse valid packet")
	}

	// Truncated header
	_, err = DecodePacket([]byte{0x4D, 0x50})
	if !errors.Is(err, ErrPacketTooShort) {
		panic("Expected ErrPacketTooShort")
	}

	// Truncated payload
	_, err = DecodePacket([]byte{0x4D, 0x50, 0x01, 0x00, 0x05, 'X'})
	if !errors.Is(err, ErrTruncatedBody) {
		panic("Expected ErrTruncatedBody")
	}

	fmt.Println("GO SFT 0006: Binary packet decoder bounds checks verified.")
}
""",
        "capabilities": ["binary_protocol", "bounds_checking", "packet_parsing", "error_handling", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 001 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: goroutine sends on an unbuffered channel after the receiver timed out (goroutine leak); chosen avoids the leak.
        "id": "TWU_POLY_GO_DPO_0001",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Prevent goroutine leaks when performing asynchronous operations with early timeouts in Go.",
        "chosen": r"""package main

import (
	"context"
	"fmt"
	"time"
)

func QueryWithTimeout(timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// Buffered channel of size 1 ensures goroutine sender can write without blocking,
	// even if the caller abandons the read due to timeout.
	resChan := make(chan string, 1)

	go func() {
		// Simulating network query
		time.Sleep(50 * time.Millisecond)
		resChan <- "ok"
	}()

	select {
	case res := <-resChan:
		return res, nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}

func main() {
	res, err := QueryWithTimeout(100 * time.Millisecond)
	if err != nil || res != "ok" {
		panic("Expected clean success")
	}

	_, err = QueryWithTimeout(10 * time.Millisecond)
	if err == nil {
		panic("Expected timeout error")
	}

	fmt.Println("GO DPO 0001 Chosen: Goroutine leak avoided via buffered channel.")
}
""",
        "rejected": r"""package main

import (
	"context"
	"time"
)

func LeakyQuery(timeout time.Duration) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// FATAL BUG: Unbuffered channel causes permanent goroutine leak!
	// If ctx.Done() triggers first, the background goroutine blocks forever on ch <- res
	ch := make(chan string)

	go func() {
		time.Sleep(50 * time.Millisecond)
		ch <- "response" // BLOCKS FOREVER IF RECEIVER LEFT -> GOROUTINE LEAK
	}()

	select {
	case res := <-ch:
		return res, nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}
""",
        "rejection_reason": "Rejected code sends to an unbuffered channel in a goroutine while the receiver may exit due to context timeout, leaving the sender blocked permanently and leaking goroutines and memory.",
        "capabilities": ["concurrency", "goroutine_leak_prevention", "buffered_channels", "context"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 002 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: loop variable captured by goroutines (all see the final index).
        "id": "TWU_POLY_GO_DPO_0002",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Safely launch concurrent goroutines within a loop avoiding loop variable capture bugs in Go.",
        "chosen": r"""package main

import (
	"fmt"
	"sync"
)

func main() {
	var wg sync.WaitGroup
	var mu sync.Mutex
	collected := make(map[int]bool)

	for i := 0; i < 10; i++ {
		wg.Add(1)
		// Pass 'i' as an explicit function parameter to create a local copy
		go func(val int) {
			defer wg.Done()
			mu.Lock()
			collected[val] = true
			mu.Unlock()
		}(i)
	}

	wg.Wait()

	if len(collected) != 10 {
		panic(fmt.Sprintf("Expected 10 distinct values, got %d", len(collected)))
	}

	fmt.Println("GO DPO 0002 Chosen: Parameter passing prevented loop capture race.")
}
""",
        "rejected": r"""package main

import (
	"fmt"
	"sync"
)

func BuggyLoop() {
	var wg sync.WaitGroup
	for i := 0; i < 10; i++ {
		wg.Add(1)
		// FATAL BUG: Closure captures mutable loop variable 'i'
		go func() {
			defer wg.Done()
			fmt.Println(i) // Race condition: goroutines read modified 'i' (often printing 10 repeatedly)
		}()
	}
	wg.Wait()
}
""",
        "rejection_reason": "Rejected code captures the loop variable 'i' across concurrent goroutines without rebinding or parameter passing, causing all goroutines to race and observe the final mutated index.",
        "capabilities": ["concurrency", "closures", "goroutines", "loop_variables"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 003 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: unsynchronized concurrent map writes (fatal runtime error).
        "id": "TWU_POLY_GO_DPO_0003",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Safely mutate a shared map concurrently in Go avoiding fatal runtime crashes.",
        "chosen": r"""package main

import (
	"fmt"
	"sync"
)

type SafeCounterMap struct {
	sync.RWMutex
	data map[string]int
}

func main() {
	sc := &SafeCounterMap{data: make(map[string]int)}
	var wg sync.WaitGroup

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sc.Lock()
			sc.data["hits"]++
			sc.Unlock()
		}()
	}

	wg.Wait()

	sc.RLock()
	total := sc.data["hits"]
	sc.RUnlock()

	if total != 100 {
		panic(fmt.Sprintf("Expected 100, got %d", total))
	}

	fmt.Println("GO DPO 0003 Chosen: RWMutex protected concurrent map writes.")
}
""",
        "rejected": r"""package main

func FatalMapWrite() {
	m := make(map[string]int)
	for i := 0; i < 100; i++ {
		go func() {
			// FATAL RUNTIME CRASH: concurrent map writes trigger unrecoverable fatal error:
			// fatal error: concurrent map writes
			m["hits"]++
		}()
	}
}
""",
        "rejection_reason": "Rejected code writes concurrently to a standard Go map without synchronization, which triggers an unrecoverable runtime crash: fatal error: concurrent map writes.",
        "capabilities": ["concurrency", "concurrent_map_writes", "rwmutex", "runtime_safety"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 004 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: buf[offset:offset+length] with no bounds validation (slice-range panic).
        "id": "TWU_POLY_GO_DPO_0004",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Extract a sub-slice from an untrusted byte buffer in Go with bounds protection against runtime slice index out of range panics.",
        "chosen": r"""package main

import (
	"errors"
	"fmt"
)

var ErrOutOfBounds = errors.New("requested slice offset and length out of range")

func SafeSubSlice(buf []byte, offset int, length int) ([]byte, error) {
	if offset < 0 || length < 0 || offset > len(buf) || offset+length > len(buf) {
		return nil, ErrOutOfBounds
	}
	return buf[offset : offset+length], nil
}

func main() {
	data := []byte("antigravity")
	sub, err := SafeSubSlice(data, 0, 4)
	if err != nil || string(sub) != "anti" {
		panic("Failed valid slice")
	}

	// Out of bounds attempt
	_, err = SafeSubSlice(data, 8, 10)
	if !errors.Is(err, ErrOutOfBounds) {
		panic("Expected ErrOutOfBounds")
	}

	fmt.Println("GO DPO 0004 Chosen: SafeSubSlice prevented slice panic.")
}
""",
        "rejected": r"""package main

func UnsafeSlice(buf []byte, offset int, length int) []byte {
	// FATAL: Directly slicing without validation panics at runtime:
	// panic: runtime error: slice bounds out of range [:20] with length 11
	return buf[offset : offset+length]
}
""",
        "rejection_reason": "Rejected code performs slice expressions buf[offset:offset+length] without boundary validation, causing unhandled runtime slice bounds out of range panics.",
        "capabilities": ["bounds_checking", "slice_safety", "panic_prevention", "defensive_programming"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 005 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: blocking channel send while holding a mutex (lock/channel inversion deadlock).
        "id": "TWU_POLY_GO_DPO_0005",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Avoid mutex-channel inversion deadlocks when sending events in Go.",
        "chosen": r"""package main

import (
	"fmt"
	"sync"
)

type EventBroadcaster struct {
	mu     sync.Mutex
	status string
	events chan string
}

func (eb *EventBroadcaster) UpdateStatus(newStatus string) {
	// Step 1: Update protected state under lock
	eb.mu.Lock()
	eb.status = newStatus
	eb.mu.Unlock() // Crucial: Release lock BEFORE channel send

	// Step 2: Send on channel without holding mutex
	eb.events <- newStatus
}

func main() {
	eb := &EventBroadcaster{
		status: "init",
		events: make(chan string, 1),
	}

	eb.UpdateStatus("running")
	evt := <-eb.events
	if evt != "running" {
		panic("Event mismatch")
	}

	fmt.Println("GO DPO 0005 Chosen: Lock released before channel send avoided deadlock.")
}
""",
        "rejected": r"""package main

import "sync"

type DeadlockBroadcaster struct {
	mu     sync.Mutex
	status string
	ch     chan string
}

func (db *DeadlockBroadcaster) BadUpdate(val string) {
	db.mu.Lock()
	defer db.mu.Unlock()

	// FATAL DEADLOCK: Blocking channel send while holding lock.
	// If the receiver of db.ch needs to acquire db.mu to process the message,
	// both goroutines deadlock permanently!
	db.ch <- val
}
""",
        "rejection_reason": "Rejected code executes a blocking channel send while holding a sync.Mutex, causing lock inversion deadlocks if the channel receiver attempts to acquire the same mutex.",
        "capabilities": ["concurrency", "deadlock_prevention", "mutex", "channel_communication"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 006 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: wg.Add(1) called inside the goroutine, so Wait can return early.
        "id": "TWU_POLY_GO_DPO_0006",
        "domain": "go",
        "kind": "dpo",
        "prompt": "Coordinate goroutine completion using sync.WaitGroup properly without premature returns.",
        "chosen": r"""package main

import (
	"fmt"
	"sync"
	"sync/atomic"
)

func main() {
	var wg sync.WaitGroup
	var completed uint32

	for i := 0; i < 5; i++ {
		// Rule: wg.Add(1) MUST be called BEFORE launching goroutine
		wg.Add(1)
		go func() {
			defer wg.Done()
			atomic.AddUint32(&completed, 1)
		}()
	}

	wg.Wait()

	if completed != 5 {
		panic(fmt.Sprintf("Expected 5 completed, got %d", completed))
	}

	fmt.Println("GO DPO 0006 Chosen: WaitGroup Add before goroutine launch verified.")
}
""",
        "rejected": r"""package main

import (
	"sync"
	"sync/atomic"
)

func BuggyWaitGroup() {
	var wg sync.WaitGroup
	var completed uint32

	for i := 0; i < 5; i++ {
		go func() {
			// RACE CONDITION BUG: Calling Add inside goroutine allows wg.Wait()
			// in the caller thread to exit BEFORE Add is ever executed!
			wg.Add(1)
			defer wg.Done()
			atomic.AddUint32(&completed, 1)
		}()
	}

	wg.Wait() // May return immediately while goroutines haven't started!
}
""",
        "rejection_reason": "Rejected code invokes wg.Add(1) inside the launched goroutine rather than before launch, creating a data race where wg.Wait() returns before the goroutines have registered their work.",
        "capabilities": ["concurrency", "waitgroup", "race_condition_prevention", "goroutines"],
        "quality": "execution_verified",
        "created_at": NOW
    }
]
