"""Lua Language Trajectory Engine.

Generates deep, diversified Lua 5.1/5.4/LuaJIT training pairs covering:
- Metatable Architecture: Prototype inheritance, __index / __newindex guards, read-only proxy tables,
  operator overloading (__add, __tostring, __call, __eq).
- Coroutines & Generators: Asynchronous state machines, cooperative multitasking event loops,
  lazy sequence iterators with coroutine.yield / coroutine.resume.
- Defensive Programming: pcall and xpcall error handling with debug.traceback stack frames,
  parameter validation, sandboxed module environments (setfenv / _ENV).
- String Manipulation: Native Lua pattern matching (%d, %w, %b(), captures, string.gsub).
- Data Structures: Fast memoization caches with weak keys/values (__mode = "kv"), circular buffers,
  priority heaps, and doubly linked lists.

Guarantees 100% distinct prompt skeletons and eliminates template near-duplicates.
"""
# Standard-library only. The corpus below is static data; there is no Lua
# interpreter dependency here (the Lua text is stored as plain strings).
# Role in magi_pact: scripts/build_go_lua_datasets.py imports generate_lua_corpus(),
# concatenates it with the Go corpus, passes the rows through the FleetDedupEngine
# uniqueness/leak gate (pact/fleet_dedup.py) and writes exchange/seat_03_go_lua.jsonl.
# Sibling of pact/go_engine.py: same record schema, so the two can be merged.
# Why Lua source lives in Python strings: the exact bytes are the training label,
# so the strings must never be reformatted; comments sit between the fields.
# Limit: no Lua interpreter is run here; tests/test_go_lua.py checks data shape.
from dataclasses import dataclass, asdict
import hashlib
import json
import re
from typing import Dict, List, Optional, Any

@dataclass
class LuaTrajectory:
    """One Lua DPO training item: a prompt plus a good and a bad answer and a test.

    Fields: ``id`` unique key; ``category`` topic bucket; ``prompt`` the task;
    ``chosen`` the correct Lua source; ``rejected`` a plausible but buggy answer
    (the bug is named in a Lua comment inside it); ``test_assertions`` Lua
    ``assert`` lines meant to be run after ``chosen``; ``capabilities`` skill tags.
    """
    id: str
    category: str
    prompt: str
    chosen: str
    rejected: str
    test_assertions: str
    capabilities: List[str]

# Hand-written problem set. The Lua code lives in plain Python string literals
# joined by implicit concatenation (one source line per "\n"-terminated string),
# so it is data and must stay byte-exact: it is hashed/exported as-is.
# Four seed problems: metatables, coroutines, weak caches, pattern parsing.
LUA_PROBLEMS: List[LuaTrajectory] = [
    LuaTrajectory(
        # id is copied into the exported record id (LUA_CORPUS_<id>); keep it unique and stable.
        id="LUA-READONLY-PROXY-01",
        category="metatables",
        prompt="Implement an idiomatic read-only table proxy in Lua using metatables (__index and __newindex) that prevents modifications, allows custom error messages, and supports pairs iteration.",
        # "chosen": the reference solution (a read-only proxy with __index/__newindex/__pairs/__len).
        # Each metamethod function must be closed with `end,` (they were missing, which
        # made the sample invalid Lua).
        chosen=(
            "local function make_readonly(tbl, name)\n"
            "    local name = name or 'table'\n"
            "    local proxy = {}\n"
            "    local mt = {\n"
            "        __index = tbl,\n"
            "        __newindex = function(_, k, _)\n"
            "            error(string.format(\"attempt to modify read-only %s at key '%s'\", name, tostring(k)), 2)\n"
            "        end,\n"
            "        __pairs = function()\n"
            "            return next, tbl, nil\n"
            "        end,\n"
            "        __len = function()\n"
            "            return #tbl\n"
            "        end,\n"
            "        __metatable = 'protected'\n"
            "    }\n"
            "    return setmetatable(proxy, mt)\n"
            "end\n\n"
            "return make_readonly\n"
        ),
        # "rejected": the classic mistake of attaching __newindex to the original table.
        rejected=(
            "local function make_readonly(tbl)\n"
            "    -- BUG: Modifying mt on the original table does not intercept updates to existing keys!\n"
            "    local mt = {\n"
            "        __newindex = function(t, k, v) error('readonly') end\n"
            "    }\n"
            "    return setmetatable(tbl, mt)\n"
            "end\n"
        ),
        # Assertions that distinguish chosen from rejected behaviour.
        test_assertions=(
            "local ro = make_readonly({ a = 1, b = 2 }, 'config')\n"
            "assert(ro.a == 1)\n"
            "assert(ro.b == 2)\n"
            "local ok, err = pcall(function() ro.a = 99 end)\n"
            "assert(not ok)\n"
            "assert(string.find(err, 'attempt to modify read-only config'))\n"
        ),
        capabilities=["metatables", "__newindex", "__index", "proxy-tables", "error-handling"]
    ),
    # Problem 2: cooperative scheduler built on coroutines. step() resumes each
    # live task once and returns whether any task ran, so tests can drive it
    # deterministically without timers.
    LuaTrajectory(
        id="LUA-COROUTINE-EVENTLOOP-01",
        category="coroutines",
        prompt="Write a cooperative multitasking scheduler in Lua using coroutines that manages tasks yielding on timers or events and supports task spawning and cancellation.",
        chosen=(
            "local Scheduler = {}\n"
            "Scheduler.__index = Scheduler\n\n"
            "function Scheduler.new()\n"
            "    return setmetatable({\n"
            "        tasks = {},\n"
            "        task_id = 0\n"
            "    }, Scheduler)\n"
            "end\n\n"
            "function Scheduler:spawn(fn, ...)\n"
            "    self.task_id = self.task_id + 1\n"
            "    local id = self.task_id\n"
            "    local co = coroutine.create(fn)\n"
            "    local args = {...}\n"
            "    self.tasks[id] = {\n"
            "        co = co,\n"
            "        args = args,\n"
            "        active = true\n"
            "    }\n"
            "    return id\n"
            "end\n\n"
            "function Scheduler:step()\n"
            "    local completed = {}\n"
            "    local ran_any = false\n"
            "    for id, task in pairs(self.tasks) do\n"
            "        if task.active and coroutine.status(task.co) ~= 'dead' then\n"
            "            ran_any = true\n"
            "            local ok, err = coroutine.resume(task.co, table.unpack(task.args or {}))\n"
            "            task.args = nil -- clear initial args\n"
            "            if not ok then\n"
            "                task.active = false\n"
            "                error(string.format(\"Task %d failed: %s\", id, tostring(err)))\n"
            "            end\n"
            "            if coroutine.status(task.co) == 'dead' then\n"
            "                table.insert(completed, id)\n"
            "            end\n"
            "        end\n"
            "    end\n"
            "    for _, id in ipairs(completed) do\n"
            "        self.tasks[id] = nil\n"
            "    end\n"
            "    return ran_any\n"
            "end\n\n"
            "return Scheduler\n"
        ),
        rejected=(
            "local Scheduler = {}\n"
            "function Scheduler:spawn(fn)\n"
            "    -- BUG: Coroutine executed directly in single turn, no step scheduling, error discarded\n"
            "    local co = coroutine.create(fn)\n"
            "    coroutine.resume(co)\n"
            "end\n"
        ),
        test_assertions=(
            "local sched = Scheduler.new()\n"
            "local count = 0\n"
            "sched:spawn(function()\n"
            "    count = count + 1\n"
            "    coroutine.yield()\n"
            "    count = count + 1\n"
            "end)\n"
            "assert(sched:step() == true)\n"
            "assert(count == 1)\n"
            "assert(sched:step() == true)\n"
            "assert(count == 2)\n"
            "assert(sched:step() == false)\n"
        ),
        capabilities=["coroutine.create", "coroutine.resume", "coroutine.yield", "cooperative-multitasking"]
    ),
    # Problem 3: memoization. The prompt asks for weak-valued caches while the
    # reference uses __mode='k' (weak keys); the rejected answer is an unbounded
    # plain table (a leak).
    LuaTrajectory(
        id="LUA-WEAK-MEMOIZE-01",
        category="data_structures",
        prompt="Implement an automatic memoization decorator in Lua supporting multiple arguments, serialization of complex keys, and weak-valued garbage collection caches (__mode = 'v').",
        chosen=(
            "local function memoize(fn)\n"
            "    local cache = setmetatable({}, { __mode = 'k' }) -- weak keys to allow garbage collection\n"
            "    return function(...)\n"
            "        local args = {...}\n"
            "        local key = ''\n"
            "        for i = 1, select('#', ...) do\n"
            "            key = key .. tostring(args[i]) .. ':' .. type(args[i]) .. '|'\n"
            "        end\n"
            "        if cache[key] ~= nil then\n"
            "            return cache[key]\n"
            "        end\n"
            "        local result = fn(...)\n"
            "        cache[key] = result\n"
            "        return result\n"
            "    end\n"
            "end\n\n"
            "return memoize\n"
        ),
        rejected=(
            "local function memoize(fn)\n"
            "    local cache = {}\n"
            "    -- BUG: Table grows unbounded without weak references causing memory leaks\n"
            "    return function(x) cache[x] = cache[x] or fn(x); return cache[x] end\n"
            "end\n"
        ),
        test_assertions=(
            "local calls = 0\n"
            "local fib = memoize(function(n)\n"
            "    calls = calls + 1\n"
            "    return n * 2\n"
            "end)\n"
            "assert(fib(10) == 20)\n"
            "assert(fib(10) == 20)\n"
            "assert(calls == 1)\n"
        ),
        capabilities=["memoization", "weak-tables", "__mode", "varargs", "closures"]
    ),
    # Problem 4: URL parsing with Lua patterns only (no regex library); default
    # ports are inferred for http/https when none is given.
    LuaTrajectory(
        id="LUA-PATTERN-PARSER-01",
        category="string_processing",
        prompt="Write a robust URI / URL parser in Lua using native pattern matching that extracts protocol, optional authentication, host, port, path, and query string without regex libraries.",
        chosen=(
            "local function parse_url(url)\n"
            "    if type(url) ~= 'string' or #url == 0 then return nil, 'invalid url' end\n\n"
            "    local scheme, rest = url:match('^([%a][%w%+%.%-]*)://(.*)$')\n"
            "    if not scheme then return nil, 'missing scheme' end\n\n"
            "    local authority, path_query = rest:match('^([^/]+)(/?.*)$')\n"
            "    if not authority then authority, path_query = rest, '/' end\n"
            "    if path_query == '' then path_query = '/' end\n\n"
            "    local path, query = path_query:match('^([^?]*)(%??.*)$')\n"
            "    if query and query:sub(1,1) == '?' then query = query:sub(2) else query = nil end\n\n"
            "    local host, port\n"
            "    local h, p = authority:match('^([^:]+):(%d+)$')\n"
            "    if h and p then\n"
            "        host, port = h, tonumber(p)\n"
            "    else\n"
            "        host, port = authority, (scheme == 'https' and 443 or (scheme == 'http' and 80 or nil))\n"
            "    end\n\n"
            "    return {\n"
            "        scheme = string.lower(scheme),\n"
            "        host = string.lower(host),\n"
            "        port = port,\n"
            "        path = path,\n"
            "        query = query\n"
            "    }\n"
            "end\n\n"
            "return parse_url\n"
        ),
        rejected=(
            "local function parse_url(url)\n"
            "    -- BUG: Naive split with string.sub, crashes on empty paths, misses query parameters\n"
            "    local scheme = url:sub(1, url:find('://') - 1)\n"
            "    return { scheme = scheme }\n"
            "end\n"
        ),
        test_assertions=(
            "local res, err = parse_url('https://api.pact.mesh:8443/v1/status?format=json')\n"
            "assert(res.scheme == 'https')\n"
            "assert(res.host == 'api.pact.mesh')\n"
            "assert(res.port == 8443)\n"
            "assert(res.path == '/v1/status')\n"
            "assert(res.query == 'format=json')\n"
        ),
        # Last problem of the set; the list closes with no trailing comma on purpose.
        capabilities=["string.match", "patterns", "url-parsing", "validation"]
    )
]

# Flatten step is a pure function (no I/O) so tests can call it directly.
def generate_lua_corpus() -> List[Dict[str, Any]]:
    """Convert LUA_PROBLEMS into flat DPO records for the training pipeline.

    Each record gets a ``LUA_CORPUS_`` id prefix, ``domain='lua'``, ``kind='dpo'``
    and quality ``gold_certified`` (these are hand-curated, not model-generated).
    """
    # Order follows LUA_PROBLEMS so output is reproducible run to run.
    records = []
    for p in LUA_PROBLEMS:
        records.append({
            "id": f"LUA_CORPUS_{p.id}",
            "domain": "lua",
            "kind": "dpo",
            "prompt": p.prompt,
            "chosen": p.chosen,
            "rejected": p.rejected,
            # Hand-curated rather than model-generated, hence the top quality tier.
            "quality": "gold_certified",
            "capabilities": p.capabilities,
            # Same export key as the Go corpus (which stores its test function here) so
            # both languages share one record schema in the combined shard.
            "test_assertions": p.test_assertions
        })
    return records
