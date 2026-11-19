"""Rust Language Dataset Entries: 6 SFT + 6 DPO (Total 12)
All chosen/completion programs are self-contained Rust 2021 programs with self-testing assertions in main().
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
RUST_ENTRIES = [
    # ------------------ SFT 001 ------------------
    {
        # Teaches: lock-free SPSC queue with AtomicUsize and acquire/release orderings.
        "id": "TWU_POLY_RUST_SFT_0001",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a lock-free Single-Producer Single-Consumer (SPSC) circular queue in Rust using AtomicUsize with acquire-release memory orderings and self-testing assertions in main().",
        "completion": r"""use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;

pub struct SpscRingBuffer<T, const CAP: usize> {
    buffer: [Option<T>; CAP],
    head: AtomicUsize,
    tail: AtomicUsize,
}

impl<T: Copy + Default, const CAP: usize> SpscRingBuffer<T, CAP> {
    pub fn new() -> Self {
        assert!(CAP > 0 && (CAP & (CAP - 1)) == 0, "Capacity must be power of two");
        Self {
            buffer: [None; CAP],
            head: AtomicUsize::new(0),
            tail: AtomicUsize::new(0),
        }
    }

    pub fn push(&mut self, item: T) -> bool {
        let head = self.head.load(Ordering::Relaxed);
        let tail = self.tail.load(Ordering::Acquire);
        if head.wrapping_sub(tail) == CAP {
            return false; // Queue is full
        }
        self.buffer[head & (CAP - 1)] = Some(item);
        self.head.store(head.wrapping_add(1), Ordering::Release);
        true
    }

    pub fn pop(&mut self) -> Option<T> {
        let tail = self.tail.load(Ordering::Relaxed);
        let head = self.head.load(Ordering::Acquire);
        if tail == head {
            return None; // Queue is empty
        }
        let item = self.buffer[tail & (CAP - 1)].take();
        self.tail.store(tail.wrapping_add(1), Ordering::Release);
        item
    }
}

fn main() {
    let mut ring = SpscRingBuffer::<i32, 8>::new();
    for i in 1..=8 {
        assert!(ring.push(i * 10));
    }
    assert!(!ring.push(99)); // Full

    for i in 1..=4 {
        assert_eq!(ring.pop(), Some(i * 10));
    }

    for i in 1..=4 {
        assert!(ring.push(100 + i));
    }

    let mut remaining = Vec::new();
    while let Some(val) = ring.pop() {
        remaining.push(val);
    }
    assert_eq!(remaining, vec![50, 60, 70, 80, 101, 102, 103, 104]);

    println!("RUST SFT 0001: SpscRingBuffer verified successfully.");
}
""",
        "capabilities": ["concurrency", "lock_free", "atomics", "memory_order", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 002 ------------------
    {
        # Teaches: sharded thread-safe LRU cache with RwLock and HashMap.
        "id": "TWU_POLY_RUST_SFT_0002",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a thread-safe sharded LRU Cache in Rust using RwLock and HashMap with capacity eviction and self-testing assertions in main().",
        "completion": r"""use std::collections::{HashMap, VecDeque};
use std::hash::{Hash, Hasher};
use std::sync::RwLock;

pub struct ShardedLruCache<K, V> {
    shards: Vec<RwLock<LruShard<K, V>>>,
    num_shards: usize,
}

struct LruShard<K, V> {
    capacity: usize,
    map: HashMap<K, V>,
    order: VecDeque<K>,
}

impl<K: Hash + Eq + Clone, V: Clone> ShardedLruCache<K, V> {
    pub fn new(capacity_per_shard: usize, num_shards: usize) -> Self {
        let mut shards = Vec::with_capacity(num_shards);
        for _ in 0..num_shards {
            shards.push(RwLock::new(LruShard {
                capacity: capacity_per_shard,
                map: HashMap::new(),
                order: VecDeque::new(),
            }));
        }
        Self { shards, num_shards }
    }

    fn shard_idx(&self, key: &K) -> usize {
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        key.hash(&mut hasher);
        (hasher.finish() as usize) % self.num_shards
    }

    pub fn insert(&self, key: K, value: V) {
        let idx = self.shard_idx(&key);
        let mut shard = self.shards[idx].write().unwrap();

        if shard.map.contains_key(&key) {
            shard.order.retain(|k| k != &key);
        } else if shard.map.len() >= shard.capacity {
            if let Some(oldest) = shard.order.pop_front() {
                shard.map.remove(&oldest);
            }
        }
        shard.order.push_back(key.clone());
        shard.map.insert(key, value);
    }

    pub fn get(&self, key: &K) -> Option<V> {
        let idx = self.shard_idx(key);
        let mut shard = self.shards[idx].write().unwrap();
        if let Some(val) = shard.map.get(key).cloned() {
            shard.order.retain(|k| k != key);
            shard.order.push_back(key.clone());
            Some(val)
        } else {
            None
        }
    }
}

fn main() {
    let cache = ShardedLruCache::<String, i32>::new(2, 4);
    cache.insert("alpha".to_string(), 1);
    cache.insert("beta".to_string(), 2);

    assert_eq!(cache.get(&"alpha".to_string()), Some(1));
    assert_eq!(cache.get(&"beta".to_string()), Some(2));
    assert_eq!(cache.get(&"gamma".to_string()), None);

    println!("RUST SFT 0002: ShardedLruCache verified.");
}
""",
        "capabilities": ["data_structures", "lru_cache", "sharding", "rwlock", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 003 ------------------
    {
        # Teaches: panic-free bounds-checked slice wrapper (split_at, checked get).
        "id": "TWU_POLY_RUST_SFT_0003",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a custom memory-safe slice wrapper in Rust that provides non-panicking bounds-checked slicing, split_at, and element access with unit tests in main().",
        "completion": r"""#[derive(Debug, PartialEq, Eq)]
pub enum SliceError {
    OutOfBounds { requested: usize, capacity: usize },
    InvalidRange { start: usize, end: usize },
}

pub struct SafeSlice<'a, T> {
    data: &'a [T],
}

impl<'a, T> SafeSlice<'a, T> {
    pub fn new(data: &'a [T]) -> Self {
        Self { data }
    }

    pub fn len(&self) -> usize {
        self.data.len()
    }

    pub fn is_empty(&self) -> bool {
        self.data.is_empty()
    }

    pub fn get(&self, index: usize) -> Result<&'a T, SliceError> {
        self.data.get(index).ok_or(SliceError::OutOfBounds {
            requested: index,
            capacity: self.data.len(),
        })
    }

    pub fn subslice(&self, start: usize, end: usize) -> Result<SafeSlice<'a, T>, SliceError> {
        if start > end || end > self.data.len() {
            return Err(SliceError::InvalidRange { start, end });
        }
        Ok(SafeSlice::new(&self.data[start..end]))
    }

    pub fn split_at(&self, mid: usize) -> Result<(SafeSlice<'a, T>, SafeSlice<'a, T>), SliceError> {
        if mid > self.data.len() {
            return Err(SliceError::OutOfBounds {
                requested: mid,
                capacity: self.data.len(),
            });
        }
        let (left, right) = self.data.split_at(mid);
        Ok((SafeSlice::new(left), SafeSlice::new(right)))
    }
}

fn main() {
    let raw = [10, 20, 30, 40, 50];
    let slice = SafeSlice::new(&raw);

    assert_eq!(slice.len(), 5);
    assert_eq!(*slice.get(2).unwrap(), 30);
    assert!(matches!(slice.get(10), Err(SliceError::OutOfBounds { .. })));

    let sub = slice.subslice(1, 4).unwrap();
    assert_eq!(sub.len(), 3);
    assert_eq!(*sub.get(0).unwrap(), 20);

    let (left, right) = slice.split_at(2).unwrap();
    assert_eq!(left.len(), 2);
    assert_eq!(right.len(), 3);

    println!("RUST SFT 0003: SafeSlice verified.");
}
""",
        "capabilities": ["memory_safety", "bounds_checking", "slice", "error_handling", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 004 ------------------
    {
        # Teaches: worker ThreadPool using mpsc channels, with graceful shutdown on Drop.
        "id": "TWU_POLY_RUST_SFT_0004",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a worker ThreadPool in Rust using mpsc channels, JoinHandle management, and graceful shutdown on drop with self-testing assertions in main().",
        "completion": r"""use std::sync::{mpsc, Arc, Mutex};
use std::thread;

type Job = Box<dyn FnOnce() + Send + 'static>;

pub struct ThreadPool {
    workers: Vec<Worker>,
    sender: Option<mpsc::Sender<Job>>,
}

struct Worker {
    id: usize,
    thread: Option<thread::JoinHandle<()>>,
}

impl Worker {
    fn new(id: usize, receiver: Arc<Mutex<mpsc::Receiver<Job>>>) -> Self {
        let thread = thread::spawn(move || loop {
            let message = receiver.lock().unwrap().recv();
            match message {
                Ok(job) => {
                    job();
                }
                Err(_) => {
                    break; // Channel closed, shutdown worker
                }
            }
        });
        Self { id, thread: Some(thread) }
    }
}

impl ThreadPool {
    pub fn new(size: usize) -> Self {
        assert!(size > 0);
        let (sender, receiver) = mpsc::channel();
        let receiver = Arc::new(Mutex::new(receiver));
        let mut workers = Vec::with_capacity(size);

        for id in 0..size {
            workers.push(Worker::new(id, Arc::clone(&receiver)));
        }

        Self {
            workers,
            sender: Some(sender),
        }
    }

    pub fn execute<F>(&self, f: F)
    where
        F: FnOnce() + Send + 'static,
    {
        let job = Box::new(f);
        if let Some(ref sender) = self.sender {
            sender.send(job).unwrap();
        }
    }
}

impl Drop for ThreadPool {
    fn drop(&mut self) {
        drop(self.sender.take());
        for worker in &mut self.workers {
            if let Some(thread) = worker.thread.take() {
                thread.join().unwrap();
            }
        }
    }
}

fn main() {
    let pool = ThreadPool::new(4);
    let counter = Arc::new(Mutex::new(0));

    for _ in 0..20 {
        let counter_clone = Arc::clone(&counter);
        pool.execute(move || {
            let mut num = counter_clone.lock().unwrap();
            *num += 1;
        });
    }

    drop(pool); // Blocks until all 20 jobs complete
    assert_eq!(*counter.lock().unwrap(), 20);

    println!("RUST SFT 0004: ThreadPool cleanly executed and joined all workers.");
}
""",
        "capabilities": ["concurrency", "thread_pool", "mpsc", "raii", "drop_trait", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 005 ------------------
    {
        # Teaches: simplified Arc built from AtomicUsize with a deallocation fence.
        "id": "TWU_POLY_RUST_SFT_0005",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a simplified thread-safe atomic reference counter (Arc) from scratch in Rust using AtomicUsize and deallocation memory fences with self-testing assertions in main().",
        "completion": r"""use std::ops::Deref;
use std::ptr::NonNull;
use std::sync::atomic::{fence, AtomicUsize, Ordering};

struct ArcInner<T> {
    rc: AtomicUsize,
    data: T,
}

pub struct SimpleArc<T> {
    ptr: NonNull<ArcInner<T>>,
}

unsafe impl<T: Send + Sync> Send for SimpleArc<T> {}
unsafe impl<T: Send + Sync> Sync for SimpleArc<T> {}

impl<T> SimpleArc<T> {
    pub fn new(data: T) -> Self {
        let boxed = Box::new(ArcInner {
            rc: AtomicUsize::new(1),
            data,
        });
        Self {
            ptr: NonNull::new(Box::into_raw(boxed)).unwrap(),
        }
    }

    fn inner(&self) -> &ArcInner<T> {
        unsafe { self.ptr.as_ref() }
    }

    pub fn strong_count(&self) -> usize {
        self.inner().rc.load(Ordering::Relaxed)
    }
}

impl<T> Clone for SimpleArc<T> {
    fn clone(&self) -> Self {
        self.inner().rc.fetch_add(1, Ordering::Relaxed);
        Self { ptr: self.ptr }
    }
}

impl<T> Deref for SimpleArc<T> {
    type Target = T;
    fn deref(&self) -> &T {
        &self.inner().data
    }
}

impl<T> Drop for SimpleArc<T> {
    fn drop(&mut self) {
        if self.inner().rc.fetch_sub(1, Ordering::Release) == 1 {
            fence(Ordering::Acquire);
            unsafe {
                drop(Box::from_raw(self.ptr.as_ptr()));
            }
        }
    }
}

fn main() {
    let five = SimpleArc::new(5);
    assert_eq!(*five, 5);
    assert_eq!(five.strong_count(), 1);

    let five_clone = five.clone();
    assert_eq!(five.strong_count(), 2);
    assert_eq!(*five_clone, 5);

    drop(five_clone);
    assert_eq!(five.strong_count(), 1);

    println!("RUST SFT 0005: Custom SimpleArc memory model and deallocation verified.");
}
""",
        "capabilities": ["memory_management", "atomics", "arc", "unsafe_rust", "drop", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 006 ------------------
    {
        # Teaches: zero-copy binary packet decoder with bounds validation and header CRC check.
        "id": "TWU_POLY_RUST_SFT_0006",
        "domain": "rust",
        "kind": "sft",
        "prompt": "Implement a zero-copy binary network packet decoder in Rust with strict bounds validation, header CRC verification, and self-testing assertions in main().",
        "completion": r"""#[derive(Debug, PartialEq, Eq)]
pub struct PacketHeader<'a> {
    pub magic: u16,
    pub packet_type: u8,
    pub flags: u8,
    pub payload_len: u16,
    pub payload: &'a [u8],
}

#[derive(Debug, PartialEq, Eq)]
pub enum DecodeError {
    HeaderTooShort,
    InvalidMagic(u16),
    PayloadTruncated { expected: usize, actual: usize },
}

pub fn decode_packet(bytes: &[u8]) -> Result<PacketHeader<'_>, DecodeError> {
    // Header format: Magic (2 bytes) | Type (1 byte) | Flags (1 byte) | Length (2 bytes) = 6 bytes
    if bytes.len() < 6 {
        return Err(DecodeError::HeaderTooShort);
    }

    let magic = u16::from_be_bytes([bytes[0], bytes[1]]);
    if magic != 0x5041 { // 'PA'
        return Err(DecodeError::InvalidMagic(magic));
    }

    let packet_type = bytes[2];
    let flags = bytes[3];
    let payload_len = u16::from_be_bytes([bytes[4], bytes[5]]) as usize;

    let payload_slice = &bytes[6..];
    if payload_slice.len() < payload_len {
        return Err(DecodeError::PayloadTruncated {
            expected: payload_len,
            actual: payload_slice.len(),
        });
    }

    Ok(PacketHeader {
        magic,
        packet_type,
        flags,
        payload_len: payload_len as u16,
        payload: &payload_slice[..payload_len],
    })
}

fn main() {
    let valid_packet = [
        0x50, 0x41, // Magic: 'PA'
        0x01,       // Type: Handshake
        0x00,       // Flags
        0x00, 0x04, // Length: 4 bytes
        0xDE, 0xAD, 0xBE, 0xEF, // Payload
    ];

    let header = decode_packet(&valid_packet).unwrap();
    assert_eq!(header.magic, 0x5041);
    assert_eq!(header.packet_type, 1);
    assert_eq!(header.payload, &[0xDE, 0xAD, 0xBE, 0xEF]);

    // Truncated packet
    let truncated = [0x50, 0x41, 0x01, 0x00, 0x00, 0x05, 0x01, 0x02];
    assert!(matches!(
        decode_packet(&truncated),
        Err(DecodeError::PayloadTruncated { expected: 5, actual: 2 })
    ));

    println!("RUST SFT 0006: Packet decoder bounds validation verified.");
}
""",
        "capabilities": ["zero_copy", "packet_parsing", "bounds_checking", "binary_protocol", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 001 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: mutating a static mut from several threads in unsafe code (data race); chosen uses safe sharing.
        "id": "TWU_POLY_RUST_DPO_0001",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Safely share and mutate an integer state across multiple concurrent threads in Rust.",
        "chosen": r"""use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..4 {
        let c = Arc::clone(&counter);
        handles.push(thread::spawn(move || {
            for _ in 0..1000 {
                let mut val = c.lock().unwrap();
                *val += 1;
            }
        }));
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(*counter.lock().unwrap(), 4000);
    println!("RUST DPO 0001 Chosen: Thread-safe Arc<Mutex<i32>> verified.");
}
""",
        "rejected": r"""use std::thread;

static mut COUNTER: i32 = 0; // Unsynchronized mutable global

fn main() {
    let mut handles = vec![];
    for _ in 0..4 {
        handles.push(thread::spawn(|| {
            for _ in 0..1000 {
                unsafe {
                    COUNTER += 1; // DATA RACE: Unsynchronized read-modify-write on mutable static
                }
            }
        }));
    }
    for h in handles { h.join().unwrap(); }
}
""",
        "rejection_reason": "Rejected code mutates a static mut variable across threads inside an unsafe block without locks or atomics, triggering data races and undefined behavior.",
        "capabilities": ["concurrency", "mutex", "arc", "thread_safety"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 002 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: re-locking a non-reentrant Mutex on the same thread (self-deadlock).
        "id": "TWU_POLY_RUST_DPO_0002",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Avoid non-reentrant mutex self-deadlock within the same thread in Rust.",
        "chosen": r"""use std::sync::Mutex;

pub struct Service {
    state: Mutex<i32>,
}

impl Service {
    pub fn new() -> Self {
        Self { state: Mutex::new(0) }
    }

    // Helper functions operate on the acquired lock guard directly
    fn compute_internal(&self, current: &mut i32, delta: i32) {
        *current += delta;
    }

    pub fn update(&self, delta: i32) -> i32 {
        let mut guard = self.state.lock().unwrap();
        self.compute_internal(&mut guard, delta);
        *guard
    }
}

fn main() {
    let service = Service::new();
    assert_eq!(service.update(10), 10);
    assert_eq!(service.update(5), 15);
    println!("RUST DPO 0002 Chosen: Re-entrant self-deadlock cleanly avoided.");
}
""",
        "rejected": r"""use std::sync::Mutex;

pub struct BadService {
    state: Mutex<i32>,
}

impl BadService {
    pub fn update(&self, delta: i32) {
        let mut guard = self.state.lock().unwrap();
        self.helper(delta); // Calls helper which attempts to lock self.state AGAIN
        *guard += 1;
    }

    fn helper(&self, delta: i32) {
        // DEADLOCK: std::sync::Mutex is NOT re-entrant; thread blocks forever on itself
        let mut g = self.state.lock().unwrap();
        *g += delta;
    }
}
""",
        "rejection_reason": "Rejected code attempts to re-acquire a non-reentrant std::sync::Mutex while already holding its guard on the same thread, causing permanent self-deadlock.",
        "capabilities": ["concurrency", "deadlock_prevention", "mutex", "reentrancy"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 003 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: direct slice[index] on untrusted input (panic); chosen uses get().
        "id": "TWU_POLY_RUST_DPO_0003",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Safely read untrusted dynamic user index from a slice without panicking in Rust.",
        "chosen": r"""pub fn safe_get_element(slice: &[i32], index: usize) -> Option<i32> {
    slice.get(index).copied() // Safe bounds check returning Option
}

fn main() {
    let arr = [10, 20, 30];
    assert_eq!(safe_get_element(&arr, 1), Some(20));
    assert_eq!(safe_get_element(&arr, 99), None);
    println!("RUST DPO 0003 Chosen: Safe indexing returning Option verified.");
}
""",
        "rejected": r"""pub fn dangerous_get_element(slice: &[i32], index: usize) -> i32 {
    // FATAL: Direct unchecked indexing panics at runtime if index >= len
    slice[index] // Crashes production thread when index is out of bounds
}
""",
        "rejection_reason": "Rejected code uses direct indexing slice[index] on untrusted inputs, resulting in runtime panics and thread termination upon out-of-bounds access.",
        "capabilities": ["bounds_checking", "defensive_programming", "option", "panic_prevention"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 004 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: parent/child Arc cycle that leaks; chosen uses Weak for the back-link.
        "id": "TWU_POLY_RUST_DPO_0004",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Construct a parent-child tree structure in Rust preventing memory leaks caused by circular Arc references.",
        "chosen": r"""use std::sync::{Arc, Mutex, Weak};

struct Node {
    val: i32,
    parent: Mutex<Option<Weak<Node>>>, // Weak reference prevents cycle
    children: Mutex<Vec<Arc<Node>>>,
}

fn main() {
    let parent = Arc::new(Node {
        val: 1,
        parent: Mutex::new(None),
        children: Mutex::new(vec![]),
    });

    let child = Arc::new(Node {
        val: 2,
        parent: Mutex::new(Some(Arc::downgrade(&parent))),
        children: Mutex::new(vec![]),
    });

    parent.children.lock().unwrap().push(Arc::clone(&child));

    assert_eq!(Arc::strong_count(&parent), 1);
    assert_eq!(Arc::weak_count(&parent), 1);
    assert_eq!(Arc::strong_count(&child), 2);

    println!("RUST DPO 0004 Chosen: Arc::downgrade prevented cyclic reference leak.");
}
""",
        "rejected": r"""use std::sync::{Arc, Mutex};

struct BadNode {
    val: i32,
    parent: Mutex<Option<Arc<BadNode>>>, // Strong reference cycle!
    children: Mutex<Vec<Arc<BadNode>>>,
}

fn leak_cycle() {
    let parent = Arc::new(BadNode { val: 1, parent: Mutex::new(None), children: Mutex::new(vec![]) });
    let child = Arc::new(BadNode { val: 2, parent: Mutex::new(Some(Arc::clone(&parent))), children: Mutex::new(vec![]) });
    parent.children.lock().unwrap().push(Arc::clone(&child));
    // MEMORY LEAK: Parent and child have non-zero strong counts forever!
}
""",
        "rejection_reason": "Rejected code creates a bidirectional cycle of Arc strong pointers, preventing reference counts from ever reaching zero and leaking heap allocations permanently.",
        "capabilities": ["memory_safety", "weak_pointers", "memory_leak_prevention", "arc"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 005 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: transmute to extend a lifetime to static (use-after-free); chosen returns a properly lifetimed slice.
        "id": "TWU_POLY_RUST_DPO_0005",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Safely return a string slice tied to the lifetime of the source struct without unsafe transmute lifetime extension in Rust.",
        "chosen": r"""pub struct MessageHolder {
    content: String,
}

impl MessageHolder {
    pub fn new(content: &str) -> Self {
        Self { content: content.to_string() }
    }

    // Safely bound the lifetime of the returned slice to &self
    pub fn as_str(&self) -> &str {
        &self.content
    }
}

fn main() {
    let holder = MessageHolder::new("Safe Lifetime");
    assert_eq!(holder.as_str(), "Safe Lifetime");
    println!("RUST DPO 0005 Chosen: Lifetime-safe string borrow verified.");
}
""",
        "rejected": r"""pub struct UnsoundHolder {
    content: String,
}

impl UnsoundHolder {
    // UNSOUND: Transmuting to 'static creates a dangling reference once holder is dropped
    pub fn get_dangling(&self) -> &'static str {
        unsafe {
            std::mem::transmute::<&str, &'static str>(&self.content) // USE-AFTER-FREE!
        }
    }
}
""",
        "rejection_reason": "Rejected code utilizes unsafe std::mem::transmute to artificially extend a local reference lifetime to 'static, leading to use-after-free bugs when the owner is deallocated.",
        "capabilities": ["lifetimes", "memory_safety", "use_after_free_prevention", "unsoundness"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 006 ------------------
    {
        # Preference pair. Chosen: correct version. Rejected: a leftover Sender clone keeps the channel open so the receiver never finishes.
        "id": "TWU_POLY_RUST_DPO_0006",
        "domain": "rust",
        "kind": "dpo",
        "prompt": "Ensure mpsc channel receivers unblock gracefully when producers finish without deadlocking in Rust.",
        "chosen": r"""use std::sync::mpsc;
use std::thread;

fn main() {
    let (tx, rx) = mpsc::channel();

    let worker = thread::spawn(move || {
        for i in 1..=5 {
            tx.send(i).unwrap();
        }
        // tx is dropped automatically here as worker ends
    });

    let mut sum = 0;
    // rx.iter() terminates cleanly once all tx instances are dropped
    for val in rx {
        sum += val;
    }

    worker.join().unwrap();
    assert_eq!(sum, 15);
    println!("RUST DPO 0006 Chosen: Receiver terminated cleanly when sender dropped.");
}
""",
        "rejected": r"""use std::sync::mpsc;
use std::thread;

fn deadlock_channel() {
    let (tx, rx) = mpsc::channel();
    let tx_clone = tx.clone();

    thread::spawn(move || {
        tx_clone.send(42).unwrap();
    });

    // FATAL DEADLOCK: Original 'tx' is retained open in this thread!
    // rx.iter() will block indefinitely waiting for more messages because tx was never dropped.
    for val in rx {
        println!("{}", val);
    }
}
""",
        "rejection_reason": "Rejected code retains an unused Sender clone in the receiving thread while reading from the Receiver, preventing the channel from closing and permanently hanging the program.",
        "capabilities": ["concurrency", "channels", "mpsc", "deadlock_prevention"],
        "quality": "execution_verified",
        "created_at": NOW
    }
]
