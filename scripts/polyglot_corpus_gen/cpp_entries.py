# Program: magi_pact - cpp_entries.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Holds the hand-written C++ training entries (SFT and DPO records) used by the polyglot corpus builder.
"""C++ Language Dataset Entries: 6 SFT + 6 DPO (Total 12)
All chosen/completion programs are compilable with clang++ -std=c++17 -Wall -Wextra -Werror and contain self-testing assertions in main().
"""

from datetime import datetime, timezone

# One timestamp shared by every entry in this module.
NOW = datetime.now(timezone.utc).isoformat()

# Ordered list of records: six SFT (instruction -> completion) then six DPO (prompt, chosen, rejected).
CPP_ENTRIES = [
    # ------------------ SFT 001 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0001",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement a generic thread-safe bounded blocking queue in C++17 using std::mutex, std::condition_variable, and std::unique_lock with graceful shutdown and self-testing assertions across producer/consumer threads in main().",
        "completion": r"""#include <iostream>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>
#include <thread>
#include <vector>
#include <cassert>

template <typename T>
class BoundedBlockingQueue {
public:
    explicit BoundedBlockingQueue(size_t capacity)
        : capacity_(capacity), shutdown_(false) {
        assert(capacity > 0);
    }

    ~BoundedBlockingQueue() {
        close();
    }

    bool push(T item) {
        std::unique_lock<std::mutex> lock(mutex_);
        not_full_.wait(lock, [this]() { return queue_.size() < capacity_ || shutdown_; });
        if (shutdown_) return false;
        queue_.push(std::move(item));
        not_empty_.notify_one();
        return true;
    }

    std::optional<T> pop() {
        std::unique_lock<std::mutex> lock(mutex_);
        not_empty_.wait(lock, [this]() { return !queue_.empty() || shutdown_; });
        if (queue_.empty() && shutdown_) return std::nullopt;
        T item = std::move(queue_.front());
        queue_.pop();
        not_full_.notify_one();
        return item;
    }

    void close() {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            shutdown_ = true;
        }
        not_empty_.notify_all();
        not_full_.notify_all();
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return queue_.size();
    }

private:
    const size_t capacity_;
    std::queue<T> queue_;
    mutable std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
    bool shutdown_;
};

int main() {
    BoundedBlockingQueue<int> q(5);
    long long total_consumed = 0;

    std::thread consumer([&q, &total_consumed]() {
        while (auto val = q.pop()) {
            total_consumed += *val;
        }
    });

    std::thread producer([&q]() {
        for (int i = 1; i <= 50; ++i) {
            bool ok = q.push(i);
            assert(ok);
        }
        q.close();
    });

    producer.join();
    consumer.join();

    // 1 + 2 + ... + 50 = (50 * 51) / 2 = 1275
    assert(total_consumed == 1275);
    assert(q.size() == 0);

    std::cout << "CPP SFT 0001: BoundedBlockingQueue tests passed. Total: " << total_consumed << "\n";
    return 0;
}
""",
        "capabilities": ["concurrency", "cpp17", "blocking_queue", "thread_safety", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 002 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0002",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement a move-only RAII native memory buffer handle adhering to the Rule of Five in C++17, preventing double frees and memory leaks, with self-testing assertions in main().",
        "completion": r"""#include <iostream>
#include <cstdint>
#include <cstring>
#include <utility>
#include <cassert>

class NativeMemoryBuffer {
public:
    explicit NativeMemoryBuffer(size_t size)
        : data_(size > 0 ? new uint8_t[size]() : nullptr), size_(size) {}

    ~NativeMemoryBuffer() {
        delete[] data_;
    }

    // Delete copy operations (move-only)
    NativeMemoryBuffer(const NativeMemoryBuffer&) = delete;
    NativeMemoryBuffer& operator=(const NativeMemoryBuffer&) = delete;

    // Move constructor
    NativeMemoryBuffer(NativeMemoryBuffer&& other) noexcept
        : data_(std::exchange(other.data_, nullptr)),
          size_(std::exchange(other.size_, 0)) {}

    // Move assignment
    NativeMemoryBuffer& operator=(NativeMemoryBuffer&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = std::exchange(other.data_, nullptr);
            size_ = std::exchange(other.size_, 0);
        }
        return *this;
    }

    uint8_t* data() noexcept { return data_; }
    const uint8_t* data() const noexcept { return data_; }
    size_t size() const noexcept { return size_; }
    bool valid() const noexcept { return data_ != nullptr; }

    uint8_t& at(size_t idx) {
        if (idx >= size_ || !data_) {
            throw std::out_of_range("Buffer index out of range");
        }
        return data_[idx];
    }

private:
    uint8_t* data_{nullptr};
    size_t size_{0};
};

int main() {
    NativeMemoryBuffer buf1(64);
    assert(buf1.valid());
    assert(buf1.size() == 64);

    buf1.at(0) = 0xAA;
    buf1.at(63) = 0xBB;
    assert(buf1.at(0) == 0xAA);
    assert(buf1.at(63) == 0xBB);

    // Test move constructor
    NativeMemoryBuffer buf2 = std::move(buf1);
    assert(!buf1.valid());
    assert(buf1.size() == 0);
    assert(buf2.valid());
    assert(buf2.size() == 64);
    assert(buf2.at(0) == 0xAA);
    assert(buf2.at(63) == 0xBB);

    // Test move assignment
    NativeMemoryBuffer buf3(128);
    buf3 = std::move(buf2);
    assert(!buf2.valid());
    assert(buf3.valid());
    assert(buf3.size() == 64);
    assert(buf3.at(0) == 0xAA);

    // Out of range check
    bool caught = false;
    try {
        buf3.at(100);
    } catch (const std::out_of_range&) {
        caught = true;
    }
    assert(caught);

    std::cout << "CPP SFT 0002: RAII move-only buffer tests passed.\n";
    return 0;
}
""",
        "capabilities": ["raii", "rule_of_five", "memory_safety", "move_semantics", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 003 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0003",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement a lock-free Single-Producer Single-Consumer (SPSC) circular queue in C++17 using std::atomic<size_t> with acquire-release memory orderings, cacheline padding, and multi-threaded self-testing assertions in main().",
        "completion": r"""#include <iostream>
#include <atomic>
#include <vector>
#include <thread>
#include <cassert>

template <typename T, size_t Capacity>
class SPSCQueue {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be a power of 2");
public:
    SPSCQueue() : head_(0), tail_(0) {}

    bool push(const T& item) {
        const size_t tail = tail_.load(std::memory_order_relaxed);
        const size_t head = head_.load(std::memory_order_acquire);
        if ((tail - head) == Capacity) {
            return false; // Queue full
        }
        buffer_[tail & (Capacity - 1)] = item;
        tail_.store(tail + 1, std::memory_order_release);
        return true;
    }

    bool pop(T& item) {
        const size_t head = head_.load(std::memory_order_relaxed);
        const size_t tail = tail_.load(std::memory_order_acquire);
        if (head == tail) {
            return false; // Queue empty
        }
        item = buffer_[head & (Capacity - 1)];
        head_.store(head + 1, std::memory_order_release);
        return true;
    }

private:
    T buffer_[Capacity];
    // Separate atomics by 64 bytes to prevent false sharing
    alignas(64) std::atomic<size_t> head_;
    alignas(64) std::atomic<size_t> tail_;
};

int main() {
    SPSCQueue<int, 64> spsc;
    const int count = 5000;
    long long consumed_sum = 0;

    std::thread producer([&spsc]() {
        for (int i = 1; i <= count; ++i) {
            while (!spsc.push(i)) {
                std::this_thread::yield();
            }
        }
    });

    std::thread consumer([&spsc, &consumed_sum]() {
        int item;
        for (int i = 1; i <= count; ++i) {
            while (!spsc.pop(item)) {
                std::this_thread::yield();
            }
            consumed_sum += item;
        }
    });

    producer.join();
    consumer.join();

    long long expected_sum = (static_cast<long long>(count) * (count + 1)) / 2;
    assert(consumed_sum == expected_sum);

    std::cout << "CPP SFT 0003: SPSC lock-free queue test passed. Sum = " << consumed_sum << "\n";
    return 0;
}
""",
        "capabilities": ["concurrency", "lock_free", "atomics", "memory_order", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 004 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0004",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement a safe, non-owning contiguous ArraySpan<T> in C++17 that enforces bounds checks on indexing and subspan slicing with unit tests in main().",
        "completion": r"""#include <iostream>
#include <stdexcept>
#include <cstddef>
#include <cassert>

template <typename T>
class ArraySpan {
public:
    constexpr ArraySpan() noexcept : data_(nullptr), size_(0) {}
    constexpr ArraySpan(T* data, size_t size) noexcept : data_(data), size_(size) {}

    template <size_t N>
    constexpr ArraySpan(T (&arr)[N]) noexcept : data_(arr), size_(N) {}

    constexpr size_t size() const noexcept { return size_; }
    constexpr bool empty() const noexcept { return size_ == 0; }
    constexpr T* data() const noexcept { return data_; }

    T& at(size_t index) const {
        if (index >= size_) {
            throw std::out_of_range("ArraySpan index out of bounds");
        }
        return data_[index];
    }

    T& operator[](size_t index) const {
        return at(index); // Safe indexed access
    }

    ArraySpan<T> subspan(size_t offset, size_t count) const {
        if (offset > size_ || offset + count > size_) {
            throw std::out_of_range("Subspan offset/count exceeds span boundary");
        }
        return ArraySpan<T>(data_ + offset, count);
    }

private:
    T* data_{nullptr};
    size_t size_{0};
};

int main() {
    int raw_array[6] = {10, 20, 30, 40, 50, 60};
    ArraySpan<int> span(raw_array);

    assert(span.size() == 6);
    assert(!span.empty());
    assert(span[0] == 10);
    assert(span[5] == 60);

    // Test subspan
    auto sub = span.subspan(2, 3); // elements 30, 40, 50
    assert(sub.size() == 3);
    assert(sub[0] == 30);
    assert(sub[1] == 40);
    assert(sub[2] == 50);

    // Test bounds enforcement
    bool caught = false;
    try {
        span.at(6);
    } catch (const std::out_of_range&) {
        caught = true;
    }
    assert(caught);

    caught = false;
    try {
        span.subspan(4, 5);
    } catch (const std::out_of_range&) {
        caught = true;
    }
    assert(caught);

    std::cout << "CPP SFT 0004: ArraySpan bounds checking verified.\n";
    return 0;
}
""",
        "capabilities": ["bounds_checking", "span", "memory_safety", "templates", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 005 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0005",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement an asynchronous ThreadPool in C++17 supporting task enqueuing returning std::future, graceful shutdown joining all worker threads, and self-testing assertions in main().",
        "completion": r"""#include <iostream>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <functional>
#include <cassert>

class ThreadPool {
public:
    explicit ThreadPool(size_t num_threads) : stop_(false) {
        for (size_t i = 0; i < num_threads; ++i) {
            workers_.emplace_back([this]() {
                while (true) {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lock(queue_mutex_);
                        condition_.wait(lock, [this]() {
                            return stop_ || !tasks_.empty();
                        });
                        if (stop_ && tasks_.empty()) return;
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();
                }
            });
        }
    }

    template <class F, class... Args>
    auto enqueue(F&& f, Args&&... args)
        -> std::future<typename std::invoke_result<F, Args...>::type> {
        using return_type = typename std::invoke_result<F, Args...>::type;

        auto task = std::make_shared<std::packaged_task<return_type()>>(
            std::bind(std::forward<F>(f), std::forward<Args>(args)...)
        );

        std::future<return_type> res = task->get_future();
        {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            if (stop_) {
                throw std::runtime_error("enqueue called on stopped ThreadPool");
            }
            tasks_.emplace([task]() { (*task)(); });
        }
        condition_.notify_one();
        return res;
    }

    ~ThreadPool() {
        {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            stop_ = true;
        }
        condition_.notify_all();
        for (std::thread& worker : workers_) {
            if (worker.joinable()) {
                worker.join();
            }
        }
    }

private:
    std::vector<std::thread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex queue_mutex_;
    std::condition_variable condition_;
    bool stop_;
};

int main() {
    ThreadPool pool(4);
    std::vector<std::future<int>> results;

    for (int i = 1; i <= 20; ++i) {
        results.push_back(pool.enqueue([i]() {
            return i * i;
        }));
    }

    int total = 0;
    for (size_t i = 0; i < results.size(); ++i) {
        int val = results[i].get();
        int expected = (static_cast<int>(i) + 1) * (static_cast<int>(i) + 1);
        assert(val == expected);
        total += val;
    }

    // Sum of squares 1..20 = (20 * 21 * 41) / 6 = 2870
    assert(total == 2870);
    std::cout << "CPP SFT 0005: ThreadPool execution verified. Sum of squares = " << total << "\n";
    return 0;
}
""",
        "capabilities": ["concurrency", "thread_pool", "futures", "synchronization", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 006 ------------------
    {
        "id": "TWU_POLY_CPP_SFT_0006",
        "domain": "cpp",
        "kind": "sft",
        "prompt": "Implement a thread-safe LRU Cache in C++17 using std::shared_mutex, std::list, and std::unordered_map with capacity eviction and self-testing assertions in main().",
        "completion": r"""#include <iostream>
#include <unordered_map>
#include <list>
#include <shared_mutex>
#include <mutex>
#include <optional>
#include <cassert>

template <typename Key, typename Value>
class ConcurrentLRUCache {
public:
    explicit ConcurrentLRUCache(size_t capacity) : capacity_(capacity) {
        assert(capacity > 0);
    }

    void put(const Key& key, const Value& val) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        auto it = map_.find(key);
        if (it != map_.end()) {
            items_.erase(it->second);
            items_.push_front({key, val});
            it->second = items_.begin();
            return;
        }

        if (items_.size() >= capacity_) {
            auto lru = items_.back();
            map_.erase(lru.first);
            items_.pop_back();
        }

        items_.push_front({key, val});
        map_[key] = items_.begin();
    }

    std::optional<Value> get(const Key& key) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        auto it = map_.find(key);
        if (it == map_.end()) {
            return std::nullopt;
        }
        items_.splice(items_.begin(), items_, it->second);
        return it->second->second;
    }

    size_t size() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return items_.size();
    }

private:
    const size_t capacity_;
    mutable std::shared_mutex mutex_;
    std::list<std::pair<Key, Value>> items_;
    std::unordered_map<Key, typename std::list<std::pair<Key, Value>>::iterator> map_;
};

int main() {
    ConcurrentLRUCache<int, std::string> cache(3);

    cache.put(1, "one");
    cache.put(2, "two");
    cache.put(3, "three");
    assert(cache.size() == 3);

    assert(cache.get(1).value() == "one"); // 1 is now most recently used
    cache.put(4, "four"); // Evicts key 2 (least recently used)

    assert(cache.get(2) == std::nullopt);
    assert(cache.get(1).value() == "one");
    assert(cache.get(3).value() == "three");
    assert(cache.get(4).value() == "four");

    std::cout << "CPP SFT 0006: ConcurrentLRUCache eviction and lookup verified.\n";
    return 0;
}
""",
        "capabilities": ["data_structures", "lru_cache", "shared_mutex", "concurrency", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 001 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0001",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Remove elements satisfying a predicate from a std::vector in C++ safely without iterator invalidation or undefined behavior.",
        "chosen": r"""#include <iostream>
#include <vector>
#include <algorithm>
#include <cassert>

void remove_evens(std::vector<int>& vec) {
    // Erase-remove idiom (or std::erase_if in C++20)
    vec.erase(std::remove_if(vec.begin(), vec.end(), [](int n) {
        return (n % 2) == 0;
    }), vec.end());
}

int main() {
    std::vector<int> nums = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    remove_evens(nums);

    std::vector<int> expected = {1, 3, 5, 7, 9};
    assert(nums == expected);

    std::cout << "CPP DPO 0001 Chosen: Erase-remove idiom safely mutated vector.\n";
    return 0;
}
""",
        "rejected": r"""#include <vector>

void buggy_remove_evens(std::vector<int>& vec) {
    // FATAL BUG: Mutating vector inside range-for invalidates iterators
    for (auto it = vec.begin(); it != vec.end(); ++it) {
        if (*it % 2 == 0) {
            vec.erase(it); // it is now invalidated; ++it causes Undefined Behavior / Crash
        }
    }
}
""",
        "rejection_reason": "Rejected code modifies the vector using erase(it) inside a loop without reassigning the returned iterator, causing iterator invalidation, undefined behavior, and segfaults.",
        "capabilities": ["memory_safety", "iterator_invalidation", "stl", "containers"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 002 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0002",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Acquire multiple mutexes simultaneously without causing deadlocks in C++.",
        "chosen": r"""#include <iostream>
#include <mutex>
#include <thread>
#include <cassert>

class BankAccount {
public:
    explicit BankAccount(int balance) : balance_(balance) {}

    static void transfer(BankAccount& from, BankAccount& to, int amount) {
        // std::scoped_lock acquires multiple locks atomically using deadlock avoidance
        std::scoped_lock lock(from.mutex_, to.mutex_);
        if (from.balance_ >= amount) {
            from.balance_ -= amount;
            to.balance_ += amount;
        }
    }

    int balance() const { return balance_; }

private:
    int balance_;
    std::mutex mutex_;
};

int main() {
    BankAccount acc1(1000);
    BankAccount acc2(1000);

    std::thread t1([&]() {
        for (int i = 0; i < 500; ++i) BankAccount::transfer(acc1, acc2, 1);
    });
    std::thread t2([&]() {
        for (int i = 0; i < 500; ++i) BankAccount::transfer(acc2, acc1, 1);
    });

    t1.join();
    t2.join();

    assert(acc1.balance() + acc2.balance() == 2000);
    std::cout << "CPP DPO 0002 Chosen: Deadlock avoided via std::scoped_lock.\n";
    return 0;
}
""",
        "rejected": r"""#include <mutex>

class Account {
public:
    int balance;
    std::mutex m;

    static void buggy_transfer(Account& from, Account& to, int amt) {
        // Inconsistent lock acquisition order:
        // Thread A: locks from then to.
        // Thread B: locks to then from.
        from.m.lock();
        to.m.lock(); // DEADLOCK occurs when A and B execute concurrently!
        from.balance -= amt;
        to.balance += amt;
        to.m.unlock();
        from.m.unlock();
    }
};
""",
        "rejection_reason": "Rejected code acquires multiple mutexes in arbitrary caller-dependent order without deadlock-avoidance algorithms, resulting in classic circular lock order deadlock.",
        "capabilities": ["concurrency", "deadlock_prevention", "scoped_lock", "mutex"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 003 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0003",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Implement a parent-child tree node relationship in C++ using smart pointers without causing cyclic reference memory leaks.",
        "chosen": r"""#include <iostream>
#include <memory>
#include <vector>
#include <cassert>

struct Node {
    int id;
    std::weak_ptr<Node> parent; // std::weak_ptr prevents reference cycles
    std::vector<std::shared_ptr<Node>> children;

    explicit Node(int val) : id(val) {}
};

int main() {
    std::weak_ptr<Node> weak_child;
    {
        auto root = std::make_shared<Node>(1);
        auto child = std::make_shared<Node>(2);

        child->parent = root;
        root->children.push_back(child);

        weak_child = child;
        assert(weak_child.lock() != nullptr);
        assert(root.use_count() == 1);
        assert(child.use_count() == 2);
    }
    // Both root and child must be destroyed once out of scope
    assert(weak_child.expired());

    std::cout << "CPP DPO 0003 Chosen: Weak pointer cleanly prevents circular reference memory leak.\n";
    return 0;
}
""",
        "rejected": r"""#include <memory>
#include <vector>

struct BadNode {
    int id;
    std::shared_ptr<BadNode> parent; // Cyclic dependency!
    std::vector<std::shared_ptr<BadNode>> children;
    BadNode(int val) : id(val) {}
};

void create_cycle() {
    auto parent = std::make_shared<BadNode>(1);
    auto child = std::make_shared<BadNode>(2);
    parent->children.push_back(child);
    child->parent = parent; // Circular shared_ptr reference: use_count will never hit 0!
    // MEMORY LEAK: destructor is NEVER called!
}
""",
        "rejection_reason": "Rejected code creates a circular reference of std::shared_ptr between parent and child, permanently retaining reference counts and leaking memory.",
        "capabilities": ["memory_safety", "smart_pointers", "memory_leak_prevention", "weak_ptr"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 004 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0004",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Implement lazy thread-safe singleton initialization in C++ adhering to modern standard memory model guarantees.",
        "chosen": r"""#include <iostream>
#include <thread>
#include <vector>
#include <cassert>

class DatabaseConnection {
public:
    static DatabaseConnection& instance() {
        // Meyer's Singleton: C++11 guarantees thread-safe initialization of static locals
        static DatabaseConnection inst;
        return inst;
    }

    int query(int input) {
        return input * factor_;
    }

private:
    DatabaseConnection() : factor_(10) {}
    ~DatabaseConnection() = default;
    DatabaseConnection(const DatabaseConnection&) = delete;
    DatabaseConnection& operator=(const DatabaseConnection&) = delete;

    int factor_;
};

int main() {
    std::vector<std::thread> workers;
    for (int i = 0; i < 4; ++i) {
        workers.emplace_back([]() {
            auto& db = DatabaseConnection::instance();
            assert(db.query(5) == 50);
        });
    }
    for (auto& w : workers) w.join();

    std::cout << "CPP DPO 0004 Chosen: Meyer's singleton thread safety verified.\n";
    return 0;
}
""",
        "rejected": r"""class UnsafeSingleton {
public:
    static UnsafeSingleton* instance() {
        // Unsafe double-checked locking without atomics or memory barriers
        if (instance_ == nullptr) {
            instance_ = new UnsafeSingleton(); // Data race & instruction reordering!
        }
        return instance_;
    }
private:
    UnsafeSingleton() = default;
    static UnsafeSingleton* instance_;
};
UnsafeSingleton* UnsafeSingleton::instance_ = nullptr;
""",
        "rejection_reason": "Rejected code implements double-checked locking with a non-atomic raw pointer, violating the C++ memory model and exposing threads to data races and partial initialization.",
        "capabilities": ["concurrency", "singleton", "memory_model", "thread_safety"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 005 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0005",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Safely format and return a combined string from a function without creating dangling references or string_view lifetime bugs in C++.",
        "chosen": r"""#include <iostream>
#include <string>
#include <cassert>

std::string format_greeting(const std::string& name) {
    // Return by value: Return Value Optimization (RVO) avoids copies safely
    return "Greetings, " + name + "!";
}

int main() {
    std::string msg = format_greeting("Antigravity");
    assert(msg == "Greetings, Antigravity!");
    assert(msg.length() == 23);

    std::cout << "CPP DPO 0005 Chosen: String lifetime and value semantics verified.\n";
    return 0;
}
""",
        "rejected": r"""#include <string>
#include <string_view>

std::string_view broken_greeting(const std::string& name) {
    std::string temp = "Greetings, " + name + "!";
    // FATAL BUG: Returning string_view referencing a destroyed local variable!
    return std::string_view(temp); // Dangling pointer!
}
""",
        "rejection_reason": "Rejected code returns a std::string_view pointing to a local temporary std::string that is destroyed when the function returns, creating a dangling pointer and undefined memory access.",
        "capabilities": ["memory_safety", "lifetime", "dangling_pointer_prevention", "strings"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 006 ------------------
    {
        "id": "TWU_POLY_CPP_DPO_0006",
        "domain": "cpp",
        "kind": "dpo",
        "prompt": "Implement a 2D matrix class in C++ with boundary enforcement on coordinate access to prevent buffer overruns.",
        "chosen": r"""#include <iostream>
#include <vector>
#include <stdexcept>
#include <cassert>

class Matrix2D {
public:
    Matrix2D(size_t rows, size_t cols)
        : rows_(rows), cols_(cols), data_(rows * cols, 0) {
        assert(rows > 0 && cols > 0);
    }

    int& at(size_t r, size_t c) {
        if (r >= rows_ || c >= cols_) {
            throw std::out_of_range("Matrix coordinates out of bounds");
        }
        return data_[r * cols_ + c];
    }

    int at(size_t r, size_t c) const {
        if (r >= rows_ || c >= cols_) {
            throw std::out_of_range("Matrix coordinates out of bounds");
        }
        return data_[r * cols_ + c];
    }

    size_t rows() const { return rows_; }
    size_t cols() const { return cols_; }

private:
    size_t rows_;
    size_t cols_;
    std::vector<int> data_;
};

int main() {
    Matrix2D mat(3, 4);
    mat.at(0, 0) = 10;
    mat.at(2, 3) = 99;

    assert(mat.at(0, 0) == 10);
    assert(mat.at(2, 3) == 99);

    bool caught = false;
    try {
        mat.at(3, 0); // Out of bounds row
    } catch (const std::out_of_range&) {
        caught = true;
    }
    assert(caught);

    caught = false;
    try {
        mat.at(1, 4); // Out of bounds col
    } catch (const std::out_of_range&) {
        caught = true;
    }
    assert(caught);

    std::cout << "CPP DPO 0006 Chosen: Matrix bounds checking verified.\n";
    return 0;
}
""",
        "rejected": r"""class UnsafeMatrix {
public:
    int* data;
    int rows, cols;
    int& get(int r, int c) {
        // Unchecked access: caller can pass negative or out-of-range indices
        return data[r * cols + c]; // Out-of-bounds memory corruption
    }
};
""",
        "rejection_reason": "Rejected code performs direct arithmetic indexing without validating row or column boundaries, enabling arbitrary out-of-bounds heap memory read/write corruption.",
        "capabilities": ["bounds_checking", "matrix", "exception_handling", "memory_safety"],
        "quality": "execution_verified",
        "created_at": NOW
    }
]
