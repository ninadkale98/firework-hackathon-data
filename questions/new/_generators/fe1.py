from common import *

README = '''# web-shop: product search

The search page lists products as the user types.

- `SearchPage` keeps the text in the box (`query`) and the "In stock only" box.
- `useSearch(query, inStockOnly)` calls the search API once the text is at least
  2 characters and returns the results, the total, a loading flag and an error.
- `GET /api/search?q=...&inStock=...&limit=20` returns
  `{ query, total, items }`; `query` echoes the `q` it was sent.

Short queries match many products and are slower on the server (a two-letter
query can take more than a second); long queries usually answer in about 200 ms.

React 19.3, TypeScript 7.0, Vite. `npm run typecheck` and `npm test` run on
every pull request.
'''

PACKAGE = '''{
  "name": "web-shop",
  "private": true,
  "version": "2.41.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "19.3.0",
    "react-dom": "19.3.0"
  },
  "devDependencies": {
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "typescript": "7.0.2",
    "vite": "8.1.0",
    "vitest": "5.0.3"
  }
}
'''

SEARCH_API = '''export interface Product {
  id: string;
  name: string;
  price: number;
  inStock: boolean;
}

export interface SearchResponse {
  query: string;
  total: number;
  items: Product[];
}

export async function searchProducts(
  query: string,
  inStockOnly: boolean,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, inStock: String(inStockOnly), limit: "20" });
  const res = await fetch(`/api/search?${params}`, { signal });
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}
'''

USE_SEARCH = '''import { useEffect, useState } from "react";
import { searchProducts, type Product } from "../api/search";

export function useSearch(query: string, inStockOnly: boolean) {
  const [results, setResults] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setTotal(0);
      return;
    }
    setLoading(true);
    setError(null);
    searchProducts(query, inStockOnly)
      .then((res) => {
        setResults(res.items);
        setTotal(res.total);
      })
      .catch(() => setError("Search failed. Try again."))
      .finally(() => setLoading(false));
  }, [query, inStockOnly]);

  return { results, total, loading, error };
}
'''

SEARCH_PAGE = '''import { useState } from "react";
import { useSearch } from "./useSearch";

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [inStockOnly, setInStockOnly] = useState(false);
  const { results, total, loading, error } = useSearch(query, inStockOnly);

  return (
    <section className="search">
      <input
        type="search"
        aria-label="Search products"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <label>
        <input type="checkbox" checked={inStockOnly} onChange={(e) => setInStockOnly(e.target.checked)} />
        In stock only
      </label>
      {loading && <p className="spinner">Searching...</p>}
      {error && <p role="alert">{error}</p>}
      {query.trim().length >= 2 && (
        <h2>
          Results for "{query}" <small>{total} results</small>
        </h2>
      )}
      <ul>
        {results.map((p) => (
          <li key={p.id}>
            {p.name} <span className="price">{p.price.toFixed(2)}</span>
            {!p.inStock && <span className="badge">Out of stock</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
'''

files = {
    "README.md": README,
    "package.json": PACKAGE,
    "src/api/search.ts": SEARCH_API,
    "src/search/SearchPage.tsx": SEARCH_PAGE,
    "src/search/useSearch.ts": USE_SEARCH,
}

# ---- one typing session: keys, requests, arrival order -------------------
keys = [(0, "l"), (110, "a"), (230, "p"), (340, "t"), (460, "o"), (570, "p"), (700, " "),
        (820, "s"), (930, "t"), (1040, "a"), (1150, "n"), (1260, "d")]
durations = {"la": 1420, "lap": 1840, "lapt": 610, "lapto": 420, "laptop": 390, "laptop ": 380,
             "laptop s": 300, "laptop st": 260, "laptop sta": 240, "laptop stan": 230, "laptop stand": 220}
totals = {"la": 1904, "lap": 312, "lapt": 96, "lapto": 94, "laptop": 94, "laptop ": 94,
          "laptop s": 31, "laptop st": 22, "laptop sta": 19, "laptop stan": 18, "laptop stand": 18}
first = {"la": "Lab coat, white", "lap": "Lap desk with cushion", "lapt": "Laptop sleeve, 13 inch",
         "lapto": "Laptop sleeve, 13 inch", "laptop": "Laptop sleeve, 13 inch", "laptop ": "Laptop sleeve, 13 inch",
         "laptop s": "Laptop stand, aluminium", "laptop st": "Laptop stand, aluminium",
         "laptop sta": "Laptop stand, aluminium", "laptop stan": "Laptop stand, aluminium",
         "laptop stand": "Laptop stand, aluminium"}


def session(delay):
    text, reqs = "", []
    for t, k in keys:
        text += k
        if len(text.strip()) >= 2:
            start = t + delay
            reqs.append((text, start, durations[text], start + durations[text]))
    return reqs


def log(reqs, title_lines):
    q = lambda s: s.replace(" ", "+")
    out = list(title_lines)
    out.append("")
    out.append("Key presses (from a keydown listener added for this recording), ms:")
    out.append("  " + " | ".join(f"{t} {'(space)' if k == ' ' else k}" for t, k in keys))
    out.append("")
    out.append(f"{'#':<3} {'Request':<54} {'Start':>6} {'Took':>6} {'End':>6}  Status  Response: query / total / first item")
    for i, (text, s, d, e) in enumerate(reqs, 1):
        url = f"GET /api/search?q={q(text)}&inStock=false&limit=20"
        out.append(f"{i:<3} {url:<54} {s:>6} {d:>6} {e:>6}  200     \"{text}\" / {totals[text]} / \"{first[text]}\"")
    out.append("")
    out.append(f"{len(reqs)} requests, all completed with status 200. None was canceled. None was served from the browser cache.")
    out.append("")
    out.append("Requests in the order their responses arrived:")
    for text, s, d, e in sorted(reqs, key=lambda r: r[3]):
        out.append(f"  {e:>5} ms  \"{text}\"")
    return out


reqs = session(0)
arrival = sorted(reqs, key=lambda r: r[3])
assert len(reqs) == 11 and arrival[-1][0] == "lap" and arrival[-2][0] == "la" and arrival[-3][0] == "laptop stand"
assert arrival[0][0] == "lapto" and arrival[0][3] == 880
NETLOG = "\n".join(log(reqs, [
    "Chrome DevTools, Network panel, filter \"/api/search\", exported as text. Production, desktop Chrome.",
    "Times are milliseconds from the first key press. The user typed \"laptop stand\" at a steady pace,",
    "then stopped and waited. \"In stock only\" was off. \"Took\" is the time until the full response arrived.",
]) + [
    "",
    "Filmstrip (screenshots the panel took during the recording):",
    "     120 ms  \"Searching...\" shown; heading 'Results for \"la\"', 0 results; list empty",
    "     880 ms  \"Searching...\" gone; heading 'Results for \"laptop s\"', 94 results; first item \"Laptop sleeve, 13 inch\"",
    "    1500 ms  heading 'Results for \"laptop stand\"', 18 results; first item \"Laptop stand, aluminium\"",
    "    1550 ms  heading 'Results for \"laptop stand\"', 1904 results; first item \"Lab coat, white\"",
    "    2100 ms  heading 'Results for \"laptop stand\"', 312 results; first item \"Lap desk with cushion\"",
    "    5000 ms  unchanged since 2100 ms",
])

reqs2 = session(300)
arr2 = sorted(reqs2, key=lambda r: r[3])
assert len(reqs2) == 11 and arr2[-1][0] == "lap" and arr2[-1][3] == 2370 and arr2[-3][0] == "laptop stand" and arr2[0][3] == 1180
NETLOG_AFTER = "\n".join(log(reqs2, [
    "Chrome DevTools, Network panel, filter \"/api/search\", exported as text. Staging, with the pull request applied;",
    "the staging search API is a copy of production with the same data and the same response times.",
    "Times are milliseconds from the first key press. The same typing as before: \"laptop stand\", then a stop.",
    "\"In stock only\" was off.",
]) + [
    "",
    "Filmstrip:",
    "     120 ms  \"Searching...\" shown; heading 'Results for \"la\"', 0 results; list empty",
    "    1180 ms  \"Searching...\" gone; heading 'Results for \"laptop stan\"', 94 results; first item \"Laptop sleeve, 13 inch\"",
    "    1800 ms  heading 'Results for \"laptop stand\"', 18 results; first item \"Laptop stand, aluminium\"",
    "    1850 ms  heading 'Results for \"laptop stand\"', 1904 results; first item \"Lab coat, white\"",
    "    2400 ms  heading 'Results for \"laptop stand\"', 312 results; first item \"Lap desk with cushion\"",
    "    5000 ms  unchanged since 2400 ms",
])

SCREENSHOT = '''A screenshot of the product search page in desktop Chrome, taken by a user a few seconds after they stopped typing.

- The search box contains: `laptop stand`. The "In stock only" checkbox is not ticked. No "Searching..." text is visible and there is no error message.
- Heading under the box: **Results for "laptop stand"**, and next to it in smaller text: **312 results**.
- The list below shows six items (the rest are below the fold), each with a price:
  1. Lap desk with cushion, 34.90
  2. Lapel pins, set of 6, 12.50
  3. Laptop sleeve, 13 inch, 19.99
  4. Lap tray, bamboo, 27.00, with a grey "Out of stock" badge
  5. Laptop backpack, 20 L, 59.00
  6. Lapis bead bracelet, 22.40

(For the interviewer: none of the six visible items is a laptop stand. 312 is the total the API returns for the query "lap"; the API returns 18 for "laptop stand", whose first item is "Laptop stand, aluminium".)
'''

PR_DIFF = '''Pull request: "Debounce product search and ignore stale responses"

Description: Search sent a request on every key press, and old responses could
overwrite new ones. This waits 300 ms after typing and drops responses whose
query is not the current one. Tested locally by typing fast: results are correct.

Checks: typecheck passed; 14 tests passed.

diff --git a/src/search/useSearch.ts b/src/search/useSearch.ts
index 4b1c9e2..a07d3f5 100644
--- a/src/search/useSearch.ts
+++ b/src/search/useSearch.ts
@@ -15,13 +15,18 @@ export function useSearch(query: string, inStockOnly: boolean) {
     }
     setLoading(true);
     setError(null);
-    searchProducts(query, inStockOnly)
-      .then((res) => {
-        setResults(res.items);
-        setTotal(res.total);
-      })
-      .catch(() => setError("Search failed. Try again."))
-      .finally(() => setLoading(false));
+    // Debounce: wait until the user stops typing for 300 ms.
+    setTimeout(() => {
+      searchProducts(query, inStockOnly)
+        .then((res) => {
+          // Drop responses for old queries.
+          if (res.query !== query) return;
+          setResults(res.items);
+          setTotal(res.total);
+        })
+        .catch(() => setError("Search failed. Try again."))
+        .finally(() => setLoading(false));
+    }, 300);
   }, [query, inStockOnly]);
 
   return { results, total, loading, error };
'''
# hunk header check: old 15..27 is 13 lines, new 18 lines
assert USE_SEARCH.split("\n")[14].strip() == "}" and USE_SEARCH.split("\n")[26].strip().startswith("return")

CACHE = '''// Proposed by a teammate: src/search/search-cache.ts
// useSearch would call cachedSearch(query, inStockOnly, controller.signal)
// instead of searchProducts, keeping the AbortController from your fix.
// Measured on staging: going back to a query already typed shows results in
// under 5 ms instead of 200 to 1,800 ms.

import { searchProducts, type SearchResponse } from "../api/search";

// Remember every search so going back to an earlier query is instant.
const cache = new Map<string, Promise<SearchResponse>>();

export function cachedSearch(
  query: string,
  inStockOnly: boolean,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const key = query.trim().toLowerCase();
  let pending = cache.get(key);
  if (!pending) {
    pending = searchProducts(query, inStockOnly, signal);
    cache.set(key, pending);
  }
  return pending;
}
'''

entities = [
    repo_entity("e1", "web-shop-search", files),
    image_entity("e2", "search-screenshot.png", SCREENSHOT),
    code_entity("e3", "network-log.txt", NETLOG),
    code_entity("e4", "pr-search-debounce.diff", PR_DIFF),
    code_entity("e5", "network-log-after-pr.txt", NETLOG_AFTER),
    code_entity("e6", "useSearch.ts", USE_SEARCH),
    code_entity("e7", "search-cache.ts", CACHE),
]

eff_start = line_of(USE_SEARCH, "useEffect(() => {")
eff_end = line_of(USE_SEARCH, "}, [query, inStockOnly]);")

p3 = probe(
    1,
    "A teammate proposes caching search results in the browser so going back to an earlier query is instant, on top of the fixed hook. Show search-cache.ts. Ask whether they would approve it as written, what could go wrong for a user, and what they would do instead. If they ask how long users keep the page open: often all day, in a tab. If they ask how often stock and prices change: every few minutes. If they ask whether the fix from the previous step is merged: yes, the hook now aborts the previous request when the text changes.",
    "Not as written. (1) The key is only the text: `inStockOnly` is not part of the key, so after typing \"lap\" and then ticking In stock only, the hook gets the cached unfiltered results, out-of-stock items included, and the reverse. Every input that changes the response must be in the key. (2) It stores the promise, including a rejected one, forever: a failed request (a 500, a dropped connection) poisons that query until the page reloads. Worse with the previous fix: the first caller's AbortSignal is passed into the cached request, so typing \"lap\" on the way to \"laptop\" aborts that request and the cached rejection is an AbortError; coming back to \"lap\" then returns the aborted promise every time (an error, or nothing if AbortError is ignored). One caller's shared signal must not control a request that others reuse. (3) No expiry and no size limit: prices and stock change every few minutes but a tab stays open all day, so results go stale, and every prefix typed (\"la\", \"lap\", \"lapt\"...) is kept, so memory grows all day. (4) Minor: the key is trimmed and lowercased but the first caller's exact text is what gets sent. What to do: key on everything that shapes the response (normalised text plus inStockOnly plus limit); delete the entry when the promise rejects; don't tie the shared request to one caller's signal (abort only stops that caller from using it, or let it finish and keep it); a short time-to-live plus a size limit (a small LRU); or use a data-fetching library that already does this (TanStack Query with queryKey ['search', q, inStockOnly], a staleTime, request de-duplication, cancellation through its signal, errors not cached, garbage collection of unused entries). Also check the server's Cache-Control: HTTP caching may already be enough for repeat queries. Strong candidates connect (2) to the AbortController from the previous step without being led.",
    ["cached rejection", "not part of the key", "shared signal"],
    ["Type \"lap\", then tick In stock only. What does cachedSearch return?",
     "What is in the Map after a request fails, or after its signal aborts it?",
     "The tab stays open all day. What does the Map hold by evening, and how old is it?"],
    3, ["e7"])

p2 = probe(
    1,
    "Show useSearch.ts, a copy of the hook as it was before the pull request, which they can edit. Ask them to change it so the list always matches the text in the box, then walk through their version. Then ask about their code only, one question at a time, choosing what their version leaves open: what happens to a response that arrives after the text has changed; what the error and the spinner show while requests overlap; what happens if the user clears the box while a request is in flight; what happens when the In stock only box changes mid-request. Ask them to attach the lines they mean.",
    "A good version gives the effect a cleanup function so every run cancels or ignores the previous one. Typical: `const controller = new AbortController();` before the call, `searchProducts(query, inStockOnly, controller.signal)` (searchProducts in src/api/search.ts already accepts a signal and nothing passes it), and `return () => controller.abort();`. The catch must ignore the AbortError (`if (controller.signal.aborted) return;` or check `err.name === \"AbortError\"`), otherwise every key press flashes \"Search failed\". `setLoading(false)` must run only for the request that is still current, so the spinner stays until the latest answer arrives. An ignore flag (`let ignore = false; ... return () => { ignore = true; }` and `if (ignore) return;` before each setState) is equally correct for the list; abort also frees the connection and the server work. Optional: a real debounce in the same effect (`const t = setTimeout(..., 250)` and clear it in the cleanup) to cut requests, but it is not what keeps order. Clearing the box below 2 characters runs the cleanup too, so a late response cannot refill the list. The In stock only box is in the dependency array, so changing it also cancels the old request. Weak versions: compare res.query with query inside the closure (always equal), keep a module-level 'latest query' variable updated in render, or debounce only.",
    ["AbortError", "ignore flag"],
    ["What does an effect's cleanup function run, and when?",
     "searchProducts takes a third argument. What is it for?",
     "When a request is cancelled, which of your handlers run?"],
    2, ["e6"], editable=["e6"], nxt=[p3])

p1 = probe(
    1,
    "A teammate opened a pull request to fix it. Show the diff and the network log recorded on staging with the pull request applied, typing the same text. Ask them to review it as they would on the team: what each change does when the page runs, whether it fixes the wrong results, and what they would ask the teammate to change. If they ask how it was tested: locally, against a development API where every search answers in about 20 ms. If they ask whether staging matches production: same data and the same response times.",
    "It fixes neither problem. The setTimeout is never cleared: the effect has no cleanup, so nothing cancels the timer when the next key arrives. That is a delay, not a debounce: the after-log still shows 11 requests, each starting 300 ms after its key (la at 410, lap at 530 ... laptop stand at 1560). The check `if (res.query !== query) return;` compares the response with `query` from the same effect run's closure, the text that request was sent with, so it is always equal (the API echoes q) and it never drops anything: a stale closure. The last response to arrive still wins: \"lap\" arrives at 2370 ms, after \"laptop stand\" at 1780, and the page ends on 312 results again, now 300 ms later. The spinner still disappears with the first response to finish (1180 ms) while 6 requests are pending, and an error from an old request can still replace good results. The local test could not show the bug: with every answer in about 20 ms, responses never overtake each other. The check also ignores inStockOnly. What to ask for: a cleanup in the effect that clears the timer and cancels or ignores the in-flight request (AbortController, whose signal searchProducts already accepts, or an ignore flag), so only the latest effect run may set state; a test with a fake API that answers an earlier query after a later one.",
    ["never drops anything", "not a debounce", "stale closure"],
    ["How many requests does the after-log show, and when does each start?",
     "Inside the .then, which query is `query`: the one in the box now, or another?",
     "Why could typing fast against the development API not show this?"],
    3, ["e4", "e5"], nxt=[p2])

question = {
    "name": "Why product search shows results for an earlier query",
    "mode": "open-probe",
    "topics": [
        "React data fetching in effects: cleanup, cancellation and out-of-order responses",
        "Async JavaScript: promises, timers, closures and AbortController",
        "Caching server data in the browser: cache keys, errors and expiry",
    ],
    "seniority": "mid",
    "duration": 12,
    "status": "draft",
    "seed_question": "On the product search page, users type a query and sometimes end up looking at results for an earlier, shorter one: the box says `laptop stand`, the heading says **312 results**, and the list shows lap desks and lapel pins. While they type, the list also changes several times before it settles. The search API returns the right results for every query it is sent. The page is React 19.3 with TypeScript.\n\nAttached: the search code, a user's screenshot, and the browser's network log of one typing session.\n\n**Why does the page end up showing the wrong results? Point to the code and the log.**",
    "entity_refs": [{"id": "e1", "run": None, "editable": False},
                    {"id": "e2", "run": None, "editable": False},
                    {"id": "e3", "run": None, "editable": False}],
    "mcq_choices": [],
    "question_prompt": "Front-end developer, 2 to 4 years, React and TypeScript. The question follows one search-as-you-type page whose hook fetches in useEffect with no cleanup: why the list ends on an earlier query's results, a teammate's pull request that delays requests and checks the response's query, the candidate's own fix in an editable copy of the hook, and a teammate's proposed browser cache of results. The first probe is the richest (the pull request and the network log recorded with it: why neither change works); the last is the hardest (judging the cache: what its key leaves out, what it does with failed and aborted requests, how old its data gets). Press for answers grounded in the files. Strong candidates name specific things: the effect in useSearch.ts with no return/cleanup; `.then` calling setResults whenever a response arrives; the \"lap\" request sent at 230 ms that took 1840 ms and arrived at 2070, after \"laptop stand\" at 1480; 312 as the total for \"lap\"; the filmstrip going 18, then 1904, then 312; the heading built from the current `query` state while the list comes from the last response; \"Searching...\" gone at 880 ms while requests were still pending; the unused `signal` parameter of searchProducts; in the pull request, the setTimeout that is never cleared (11 requests in the after-log) and `res.query !== query` comparing against the same closure's query. If an answer names nothing from the files, ask for one line or one number before moving on. If they ask whether the server caches search results: no, every request is computed. If they ask about mobile: the same happens there, more often on slow networks. Don't explain effect cleanup, closures, AbortController, debouncing or race conditions to the candidate.",
    "answer_key": {
        "red_flags": [
            "blames the search API or a server cache, though the log shows every response matches its own query",
            "proposes a debounce as the whole fix: fewer requests, but a slow earlier response can still arrive last",
            "says React's batching or asynchronous setState causes it, without connecting it to the order the responses arrive in",
        ],
        "required_concepts": [
            "Every change of the text (2 characters or more) runs the effect and starts a new request, and nothing cancels or ignores the earlier ones: the effect in useSearch.ts has no cleanup function, so the list shows whichever response arrives last, not the one for the latest text. Last to arrive wins.",
            "The log shows the responses arriving out of order: short queries are slow, so \"lap\" (sent at 230 ms, 1840 ms long) arrives at 2070 ms, after \"laptop stand\" (sent at 1260, arrived at 1480). The filmstrip matches: 18 results at 1500, then \"la\"'s 1904 at 1550, then \"lap\"'s 312 from 2100 on, which is the screenshot.",
            "The heading is built from the current `query` state, while the list and the total come from the last response to arrive, so the two disagree on screen. The fix is to cancel or ignore the previous request in the effect's cleanup (AbortController with the `signal` searchProducts already accepts, or a flag set in the cleanup), so only the current run may set state.",
        ],
        "good_additional_points": [
            "the spinner disappears at 880 ms when the first response finishes (`finally(() => setLoading(false))`), while six requests are still pending",
            "an error from an old request can replace good results, and a success can hide a current error",
            "clearing the box to under 2 characters empties the list, but a late response can fill it again under no heading",
            "11 requests for one query: a debounce would cut load on the server, as a separate improvement",
            "the same race happens when In stock only is toggled while a request is in flight",
            "a test with a fake API that answers an earlier query later would have caught it",
        ],
    },
    "probes": [p1],
    "seed_hints": hints([
        "In the log, which response arrives last, and which query was it for?",
        "Follow one response into useSearch.ts. What decides whether it is shown?",
        "Where does the heading get its text, and where does the list get its items?",
    ]),
    "withheld_solution_parts": ["no cleanup function", "last to arrive wins", "out of order"],
    "max_probes": 3,
    "seed_duration": 4,
    "description_sections": {
        "task": "A shop's product search shows results while the user types. Sometimes the page ends up showing results for an earlier, shorter search (the box says \"laptop stand\" but the list shows lap desks). The candidate works out why from the code and a record of the browser's requests, reviews a colleague's fix, writes their own fix, and judges a colleague's idea for remembering past results.",
        "signal": "Can this person explain, from the code and the request log, why the newest answer is not always the one shown, and fix it?",
        "audience": "Front-end developers (2 to 4 years) who build React apps in TypeScript. Knowing how React runs code after a change and how the browser sends requests helps.",
        "implement": "1. Explains why the wrong results appear, pointing to the code and the request log. *(4 min)*\n2. Reviews a colleague's fix and a new request log recorded with it, and says whether it works. *(3 min)*\n3. Changes the search code so the list always matches the text in the box, then explains it. *(2 min)*\n4. Judges a colleague's plan to keep past search results in the browser, and says what could go wrong. *(3 min)*",
        "starting_state": "- The search page's code (a small code folder)\n- A user's screenshot of the wrong results\n- The browser's record of the requests sent while one user typed\n- Later: a colleague's code change with a new record of requests, a copy of the search code they can edit, and a colleague's proposed code for remembering results",
    },
    "seed_highlights": [],
}

check_and_write("new-fe-1", question, entities)
