"""Regression: the read-only proxy `chosen` sample had unclosed `function` blocks.

No Lua interpreter is assumed on the test host, so this checks the cheapest
necessary condition for valid Lua: block openers (function/if/for/while) must
balance `end` keywords once strings and comments are stripped. It would have
caught the missing `end` after the __newindex/__pairs/__len metamethods.
"""
import re
import unittest

from pact.lua_engine import LUA_PROBLEMS


# Remove comments and string literals first, so keywords inside text such as
# "end of file" cannot disturb the count.
def _strip_strings_and_comments(src: str) -> str:
    src = re.sub(r"--[^\n]*", "", src)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    return re.sub(r"'(?:\\.|[^'\\])*'", "''", src)


# Net block depth: openers add one, `end` subtracts one; a valid chunk ends at 0.
# (`elseif` and `else` need no entry: they continue an existing block.)
def _balance(src: str) -> int:
    words = re.findall(r"\b(function|if|for|while|end)\b", _strip_strings_and_comments(src))
    return sum(1 if w != "end" else -1 for w in words)


class TestLuaBlockBalance(unittest.TestCase):
    # Applies the necessary-condition check to every reference solution in the corpus.
    def test_chosen_samples_have_balanced_blocks(self):
        for p in LUA_PROBLEMS:
            self.assertEqual(_balance(p.chosen), 0, p.id)

    # Targeted guard for the original bug: metamethod functions inside the table
    # constructor must end with `end,`.
    def test_readonly_proxy_closes_metamethod_functions(self):
        proxy = next(p for p in LUA_PROBLEMS if p.id == "LUA-READONLY-PROXY-01")
        self.assertIn("end,", proxy.chosen)


if __name__ == "__main__":
    unittest.main()
