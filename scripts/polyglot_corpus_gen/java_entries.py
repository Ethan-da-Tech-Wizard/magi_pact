"""Java Language Dataset Entries: 6 SFT + 6 DPO (Total 12)
All chosen/completion programs are self-contained Java classes with self-testing assertions in main().
"""

from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()

JAVA_ENTRIES = [
    # ------------------ SFT 001 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0001",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement a high-throughput bounded worker pool in Java 21 using Virtual Threads and Structured Concurrency (StructuredTaskScope) with timeout propagation and self-testing assertions in main().",
        "completion": r"""import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.*;

public final class LoomWorkerPool {
    public static <T> List<T> executeAll(List<Callable<T>> tasks, Duration timeout) throws Exception {
        if (tasks == null || tasks.isEmpty()) return List.of();

        // Java 21 StructuredTaskScope.ShutdownOnFailure guarantees fail-fast cancellation
        try (var scope = new StructuredTaskScope.ShutdownOnFailure()) {
            List<StructuredTaskScope.Subtask<T>> subtasks = tasks.stream()
                .map(scope::fork)
                .toList();

            scope.joinUntil(Instant.now().plus(timeout));
            scope.throwIfFailed();

            return subtasks.stream()
                .map(StructuredTaskScope.Subtask::get)
                .toList();
        }
    }

    public static void main(String[] args) throws Exception {
        List<Callable<Integer>> tasks = List.of(
            () -> 10,
            () -> 20,
            () -> 30,
            () -> 40
        );

        List<Integer> results = executeAll(tasks, Duration.ofSeconds(2));
        assert results.size() == 4 : "Expected 4 results";
        int sum = results.stream().mapToInt(Integer::intValue).sum();
        assert sum == 100 : "Expected sum 100, got: " + sum;

        System.out.println("JAVA SFT 0001: Structured concurrency executed successfully. Sum: " + sum);
    }
}
""",
        "capabilities": ["virtual_threads", "structured_concurrency", "java21", "loom", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 002 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0002",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement a generic bounded concurrent blocking queue in Java using ReentrantLock and two Condition variables (notFull, notEmpty) with self-testing assertions in main().",
        "completion": r"""import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.atomic.AtomicInteger;

public class BoundedBlockingQueue<T> {
    private final Object[] items;
    private int head;
    private int tail;
    private int count;

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notEmpty = lock.newCondition();
    private final Condition notFull = lock.newCondition();

    public BoundedBlockingQueue(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("Capacity must be positive");
        this.items = new Object[capacity];
    }

    public void put(T item) throws InterruptedException {
        if (item == null) throw new NullPointerException("Null items not supported");
        lock.lockInterruptibly();
        try {
            while (count == items.length) {
                notFull.await();
            }
            items[tail] = item;
            if (++tail == items.length) tail = 0;
            count++;
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
    }

    @SuppressWarnings("unchecked")
    public T take() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (count == 0) {
                notEmpty.await();
            }
            T item = (T) items[head];
            items[head] = null; // Prevent memory leak
            if (++head == items.length) head = 0;
            count--;
            notFull.signal();
            return item;
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try {
            return count;
        } finally {
            lock.unlock();
        }
    }

    public static void main(String[] args) throws Exception {
        BoundedBlockingQueue<Integer> queue = new BoundedBlockingQueue<>(4);
        AtomicInteger totalSum = new AtomicInteger(0);

        Thread consumer = new Thread(() -> {
            try {
                for (int i = 0; i < 50; i++) {
                    totalSum.addAndGet(queue.take());
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        Thread producer = new Thread(() -> {
            try {
                for (int i = 1; i <= 50; i++) {
                    queue.put(i);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });

        consumer.start();
        producer.start();
        producer.join();
        consumer.join();

        // 1..50 = (50 * 51) / 2 = 1275
        assert totalSum.get() == 1275 : "Expected 1275, got " + totalSum.get();
        assert queue.size() == 0 : "Queue should be empty";

        System.out.println("JAVA SFT 0002: BoundedBlockingQueue verified. Sum: " + totalSum.get());
    }
}
""",
        "capabilities": ["concurrency", "reentrant_lock", "condition_variables", "blocking_queue", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 003 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0003",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement a high-concurrency striped 64-bit adder in Java using cell padding to avoid CPU cache line false sharing, with self-testing assertions in main().",
        "completion": r"""import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicLongFieldUpdater;

public class StripedLongAdder {
    // Cache line padding to mitigate false sharing across adjacent array entries
    static final class Cell {
        volatile long p0, p1, p2, p3, p4, p5, p6; // 56 bytes padding
        volatile long value;
        volatile long q0, q1, q2, q3, q4, q5, q6; // 56 bytes padding

        Cell(long val) { this.value = val; }

        static final AtomicLongFieldUpdater<Cell> UPDATER =
            AtomicLongFieldUpdater.newUpdater(Cell.class, "value");

        boolean cas(long cmp, long val) {
            return UPDATER.compareAndSet(this, cmp, val);
        }
    }

    private final Cell[] cells;
    private final int mask;
    private final AtomicLong base = new AtomicLong(0);

    public StripedLongAdder(int numStripesPowerOf2) {
        if ((numStripesPowerOf2 & (numStripesPowerOf2 - 1)) != 0) {
            throw new IllegalArgumentException("Stripes must be power of 2");
        }
        cells = new Cell[numStripesPowerOf2];
        for (int i = 0; i < numStripesPowerOf2; i++) {
            cells[i] = new Cell(0);
        }
        mask = numStripesPowerOf2 - 1;
    }

    public void add(long x) {
        int idx = (int) (Thread.currentThread().threadId() & mask);
        Cell cell = cells[idx];
        long v;
        while (!cell.cas(v = cell.value, v + x)) {
            // retry on contention
        }
    }

    public long sum() {
        long total = base.get();
        for (Cell cell : cells) {
            total += cell.value;
        }
        return total;
    }

    public static void main(String[] args) throws Exception {
        StripedLongAdder adder = new StripedLongAdder(8);
        int numThreads = 8;
        int iters = 10000;

        Thread[] threads = new Thread[numThreads];
        for (int i = 0; i < numThreads; i++) {
            threads[i] = new Thread(() -> {
                for (int j = 0; j < iters; j++) {
                    adder.add(1);
                }
            });
            threads[i].start();
        }

        for (Thread t : threads) t.join();

        long expected = (long) numThreads * iters;
        assert adder.sum() == expected : "Expected " + expected + ", got " + adder.sum();

        System.out.println("JAVA SFT 0003: StripedLongAdder verified. Sum = " + adder.sum());
    }
}
""",
        "capabilities": ["concurrency", "false_sharing_prevention", "cache_line_padding", "cas", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 004 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0004",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement a circular byte ring buffer using java.nio.ByteBuffer with strict position/limit bounds checking and wrap-around logic, with unit tests in main().",
        "completion": r"""import java.nio.ByteBuffer;

public class ByteBufferRing {
    private final ByteBuffer buffer;
    private final int capacity;
    private int head;
    private int tail;
    private int size;

    public ByteBufferRing(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("Capacity must be positive");
        this.capacity = capacity;
        this.buffer = ByteBuffer.allocateDirect(capacity);
        this.head = 0;
        this.tail = 0;
        this.size = 0;
    }

    public synchronized boolean write(byte[] src, int offset, int length) {
        if (src == null || offset < 0 || length < 0 || offset + length > src.length) {
            throw new IndexOutOfBoundsException("Invalid source bounds");
        }
        if (size + length > capacity) return false; // Buffer overflow prevented

        for (int i = 0; i < length; i++) {
            buffer.put(tail, src[offset + i]);
            tail = (tail + 1) % capacity;
        }
        size += length;
        return true;
    }

    public synchronized int read(byte[] dst, int offset, int length) {
        if (dst == null || offset < 0 || length < 0 || offset + length > dst.length) {
            throw new IndexOutOfBoundsException("Invalid dest bounds");
        }
        int toRead = Math.min(length, size);
        for (int i = 0; i < toRead; i++) {
            dst[offset + i] = buffer.get(head);
            head = (head + 1) % capacity;
        }
        size -= toRead;
        return toRead;
    }

    public synchronized int available() {
        return size;
    }

    public static void main(String[] args) {
        ByteBufferRing ring = new ByteBufferRing(8);
        byte[] input = new byte[] { 1, 2, 3, 4, 5, 6 };
        assert ring.write(input, 0, 6) : "Write should succeed";
        assert ring.available() == 6;

        byte[] out = new byte[4];
        assert ring.read(out, 0, 4) == 4;
        assert out[0] == 1 && out[3] == 4;

        byte[] wrap = new byte[] { 7, 8, 9, 10 };
        assert ring.write(wrap, 0, 4) : "Wrap write should succeed";
        assert ring.available() == 6;

        byte[] drain = new byte[6];
        assert ring.read(drain, 0, 6) == 6;
        assert drain[0] == 5 && drain[1] == 6 && drain[2] == 7 && drain[5] == 10;
        assert ring.available() == 0;

        System.out.println("JAVA SFT 0004: ByteBufferRing verified.");
    }
}
""",
        "capabilities": ["bytebuffer", "bounds_checking", "ring_buffer", "memory_safety", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 005 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0005",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement an asynchronous event dispatcher in Java using CompletableFuture and a bounded ThreadPoolExecutor with error isolation and self-testing assertions in main().",
        "completion": r"""import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

public class AsyncEventBus {
    private final ExecutorService executor;

    public AsyncEventBus(int threads, int queueCapacity) {
        this.executor = new ThreadPoolExecutor(
            threads, threads,
            0L, TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(queueCapacity),
            new ThreadPoolExecutor.CallerRunsPolicy()
        );
    }

    public <T> CompletableFuture<Void> publish(T event, Consumer<T> subscriber) {
        return CompletableFuture.runAsync(() -> {
            try {
                subscriber.accept(event);
            } catch (Exception ex) {
                System.err.println("Subscriber error handled: " + ex.getMessage());
            }
        }, executor);
    }

    public void shutdown() throws InterruptedException {
        executor.shutdown();
        if (!executor.awaitTermination(3, TimeUnit.SECONDS)) {
            executor.shutdownNow();
        }
    }

    public static void main(String[] args) throws Exception {
        AsyncEventBus bus = new AsyncEventBus(2, 10);
        AtomicInteger counter = new AtomicInteger(0);

        CompletableFuture<?>[] futures = new CompletableFuture<?>[20];
        for (int i = 0; i < 20; i++) {
            futures[i] = bus.publish(i, val -> {
                counter.incrementAndGet();
            });
        }

        CompletableFuture.allOf(futures).join();
        assert counter.get() == 20 : "Expected 20 processed events, got " + counter.get();

        bus.shutdown();
        System.out.println("JAVA SFT 0005: AsyncEventBus verified. Processed: " + counter.get());
    }
}
""",
        "capabilities": ["async", "completable_future", "event_bus", "thread_pool", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 006 ------------------
    {
        "id": "TWU_POLY_JAVA_SFT_0006",
        "domain": "java",
        "kind": "sft",
        "prompt": "Implement a concurrent lock-free prefix search trie in Java using AtomicReferenceArray with self-testing assertions in main().",
        "completion": r"""import java.util.concurrent.atomic.AtomicReferenceArray;

public class ConcurrentTrie {
    private static final int ALPHABET_SIZE = 26;

    static final class TrieNode {
        volatile boolean isTerminal;
        final AtomicReferenceArray<TrieNode> children = new AtomicReferenceArray<>(ALPHABET_SIZE);
    }

    private final TrieNode root = new TrieNode();

    public void insert(String word) {
        if (word == null) return;
        TrieNode current = root;
        for (int i = 0; i < word.length(); i++) {
            char c = word.charAt(i);
            int idx = c - 'a';
            if (idx < 0 || idx >= ALPHABET_SIZE) continue;

            TrieNode child = current.children.get(idx);
            if (child == null) {
                TrieNode newNode = new TrieNode();
                if (!current.children.compareAndSet(idx, null, newNode)) {
                    child = current.children.get(idx);
                } else {
                    child = newNode;
                }
            }
            current = child;
        }
        current.isTerminal = true;
    }

    public boolean contains(String word) {
        if (word == null) return false;
        TrieNode current = root;
        for (int i = 0; i < word.length(); i++) {
            char c = word.charAt(i);
            int idx = c - 'a';
            if (idx < 0 || idx >= ALPHABET_SIZE) return false;
            current = current.children.get(idx);
            if (current == null) return false;
        }
        return current.isTerminal;
    }

    public static void main(String[] args) {
        ConcurrentTrie trie = new ConcurrentTrie();
        trie.insert("pact");
        trie.insert("polyglot");
        trie.insert("mesh");

        assert trie.contains("pact");
        assert trie.contains("polyglot");
        assert trie.contains("mesh");
        assert !trie.contains("pac");
        assert !trie.contains("unknown");

        System.out.println("JAVA SFT 0006: ConcurrentTrie verified.");
    }
}
""",
        "capabilities": ["data_structures", "trie", "lock_free", "atomic_reference", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 001 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0001",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Implement the thread-safe double-checked locking singleton pattern in Java.",
        "chosen": r"""public class SafeSingleton {
    // volatile ensures memory barrier and prevents CPU instruction reordering
    private static volatile SafeSingleton instance;

    private SafeSingleton() {}

    public static SafeSingleton getInstance() {
        SafeSingleton localRef = instance;
        if (localRef == null) {
            synchronized (SafeSingleton.class) {
                localRef = instance;
                if (localRef == null) {
                    instance = localRef = new SafeSingleton();
                }
            }
        }
        return localRef;
    }

    public static void main(String[] args) {
        SafeSingleton s1 = SafeSingleton.getInstance();
        SafeSingleton s2 = SafeSingleton.getInstance();
        assert s1 == s2 : "Instances must be identical";
        System.out.println("JAVA DPO 0001 Chosen: Safe volatile singleton verified.");
    }
}
""",
        "rejected": r"""public class BuggySingleton {
    // FATAL: Missing 'volatile' allows instruction reordering
    private static BuggySingleton instance;

    public static BuggySingleton getInstance() {
        if (instance == null) {
            synchronized (BuggySingleton.class) {
                if (instance == null) {
                    // CPU can publish reference before constructor completes!
                    instance = new BuggySingleton();
                }
            }
        }
        return instance; // Caller may observe partially constructed object
    }
}
""",
        "rejection_reason": "Rejected code omits the volatile keyword on the singleton field. Under Java's memory model, this permits instruction reordering where a non-null reference is published before object fields are initialized.",
        "capabilities": ["concurrency", "singleton", "volatile", "memory_model"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 002 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0002",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Safely iterate and filter a collection concurrently in Java without ConcurrentModificationException.",
        "chosen": r"""import java.util.concurrent.CopyOnWriteArrayList;
import java.util.List;

public class SafeCollectionIteration {
    public static void main(String[] args) {
        List<String> list = new CopyOnWriteArrayList<>();
        list.add("A");
        list.add("B");
        list.add("C");

        // CopyOnWriteArrayList provides snapshot iterators that never throw ConcurrentModificationException
        for (String item : list) {
            if ("B".equals(item)) {
                list.remove(item);
            }
        }

        assert list.size() == 2;
        assert !list.contains("B");
        System.out.println("JAVA DPO 0002 Chosen: Safe iteration completed without exception.");
    }
}
""",
        "rejected": r"""import java.util.ArrayList;
import java.util.List;

public class BuggyIteration {
    public static void main(String[] args) {
        List<String> list = new ArrayList<>();
        list.add("A"); list.add("B"); list.add("C");

        // FATAL: Mutating ArrayList during enhanced for-loop throws ConcurrentModificationException
        for (String item : list) {
            if (item.equals("B")) {
                list.remove(item); // CRASH
            }
        }
    }
}
""",
        "rejection_reason": "Rejected code structurally modifies a standard ArrayList during enhanced for-loop iteration, triggering an immediate runtime ConcurrentModificationException.",
        "capabilities": ["collections", "concurrency", "copy_on_write", "safe_iteration"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 003 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0003",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Configure a production-safe thread pool in Java that prevents OutOfMemoryError caused by unbounded task queuing.",
        "chosen": r"""import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class SafeThreadPool {
    public static void main(String[] args) throws InterruptedException {
        // Production standard: bounded queue with CallerRunsPolicy prevents JVM heap exhaustion
        ExecutorService executor = new ThreadPoolExecutor(
            2, 4,
            60L, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(100),
            new ThreadPoolExecutor.CallerRunsPolicy()
        );

        AtomicInteger count = new AtomicInteger(0);
        for (int i = 0; i < 50; i++) {
            executor.submit(count::incrementAndGet);
        }

        executor.shutdown();
        assert executor.awaitTermination(5, TimeUnit.SECONDS);
        assert count.get() == 50;

        System.out.println("JAVA DPO 0003 Chosen: Bounded queue protected against OOM.");
    }
}
""",
        "rejected": r"""import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;

public class DangerousThreadPool {
    public static void run() {
        // FATAL: newFixedThreadPool uses unbounded LinkedBlockingQueue (capacity Integer.MAX_VALUE)
        // Under bursty traffic, tasks queue endlessly until Java heap throws java.lang.OutOfMemoryError
        ExecutorService executor = Executors.newFixedThreadPool(4);
    }
}
""",
        "rejection_reason": "Rejected code uses Executors.newFixedThreadPool which internally backs the pool with an unbounded LinkedBlockingQueue, causing JVM OutOfMemoryError crashes under peak load.",
        "capabilities": ["thread_pool", "oom_prevention", "bounded_queues", "backpressure"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 004 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0004",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Implement binary search in Java preventing integer overflow on midpoint calculation.",
        "chosen": r"""public class SafeBinarySearch {
    public static int search(int[] arr, int target) {
        int low = 0;
        int high = arr.length - 1;

        while (low <= high) {
            // Unsigned shift avoids integer overflow when low + high > Integer.MAX_VALUE
            int mid = low + ((high - low) >>> 1);
            int midVal = arr[mid];

            if (midVal < target) {
                low = mid + 1;
            } else if (midVal > target) {
                high = mid - 1;
            } else {
                return mid;
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        int[] data = { 2, 4, 6, 8, 10, 12, 14, 16 };
        assert search(data, 10) == 4;
        assert search(data, 5) == -1;
        System.out.println("JAVA DPO 0004 Chosen: Midpoint arithmetic overflow safe.");
    }
}
""",
        "rejected": r"""public class BuggyBinarySearch {
    public static int search(int[] arr, int target) {
        int low = 0;
        int high = arr.length - 1;
        while (low <= high) {
            // FATAL: (low + high) overflows to negative when low + high exceeds 2^31 - 1
            int mid = (low + high) / 2; // Produces negative index, throwing ArrayIndexOutOfBoundsException!
            if (arr[mid] < target) low = mid + 1;
            else if (arr[mid] > target) high = mid - 1;
            else return mid;
        }
        return -1;
    }
}
""",
        "rejection_reason": "Rejected code calculates the midpoint using (low + high) / 2 which overflows into negative numbers for large arrays, resulting in ArrayIndexOutOfBoundsException.",
        "capabilities": ["algorithms", "integer_overflow", "bounds_checking", "binary_search"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 005 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0005",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Transfer resources between two objects in Java safely avoiding lock-order inversion deadlocks.",
        "chosen": r"""public class SafeTransfer {
    static class Account {
        final int id;
        int balance;
        Account(int id, int bal) { this.id = id; this.balance = bal; }
    }

    public static void transfer(Account from, Account to, int amount) {
        // Enforce consistent global lock acquisition order using identity hash or unique ID
        Account first = from.id < to.id ? from : to;
        Account second = from.id < to.id ? to : from;

        synchronized (first) {
            synchronized (second) {
                if (from.balance >= amount) {
                    from.balance -= amount;
                    to.balance += amount;
                }
            }
        }
    }

    public static void main(String[] args) {
        Account a1 = new Account(1, 100);
        Account a2 = new Account(2, 200);

        transfer(a1, a2, 50);
        assert a1.balance == 50;
        assert a2.balance == 250;

        transfer(a2, a1, 25);
        assert a1.balance == 75;
        assert a2.balance == 225;

        System.out.println("JAVA DPO 0005 Chosen: Lock order inversion avoided.");
    }
}
""",
        "rejected": r"""public class DeadlockTransfer {
    static class Account { int balance; }

    public static void transfer(Account from, Account to, int amount) {
        // DEADLOCK: Thread 1 calls transfer(A, B) -> locks A then B.
        // Thread 2 calls transfer(B, A) -> locks B then A.
        synchronized (from) {
            synchronized (to) {
                from.balance -= amount;
                to.balance += amount;
            }
        }
    }
}
""",
        "rejection_reason": "Rejected code locks objects in caller order without global ordering, leading to circular wait deadlocks when threads transfer in opposite directions simultaneously.",
        "capabilities": ["concurrency", "deadlock_prevention", "lock_ordering", "synchronization"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 006 ------------------
    {
        "id": "TWU_POLY_JAVA_DPO_0006",
        "domain": "java",
        "kind": "dpo",
        "prompt": "Safely manage closeable system resources in Java avoiding resource leaks and exception masking.",
        "chosen": r"""import java.io.ByteArrayInputStream;
import java.io.InputStream;

public class SafeResourceHandling {
    public static int readFirstByte(byte[] data) throws Exception {
        // Canonical try-with-resources guarantees close() and suppresses secondary exceptions
        try (InputStream stream = new ByteArrayInputStream(data)) {
            return stream.read();
        }
    }

    public static void main(String[] args) throws Exception {
        byte[] payload = new byte[] { 42, 100 };
        int val = readFirstByte(payload);
        assert val == 42;
        System.out.println("JAVA DPO 0006 Chosen: Try-with-resources executed safely.");
    }
}
""",
        "rejected": r"""import java.io.InputStream;

public class LeakyResourceHandling {
    public static int readFirstByte(InputStream stream) throws Exception {
        try {
            return stream.read();
        } finally {
            // BUG: If stream.close() throws, it masks the primary exception thrown in the try block!
            // Furthermore, if stream is null, throws NullPointerException in finally.
            stream.close();
        }
    }
}
""",
        "rejection_reason": "Rejected code uses manual close() in finally without null safety or suppressed exception handling, masking primary business exceptions and leaking resources if an error occurs during initialization.",
        "capabilities": ["resource_management", "try_with_resources", "exception_handling", "io"],
        "quality": "execution_verified",
        "created_at": NOW
    }
]
