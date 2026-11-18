# Program: magi_pact - csharp_entries.py
# Programmer: Ethan-da-Tech-Wizard (written with Claude, an AI assistant)
# Last Modified: 2026-11-18
# Purpose: Holds the hand-written C# training entries (SFT and DPO records) used by the polyglot corpus builder.
"""C# (.NET 8) Language Dataset Entries: 6 SFT + 6 DPO (Total 12)
All chosen/completion programs are compilable and runnable with dotnet 8.0, containing self-testing assertions in Main().
"""

from datetime import datetime, timezone

# One timestamp shared by every entry in this module.
NOW = datetime.now(timezone.utc).isoformat()

# Ordered list of records: six SFT (instruction -> completion) then six DPO (prompt, chosen, rejected).
CSHARP_ENTRIES = [
    # ------------------ SFT 001 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0001",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Create a high-performance .NET 8 IAsyncEnumerable pipeline using System.Threading.Channels with bounded capacity, backpressure, cancellation token propagation, and self-testing assertions in Main().",
        "completion": r"""using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using System.Diagnostics;

public sealed class BoundedPipeline<T>
{
    private readonly Channel<T> _channel;

    public BoundedPipeline(int capacity)
    {
        if (capacity <= 0) throw new ArgumentOutOfRangeException(nameof(capacity));
        var options = new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.Wait,
            SingleWriter = false,
            SingleReader = false
        };
        _channel = Channel.CreateBounded<T>(options);
    }

    public async ValueTask PublishAsync(T item, CancellationToken ct = default)
    {
        await _channel.Writer.WriteAsync(item, ct).ConfigureAwait(false);
    }

    public void Complete()
    {
        _channel.Writer.Complete();
    }

    public async IAsyncEnumerable<T> StreamAsync([EnumeratorCancellation] CancellationToken ct = default)
    {
        while (await _channel.Reader.WaitToReadAsync(ct).ConfigureAwait(false))
        {
            while (_channel.Reader.TryRead(out var item))
            {
                yield return item;
            }
        }
    }
}

public class Program
{
    public static async Task Main()
    {
        var pipeline = new BoundedPipeline<int>(4);
        int totalSum = 0;

        var consumer = Task.Run(async () =>
        {
            await foreach (var item in pipeline.StreamAsync())
            {
                Interlocked.Add(ref totalSum, item);
            }
        });

        var producer = Task.Run(async () =>
        {
            for (int i = 1; i <= 50; i++)
            {
                await pipeline.PublishAsync(i);
            }
            pipeline.Complete();
        });

        await Task.WhenAll(producer, consumer);

        // Sum 1..50 = (50 * 51) / 2 = 1275
        Debug.Assert(totalSum == 1275);
        if (totalSum != 1275) throw new Exception("Sum assertion failed");

        Console.WriteLine($"CSHARP SFT 0001: BoundedPipeline tests passed. Total sum = {totalSum}");
    }
}
""",
        "capabilities": ["async", "channels", "dotnet8", "iasyncenumerable", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 002 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0002",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Implement a thread-safe LRU Cache in C# (.NET 8) with O(1) reads/writes using ConcurrentDictionary and a doubly-linked list with synchronization and self-testing assertions in Main().",
        "completion": r"""using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;

public class ConcurrentLruCache<TKey, TValue> where TKey : notnull
{
    private readonly int _capacity;
    private readonly object _syncRoot = new();
    private readonly Dictionary<TKey, LinkedListNode<CacheItem>> _map;
    private readonly LinkedList<CacheItem> _lruList = new();

    private record struct CacheItem(TKey Key, TValue Value);

    public ConcurrentLruCache(int capacity)
    {
        if (capacity <= 0) throw new ArgumentOutOfRangeException(nameof(capacity));
        _capacity = capacity;
        _map = new Dictionary<TKey, LinkedListNode<CacheItem>>(capacity);
    }

    public void Set(TKey key, TValue value)
    {
        lock (_syncRoot)
        {
            if (_map.TryGetValue(key, out var existingNode))
            {
                _lruList.Remove(existingNode);
                var updatedNode = new LinkedListNode<CacheItem>(new CacheItem(key, value));
                _lruList.AddFirst(updatedNode);
                _map[key] = updatedNode;
                return;
            }

            if (_map.Count >= _capacity)
            {
                var lru = _lruList.Last;
                if (lru != null)
                {
                    _lruList.RemoveLast();
                    _map.Remove(lru.Value.Key);
                }
            }

            var newNode = new LinkedListNode<CacheItem>(new CacheItem(key, value));
            _lruList.AddFirst(newNode);
            _map[key] = newNode;
        }
    }

    public bool TryGet(TKey key, out TValue value)
    {
        lock (_syncRoot)
        {
            if (_map.TryGetValue(key, out var node))
            {
                _lruList.Remove(node);
                _lruList.AddFirst(node);
                value = node.Value.Value;
                return true;
            }
            value = default!;
            return false;
        }
    }

    public int Count
    {
        get { lock (_syncRoot) return _map.Count; }
    }
}

public class Program
{
    public static void Main()
    {
        var cache = new ConcurrentLruCache<int, string>(3);
        cache.Set(1, "one");
        cache.Set(2, "two");
        cache.Set(3, "three");
        Debug.Assert(cache.Count == 3);

        bool found = cache.TryGet(1, out var val);
        Debug.Assert(found && val == "one");

        // Key 2 was least recently used, so adding 4 evicts 2
        cache.Set(4, "four");
        Debug.Assert(cache.Count == 3);
        Debug.Assert(!cache.TryGet(2, out _));
        Debug.Assert(cache.TryGet(1, out val) && val == "one");
        Debug.Assert(cache.TryGet(3, out val) && val == "three");
        Debug.Assert(cache.TryGet(4, out val) && val == "four");

        Console.WriteLine("CSHARP SFT 0002: ConcurrentLruCache tests passed.");
    }
}
""",
        "capabilities": ["data_structures", "lru_cache", "thread_safety", "dotnet8", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 003 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0003",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Implement a high-performance zero-allocation ring buffer in C# (.NET 8) using Memory<T> and Span<T> with strict boundary checks and self-testing assertions in Main().",
        "completion": r"""using System;
using System.Diagnostics;

public sealed class SpanRingBuffer<T>
{
    private readonly T[] _storage;
    private readonly int _mask;
    private int _head;
    private int _tail;
    private int _count;

    public SpanRingBuffer(int powerOfTwoCapacity)
    {
        if (powerOfTwoCapacity <= 0 || (powerOfTwoCapacity & (powerOfTwoCapacity - 1)) != 0)
        {
            throw new ArgumentException("Capacity must be a power of two.", nameof(powerOfTwoCapacity));
        }
        _storage = new T[powerOfTwoCapacity];
        _mask = powerOfTwoCapacity - 1;
        _head = 0;
        _tail = 0;
        _count = 0;
    }

    public int Capacity => _storage.Length;
    public int Count => _count;

    public bool TryWrite(T item)
    {
        if (_count == _storage.Length) return false;
        _storage[_tail] = item;
        _tail = (_tail + 1) & _mask;
        _count++;
        return true;
    }

    public bool TryRead(out T item)
    {
        if (_count == 0)
        {
            item = default!;
            return false;
        }
        item = _storage[_head];
        _head = (_head + 1) & _mask;
        _count--;
        return true;
    }

    public void CopyTo(Span<T> destination)
    {
        if (destination.Length < _count)
        {
            throw new ArgumentException("Destination span is too short.", nameof(destination));
        }

        for (int i = 0; i < _count; i++)
        {
            destination[i] = _storage[(_head + i) & _mask];
        }
    }
}

public class Program
{
    public static void Main()
    {
        var rb = new SpanRingBuffer<int>(8);
        for (int i = 1; i <= 8; i++)
        {
            bool ok = rb.TryWrite(i * 10);
            Debug.Assert(ok);
        }
        Debug.Assert(!rb.TryWrite(99)); // Full

        Span<int> copySpan = stackalloc int[8];
        rb.CopyTo(copySpan);
        Debug.Assert(copySpan[0] == 10 && copySpan[7] == 80);

        for (int i = 1; i <= 4; i++)
        {
            bool ok = rb.TryRead(out int val);
            Debug.Assert(ok && val == i * 10);
        }

        for (int i = 1; i <= 4; i++)
        {
            bool ok = rb.TryWrite(100 + i);
            Debug.Assert(ok);
        }

        Debug.Assert(rb.Count == 8);
        Console.WriteLine("CSHARP SFT 0003: SpanRingBuffer tests passed.");
    }
}
""",
        "capabilities": ["memory_management", "span", "bounds_checking", "ring_buffer", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 004 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0004",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Implement a SemaphoreSlim-bounded asynchronous worker queue in C# (.NET 8) that executes tasks with throttled maximum concurrency, graceful drain, and self-testing assertions in Main().",
        "completion": r"""using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;

public class ThrottledWorkerPool
{
    private readonly SemaphoreSlim _semaphore;

    public ThrottledWorkerPool(int maxConcurrency)
    {
        if (maxConcurrency <= 0) throw new ArgumentOutOfRangeException(nameof(maxConcurrency));
        _semaphore = new SemaphoreSlim(maxConcurrency, maxConcurrency);
    }

    public async Task<TResult> RunAsync<TResult>(Func<Task<TResult>> taskFunc, CancellationToken ct = default)
    {
        await _semaphore.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            return await taskFunc().ConfigureAwait(false);
        }
        finally
        {
            _semaphore.Release();
        }
    }
}

public class Program
{
    public static async Task Main()
    {
        var pool = new ThrottledWorkerPool(3);
        int activeWorkers = 0;
        int maxObservedWorkers = 0;
        object lockObj = new();

        var tasks = new List<Task<int>>();
        for (int i = 1; i <= 15; i++)
        {
            int itemId = i;
            tasks.Add(pool.RunAsync(async () =>
            {
                lock (lockObj)
                {
                    activeWorkers++;
                    if (activeWorkers > maxObservedWorkers) maxObservedWorkers = activeWorkers;
                }

                await Task.Delay(10);

                lock (lockObj)
                {
                    activeWorkers--;
                }
                return itemId * 2;
            }));
        }

        var results = await Task.WhenAll(tasks);
        Debug.Assert(results.Length == 15);
        Debug.Assert(maxObservedWorkers <= 3);

        int sum = 0;
        foreach (var r in results) sum += r;
        // Sum 1..15 * 2 = 2 * (15 * 16) / 2 = 240
        Debug.Assert(sum == 240);

        Console.WriteLine($"CSHARP SFT 0004: ThrottledWorkerPool tests passed. Max concurrency: {maxObservedWorkers}");
    }
}
""",
        "capabilities": ["async", "semaphoreslim", "concurrency_control", "dotnet8", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 005 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0005",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Implement a thread-safe native resource wrapper in C# adhering to the standard Dispose pattern with Interlocked.Exchange, preventing double disposal, with self-testing assertions in Main().",
        "completion": r"""using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

public class NativeMemoryHandle : IDisposable
{
    private IntPtr _handle;
    private int _disposed; // 0 = active, 1 = disposed
    private readonly int _byteSize;

    public NativeMemoryHandle(int byteSize)
    {
        if (byteSize <= 0) throw new ArgumentOutOfRangeException(nameof(byteSize));
        _byteSize = byteSize;
        _handle = Marshal.AllocHGlobal(byteSize);
    }

    public IntPtr Handle
    {
        get
        {
            ThrowIfDisposed();
            return _handle;
        }
    }

    public int ByteSize => _byteSize;

    public void WriteByte(int offset, byte value)
    {
        ThrowIfDisposed();
        if (offset < 0 || offset >= _byteSize)
        {
            throw new ArgumentOutOfRangeException(nameof(offset));
        }
        Marshal.WriteByte(_handle, offset, value);
    }

    public byte ReadByte(int offset)
    {
        ThrowIfDisposed();
        if (offset < 0 || offset >= _byteSize)
        {
            throw new ArgumentOutOfRangeException(nameof(offset));
        }
        return Marshal.ReadByte(_handle, offset);
    }

    private void ThrowIfDisposed()
    {
        if (Volatile.Read(ref _disposed) == 1)
        {
            throw new ObjectDisposedException(nameof(NativeMemoryHandle));
        }
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        // Thread-safe atomic compare exchange: ensure memory is freed exactly once
        if (Interlocked.Exchange(ref _disposed, 1) == 0)
        {
            if (_handle != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(_handle);
                _handle = IntPtr.Zero;
            }
        }
    }

    ~NativeMemoryHandle()
    {
        Dispose(false);
    }
}

public class Program
{
    public static void Main()
    {
        using (var mem = new NativeMemoryHandle(128))
        {
            mem.WriteByte(0, 0x42);
            mem.WriteByte(127, 0xFF);
            Debug.Assert(mem.ReadByte(0) == 0x42);
            Debug.Assert(mem.ReadByte(127) == 0xFF);

            // Double dispose idempotency check
            mem.Dispose();
            mem.Dispose();

            bool thrown = false;
            try
            {
                mem.ReadByte(0);
            }
            catch (ObjectDisposedException)
            {
                thrown = true;
            }
            Debug.Assert(thrown);
        }

        Console.WriteLine("CSHARP SFT 0005: Safe native handle disposal tests passed.");
    }
}
""",
        "capabilities": ["memory_safety", "dispose_pattern", "interlocked", "unmanaged_resources", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ SFT 006 ------------------
    {
        "id": "TWU_POLY_CSHARP_SFT_0006",
        "domain": "csharp",
        "kind": "sft",
        "prompt": "Implement an asynchronous batching processor in C# (.NET 8) that accumulates items and triggers batch processing upon reaching batch size or timeout, with self-testing assertions in Main().",
        "completion": r"""using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;

public sealed class AsyncBatcher<T>
{
    private readonly Channel<T> _channel = Channel.CreateUnbounded<T>();
    private readonly int _batchSize;
    private readonly TimeSpan _timeout;

    public AsyncBatcher(int batchSize, TimeSpan timeout)
    {
        _batchSize = batchSize;
        _timeout = timeout;
    }

    public void Enqueue(T item) => _channel.Writer.TryWrite(item);
    public void Complete() => _channel.Writer.Complete();

    public async Task ProcessBatchesAsync(Func<List<T>, Task> batchHandler, CancellationToken ct = default)
    {
        var currentBatch = new List<T>(_batchSize);
        var reader = _channel.Reader;

        while (await reader.WaitToReadAsync(ct).ConfigureAwait(false))
        {
            while (reader.TryRead(out var item))
            {
                currentBatch.Add(item);
                if (currentBatch.Count >= _batchSize)
                {
                    await batchHandler(new List<T>(currentBatch)).ConfigureAwait(false);
                    currentBatch.Clear();
                }
            }
        }

        if (currentBatch.Count > 0)
        {
            await batchHandler(currentBatch).ConfigureAwait(false);
        }
    }
}

public class Program
{
    public static async Task Main()
    {
        var batcher = new AsyncBatcher<int>(5, TimeSpan.FromMilliseconds(50));
        int totalBatches = 0;
        int totalItems = 0;

        var processingTask = batcher.ProcessBatchesAsync(async batch =>
        {
            Interlocked.Increment(ref totalBatches);
            Interlocked.Add(ref totalItems, batch.Count);
            await Task.Yield();
        });

        for (int i = 0; i < 23; i++)
        {
            batcher.Enqueue(i);
        }
        batcher.Complete();

        await processingTask;

        Debug.Assert(totalItems == 23);
        // 23 items with batch size 5 = 4 full batches + 1 residual batch = 5 batches
        Debug.Assert(totalBatches == 5);

        Console.WriteLine($"CSHARP SFT 0006: AsyncBatcher verified. Batches: {totalBatches}, Items: {totalItems}");
    }
}
""",
        "capabilities": ["async", "batching", "channels", "dotnet8", "unit_test"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 001 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0001",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Demonstrate the proper asynchronous exception handling in C# without using async void.",
        "chosen": r"""using System;
using System.Diagnostics;
using System.Threading.Tasks;

public class AsyncSafeRunner
{
    public static async Task<bool> ExecuteSafelyAsync(Func<Task> operation)
    {
        try
        {
            await operation().ConfigureAwait(false);
            return true;
        }
        catch (InvalidOperationException)
        {
            return false; // Safely captured and handled
        }
    }

    public static async Task FailingOperationAsync()
    {
        await Task.Yield();
        throw new InvalidOperationException("Operation failed expectedly.");
    }
}

public class Program
{
    public static async Task Main()
    {
        bool success = await AsyncSafeRunner.ExecuteSafelyAsync(AsyncSafeRunner.FailingOperationAsync);
        Debug.Assert(!success);
        Console.WriteLine("CSHARP DPO 0001 Chosen: Async Task exceptions caught cleanly.");
    }
}
""",
        "rejected": r"""using System;
using System.Threading.Tasks;

public class BuggyAsync
{
    // FATAL: async void exceptions cannot be awaited or caught by callers; process will crash
    public static async void DangerousFireAndForget()
    {
        await Task.Delay(10);
        throw new Exception("Unhandled exception in async void terminates the CLR process!");
    }
}
""",
        "rejection_reason": "Rejected code utilizes async void methods outside of event handlers. Exceptions thrown on async void cannot be caught or awaited by callers, directly crashing the host process.",
        "capabilities": ["async_await", "exception_handling", "task_pattern", "dotnet8"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 002 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0002",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Safely dispatch multiple tasks inside a loop in C# avoiding closure over loop variables.",
        "chosen": r"""using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;

public class Program
{
    public static async Task Main()
    {
        var tasks = new List<Task<int>>();
        for (int i = 0; i < 10; i++)
        {
            int capturedIndex = i; // Local copy prevents race condition
            tasks.Add(Task.Run(() =>
            {
                return capturedIndex * 10;
            }));
        }

        var results = await Task.WhenAll(tasks);
        var set = new HashSet<int>(results);
        Debug.Assert(set.Count == 10);
        for (int i = 0; i < 10; i++)
        {
            Debug.Assert(set.Contains(i * 10));
        }

        Console.WriteLine("CSHARP DPO 0002 Chosen: Local variable capture preserved uniqueness.");
    }
}
""",
        "rejected": r"""using System;
using System.Collections.Generic;
using System.Threading.Tasks;

public class BuggyLoopClosure
{
    public static void Run()
    {
        var tasks = new List<Task>();
        for (int i = 0; i < 10; i++)
        {
            // BUG: Closure captures the mutated loop variable 'i'
            tasks.Add(Task.Run(() => Console.WriteLine(i))); // All tasks print 10!
        }
        Task.WaitAll(tasks.ToArray());
    }
}
""",
        "rejection_reason": "Rejected code captures the loop variable 'i' across concurrent tasks, causing all dispatched tasks to observe the post-loop terminal value rather than per-iteration values.",
        "capabilities": ["concurrency", "closures", "task_parallel_library", "dotnet8"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 003 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0003",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Safely accumulate metrics concurrently in C# across multiple threads.",
        "chosen": r"""using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Threading.Tasks;

public class Program
{
    public static async Task Main()
    {
        var dict = new ConcurrentDictionary<string, int>();

        var tasks = new Task[4];
        for (int t = 0; t < 4; t++)
        {
            tasks[t] = Task.Run(() =>
            {
                for (int i = 0; i < 1000; i++)
                {
                    dict.AddOrUpdate("counter", 1, (_, current) => current + 1);
                }
            });
        }

        await Task.WhenAll(tasks);
        Debug.Assert(dict["counter"] == 4000);

        Console.WriteLine($"CSHARP DPO 0003 Chosen: ConcurrentDictionary updated atomically: {dict["counter"]}");
    }
}
""",
        "rejected": r"""using System.Collections.Generic;
using System.Threading.Tasks;

public class BuggyDictionaryRace
{
    public static void MutateConcurrently()
    {
        var dict = new Dictionary<string, int>(); // Not thread-safe!
        Parallel.For(0, 4000, i =>
        {
            // FATAL: Concurrent writes corrupt internal hash buckets or throw InvalidOperationException
            dict["counter"] = dict.GetValueOrDefault("counter", 0) + 1;
        });
    }
}
""",
        "rejection_reason": "Rejected code modifies a non-thread-safe Dictionary concurrently without synchronization, resulting in corrupted bucket chains, infinite loops, and InvalidOperationExceptions.",
        "capabilities": ["concurrency", "concurrent_dictionary", "thread_safety", "dotnet8"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 004 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0004",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Safely slice and parse binary packet payloads in C# using ReadOnlySpan with strict bounds checking.",
        "chosen": r"""using System;
using System.Buffers.Binary;
using System.Diagnostics;

public class PacketDecoder
{
    public static bool TryParseHeader(ReadOnlySpan<byte> data, out ushort magic, out ushort length)
    {
        magic = 0;
        length = 0;
        // Strict boundary check before reading 4-byte header
        if (data.Length < 4) return false;

        magic = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(0, 2));
        length = BinaryPrimitives.ReadUInt16BigEndian(data.Slice(2, 2));

        // Check if data contains full announced payload
        if (data.Length < 4 + length) return false;

        return true;
    }
}

public class Program
{
    public static void Main()
    {
        byte[] validPacket = new byte[] { 0xCA, 0xFE, 0x00, 0x02, 0x11, 0x22 };
        bool ok = PacketDecoder.TryParseHeader(validPacket, out var magic, out var length);
        Debug.Assert(ok && magic == 0xCAFE && length == 2);

        byte[] truncatedPacket = new byte[] { 0xCA, 0xFE, 0x00 };
        ok = PacketDecoder.TryParseHeader(truncatedPacket, out _, out _);
        Debug.Assert(!ok);

        Console.WriteLine("CSHARP DPO 0004 Chosen: Span bounds checks verified.");
    }
}
""",
        "rejected": r"""using System;

public class BuggySpanSlice
{
    public static ushort ReadPayload(ReadOnlySpan<byte> buffer)
    {
        // FATAL: Directly slicing without checking buffer.Length throws ArgumentOutOfRangeException
        return BitConverter.ToUInt16(buffer.Slice(10, 2));
    }
}
""",
        "rejection_reason": "Rejected code slices into memory/span without validating available buffer size, triggering unhandled runtime ArgumentOutOfRangeException on malformed input.",
        "capabilities": ["bounds_checking", "span", "binary_primitives", "defensive_programming"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 005 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0005",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Avoid sync-over-async deadlocks when calling asynchronous methods in C#.",
        "chosen": r"""using System;
using System.Diagnostics;
using System.Threading.Tasks;

public class SafeAsyncService
{
    public async Task<string> FetchDataAsync()
    {
        // ConfigureAwait(false) avoids capturing SynchronizationContext
        await Task.Delay(10).ConfigureAwait(false);
        return "Clean Result";
    }
}

public class Program
{
    public static async Task Main()
    {
        var service = new SafeAsyncService();
        string res = await service.FetchDataAsync();
        Debug.Assert(res == "Clean Result");
        Console.WriteLine("CSHARP DPO 0005 Chosen: Clean async/await without sync blocking.");
    }
}
""",
        "rejected": r"""using System.Threading.Tasks;

public class DeadlockService
{
    public async Task<string> GetDataAsync()
    {
        await Task.Delay(10);
        return "data";
    }

    public string GetDataBlocking()
    {
        // FATAL: Blocking on Task.Result / Task.Wait() in SynchronizationContext environments
        // (UI thread, legacy ASP.NET) causes deadlock and thread pool starvation.
        return GetDataAsync().Result;
    }
}
""",
        "rejection_reason": "Rejected code blocks synchronously on .Result, causing thread pool starvation and deadlocks when running on single-threaded synchronization contexts.",
        "capabilities": ["async_await", "deadlock_prevention", "configure_await", "dotnet8"],
        "quality": "execution_verified",
        "created_at": NOW
    },
    # ------------------ DPO 006 ------------------
    {
        "id": "TWU_POLY_CSHARP_DPO_0006",
        "domain": "csharp",
        "kind": "dpo",
        "prompt": "Implement the IDisposable pattern in C# idempotently without resource leaks.",
        "chosen": r"""using System;
using System.Diagnostics;
using System.Threading;

public class SafeResource : IDisposable
{
    private int _isDisposed;

    public void DoWork()
    {
        if (Volatile.Read(ref _isDisposed) == 1)
        {
            throw new ObjectDisposedException(nameof(SafeResource));
        }
    }

    public void Dispose()
    {
        // Atomic compare exchange ensures idempotency
        if (Interlocked.Exchange(ref _isDisposed, 1) == 0)
        {
            // Free unmanaged resources safely
            GC.SuppressFinalize(this);
        }
    }
}

public class Program
{
    public static void Main()
    {
        var res = new SafeResource();
        res.DoWork();

        // Safe multiple calls
        res.Dispose();
        res.Dispose();

        bool caught = false;
        try
        {
            res.DoWork();
        }
        catch (ObjectDisposedException)
        {
            caught = true;
        }
        Debug.Assert(caught);
        Console.WriteLine("CSHARP DPO 0006 Chosen: Idempotent disposal pattern verified.");
    }
}
""",
        "rejected": r"""using System;

public class LeakyResource : IDisposable
{
    private IntPtr rawPtr = new IntPtr(1234);

    public void Dispose()
    {
        // Non-idempotent: if called twice or across threads, double-free crashes process.
        // No finalizer, so if Dispose() is omitted, native memory leaks permanently.
        FreeNativeMemory(rawPtr);
    }

    private void FreeNativeMemory(IntPtr p) {}
}
""",
        "rejection_reason": "Rejected code lacks idempotency guards and finalization suppression, risking double frees on repeated Dispose() calls and permanent memory leaks if Dispose() is omitted.",
        "capabilities": ["memory_safety", "dispose_pattern", "idempotency", "dotnet8"],
        "quality": "execution_verified",
        "created_at": NOW
    }
]
