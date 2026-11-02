import difflib
from common import *

README = '''# records page

One page that shows up to 2,000 rows in a table with a filter box.

- `GET /api/rows` returns every row, plus a `version` number that changes when
  any row changes. The response carries an ETag.
- `RecordsPage` loads the rows, refreshes them every 5 seconds, and filters them
  in the browser as the user types.
- `DataTable` renders the rows. Columns are sized to their widest value so
  nothing is cut off.
- Users choose which columns to hide (`TableSettings`).

React 19.3, TypeScript 7.0, Vite. Production builds only are measured.
'''

PACKAGE = '''{
  "name": "records-page",
  "private": true,
  "version": "1.12.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "19.3.0",
    "react-dom": "19.3.0"
  },
  "devDependencies": {
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "typescript": "7.0.2",
    "vite": "8.1.0"
  }
}
'''

ROWS_API = '''import type { Row } from "../table/types";

export interface RowsResponse {
  version: number;
  rows: Row[];
}

export async function fetchRows(): Promise<RowsResponse> {
  const res = await fetch("/api/rows", { credentials: "include" });
  if (!res.ok) throw new Error(`rows failed: ${res.status}`);
  return res.json();
}
'''

PAGE = '''import { useEffect, useState } from "react";
import { fetchRows } from "../api/rows";
import { DataTable } from "../table/DataTable";
import { visibleColumns } from "../table/columns";
import type { Row, TableSettings } from "../table/types";

export function RecordsPage({ settings }: { settings: TableSettings }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetchRows().then((data) => setRows(data.rows));
    const id = setInterval(() => {
      fetchRows().then((data) => setRows(data.rows));
    }, 5000);
    return () => clearInterval(id);
  }, []);

  const needle = filter.toLowerCase();
  const visible = rows.filter((r) => JSON.stringify(r).toLowerCase().includes(needle));

  return (
    <main>
      <input
        id="filter"
        placeholder="Filter rows"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <p>
        {visible.length} of {rows.length} rows
      </p>
      <DataTable columns={visibleColumns(settings)} rows={visible} />
    </main>
  );
}
'''

DATATABLE = '''import { useLayoutEffect, useRef } from "react";
import type { Column, Row } from "./types";
import { TableRow } from "./TableRow";

interface DataTableProps {
  columns: Column[];
  rows: Row[];
}

export function DataTable({ columns, rows }: DataTableProps) {
  const tableRef = useRef<HTMLTableElement>(null);

  useLayoutEffect(() => {
    const table = tableRef.current;
    if (table) fitColumns(table, columns.length);
  });

  return (
    <table ref={tableRef} className="data-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <TableRow key={row.id} row={row} columns={columns} />
        ))}
      </tbody>
    </table>
  );
}

// Size every column to its widest cell, so nothing is cut off.
function fitColumns(table: HTMLTableElement, columnCount: number) {
  const bodyRows = Array.from(table.tBodies[0].rows);
  for (let c = 0; c < columnCount; c++) {
    let widest = 0;
    for (const tr of bodyRows) {
      const cell = tr.cells[c];
      cell.style.width = "auto";
      widest = Math.max(widest, cell.scrollWidth);
    }
    for (const tr of bodyRows) {
      tr.cells[c].style.width = `${widest}px`;
    }
    table.tHead!.rows[0].cells[c].style.width = `${widest}px`;
  }
}
'''

TABLEROW = '''import type { Column, Row } from "./types";

interface TableRowProps {
  row: Row;
  columns: Column[];
}

export function TableRow({ row, columns }: TableRowProps) {
  return (
    <tr>
      {columns.map((c) => (
        <td key={c.key} className={c.align === "right" ? "num" : undefined}>
          {String(row[c.key])}
        </td>
      ))}
    </tr>
  );
}
'''

COLUMNS = '''import type { Column, TableSettings } from "./types";

export const ALL_COLUMNS: Column[] = [
  { key: "name", label: "Name" },
  { key: "status", label: "Status" },
  { key: "owner", label: "Owner" },
  { key: "region", label: "Region" },
  { key: "updated", label: "Updated" },
  { key: "amount", label: "Amount", align: "right" },
];

export function visibleColumns(settings: TableSettings): Column[] {
  return ALL_COLUMNS.filter((c) => !settings.hidden.includes(c.key));
}
'''

TYPES = '''export interface Row {
  id: string;
  name: string;
  status: "open" | "pending" | "closed";
  owner: string;
  region: string;
  updated: string;
  amount: number;
}

export interface Column {
  key: keyof Row;
  label: string;
  align?: "right";
}

export interface TableSettings {
  hidden: (keyof Row)[];
}
'''

CSS = '''.data-table {
  /* fixed: so long values don't stretch the table while rows load */
  table-layout: fixed;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 4px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.data-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
'''

files = {
    "README.md": README, "package.json": PACKAGE, "src/api/rows.ts": ROWS_API,
    "src/pages/RecordsPage.tsx": PAGE, "src/table/DataTable.tsx": DATATABLE,
    "src/table/TableRow.tsx": TABLEROW, "src/table/columns.ts": COLUMNS,
    "src/table/types.ts": TYPES, "src/styles/table.css": CSS,
}

L_FILTER = line_of(PAGE, "const visible = rows.filter")
L_INTERVAL = line_of(PAGE, "const id = setInterval")
L_FIT = line_of(DATATABLE, "function fitColumns(")
L_READ = line_of(DATATABLE, "cell.scrollWidth")
L_EFFECT = line_of(DATATABLE, "useLayoutEffect(() => {")

ROWS, COLS = 2000, 6
assert ROWS * COLS == 12000
layout, scripting, recalc, paint = 1150.2, 259.6, 41.8, 8.9
fit_self, react, filt = 97.4, 128.1, 34.1
assert round(fit_self + react + filt, 1) == scripting
assert round(layout + scripting + recalc + paint) == 1460 + 1

TRACE = f'''A screenshot of the Chrome DevTools Performance panel, recorded on the records page in production, on a mid-range laptop with no CPU throttling. The recording is 3.2 s long. Before it starts, the filter box is empty and the line above the table says "2000 of 2000 rows". The user types "a" at 0.40 s and "b" at 2.10 s.

**Interactions track:** "Keyboard, input#filter, 1,480 ms" at 0.40 s, shown in red; "Keyboard, input#filter, 210 ms" at 2.10 s.

**Main thread, first key ("a"):** one task of 1,460 ms with a red "Long task" corner.
- Event: keydown, 1 ms
- Event: input, 1,452 ms
  - renderRootSync (react-dom), 131 ms; inside it RecordsPage 38 ms (the anonymous function at RecordsPage.tsx:{L_FILTER}, 34 ms, mostly JSON.stringify) and TableRow, rendered 2,000 times, 81 ms
  - commitRoot (react-dom), 1,318 ms; inside it commitLayoutEffects 1,309 ms; inside that fitColumns (DataTable.tsx:{L_FIT}), 1,302 ms
  - Under fitColumns: a dense comb of thin purple "Layout" entries alternating with short yellow script slices. The panel counts 12,000 Layout entries in this task, each 0.05 to 0.3 ms. Every one has a red triangle; hovering one shows "Forced reflow is a likely performance bottleneck", with "Layout forced: fitColumns @ DataTable.tsx:{L_READ}".
- After the task: Recalculate Style 21 ms, Layout 38 ms, Paint 9 ms, then the frame that shows "a" in the box at 1.88 s. The line above the table then says "2000 of 2000 rows".

**Main thread, second key ("b"):** one task of 190 ms: Event: input 186 ms; renderRootSync 64 ms; commitLayoutEffects 118 ms, almost all fitColumns (115 ms) with 1,284 Layout entries, each with the same forced reflow warning. The line above the table then says "214 of 2000 rows".

**Bottom-up tab, selection = the first task (1,460 ms):**
| Activity | Self time |
|---|---|
| Layout | {layout:,} ms (78.8%) |
| Scripting | {scripting} ms (17.8%): fitColumns self {fit_self} ms; react-dom render and commit {react} ms; the filter callback at RecordsPage.tsx:{L_FILTER} {filt} ms (of which JSON.stringify 29.0 ms) |
| Recalculate Style | {recalc} ms (2.9%) |
| Paint | {paint} ms |

**Summary tab:** DOM nodes on the page: 28,412; table body rows: 2,000; cells: 12,000.

(For the interviewer: 12,000 Layout entries is 2,000 rows times 6 columns; 1,284 is 214 rows times 6. The filter callback is 34.1 ms of the 1,460.)
'''


def udiff(path, before, after):
    lines = difflib.unified_diff(before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", n=3, lineterm="")
    lines = list(lines)
    return f"diff --git a/{path} b/{path}\n" + "\n".join(lines)


DATATABLE_PR = DATATABLE.replace('''  useLayoutEffect(() => {
    const table = tableRef.current;
    if (table) fitColumns(table, columns.length);
  });''', '''  useLayoutEffect(() => {
    const table = tableRef.current;
    if (!table) return;
    // Measure in the next frame so typing is not blocked.
    requestAnimationFrame(() => fitColumns(table, columns.length));
  }, [rows, columns]);''')
TABLEROW_PR = TABLEROW.replace('import type { Column, Row } from "./types";',
                               'import { memo } from "react";\nimport type { Column, Row } from "./types";').replace(
    "export function TableRow({ row, columns }: TableRowProps) {",
    "export const TableRow = memo(function TableRow({ row, columns }: TableRowProps) {").replace(
    "  );\n}\n", "  );\n});\n")
PAGE_PR = PAGE.replace('import { useEffect, useState } from "react";', 'import { useEffect, useMemo, useState } from "react";').replace(
    "  const visible = rows.filter((r) => JSON.stringify(r).toLowerCase().includes(needle));",
    "  const visible = useMemo(\n    () => rows.filter((r) => JSON.stringify(r).toLowerCase().includes(needle)),\n    [rows, needle],\n  );")
assert DATATABLE_PR != DATATABLE and TABLEROW_PR != TABLEROW and PAGE_PR != PAGE
L_RAF = line_of(DATATABLE_PR, "requestAnimationFrame(")

PR = '''Pull request: "Speed up typing in the records filter"

Description: Column fitting no longer blocks typing: it runs in the next
animation frame, and only when the rows or columns change. Rows are memoized,
and the filter is memoized. Typing feels much better in my testing.

Checks: typecheck passed.

''' + udiff("src/table/DataTable.tsx", DATATABLE, DATATABLE_PR) + "\n" + udiff("src/table/TableRow.tsx", TABLEROW, TABLEROW_PR) + "\n" + udiff("src/pages/RecordsPage.tsx", PAGE, PAGE_PR) + "\n"

TRACE_AFTER = f'''A screenshot of the Chrome DevTools Performance panel on staging with the pull request applied: same laptop, same data (2,000 rows), no CPU throttling. The user types "a" at 0.40 s and "b" at 2.10 s into the empty filter box. A React DevTools Profiler panel is docked below it, recorded at the same time.

**Interactions track:** "Keyboard, input#filter, 1,470 ms" at 0.40 s, red; "Keyboard, input#filter, 205 ms" at 2.10 s.

**Main thread, first key ("a"):**
- Task 1, 168 ms: Event: input; renderRootSync 131 ms (TableRow rendered 2,000 times, 84 ms; the useMemo filter callback at RecordsPage.tsx 34 ms); commit 33 ms.
- No frame is painted between the two tasks.
- Task 2, 1,296 ms, red "Long task" corner: "Animation Frame Fired (DataTable.tsx:{L_RAF})", inside it fitColumns 1,291 ms with 12,000 purple Layout entries, each marked "Forced reflow is a likely performance bottleneck", "Layout forced: fitColumns @ DataTable.tsx".
- Then Recalculate Style 20 ms, Layout 37 ms, Paint 9 ms; the frame showing "a" is painted at 1.87 s.

**Main thread, second key ("b"):** Task 1, 61 ms (Event: input, render of 214 rows); Task 2, "Animation Frame Fired", 131 ms, with 1,284 Layout entries.

**React DevTools Profiler, commit for key "a":** DataTable rendered, 2.1 ms self; TableRow (Memo) rendered 2,000 times; "Why did this render?" for every TableRow: "Props changed: columns". RecordsPage: "Hook 2 changed" (the filter text).

(For the interviewer: the key press that took 1,480 ms before the pull request takes 1,470 ms after it. The Layout work has moved from the commit into the animation frame callback; its size is unchanged.)
'''

OPTIONS = '''# Records table at 20,000 rows: options measured

Next quarter the table must handle 20,000 rows. Measured by a teammate on the
version that sizes columns once per data load (one measurement pass, no forced
layout per cell). 20,000 generated rows, production build, the same mid-range
laptop, Chrome, no throttling. Each number is the median of 5 runs.

| Option | First render | Key press when every row still matches | Key press that leaves 1,900 rows | Scrolling | Table cells in the page |
|---|---|---|---|---|---|
| A. Render every row (today's code) | 4,100 ms | 2,350 ms | 290 ms | 41 fps | 120,000 |
| B. A, plus `content-visibility: auto` on each `tr` | 1,350 ms | 1,620 ms | 210 ms | 58 fps | 120,000 |
| C. Windowing: render only the ~45 rows in view, plus 10 above and 10 below | 95 ms | 38 ms | 30 ms | 60 fps | about 390 |
| D. A, plus `useDeferredValue(filter)` for the list | 4,100 ms | box shows the letter in 24 ms; list updates 2,400 ms later | box 22 ms; list 300 ms later | 41 fps | 120,000 |

Notes:
- B: one CSS line added (`.data-table tbody tr { content-visibility: auto; }`), nothing else changed. While scrolling, the scrollbar thumb jumps and changes size.
- C: column widths are measured from the rows currently rendered, so they change while scrolling: the Name column is 212 px wide at the top and 318 px around row 9,000. The browser's find (Ctrl+F) only finds rows that are rendered.
- D: typing stays smooth; the list lags behind the box.
- Not measured: a screen reader on any option.
'''

RUM = f'''A screenshot of the team's real-user monitoring dashboard for the records page, last 7 days, two weeks after the release that renders only the visible rows (windowing). Tables can now hold up to 20,000 rows. Header: "INP (Interaction to Next Paint), 75th percentile: 610 ms" in red, with "Good: 200 ms or less". A smaller note: "Lab test of the same release: key press in the filter 38 ms".

**INP by interaction target, 75th percentile, with its three phases (input delay / processing / presentation delay):**
| Target | Interactions | INP p75 | Input delay | Processing | Presentation delay |
|---|---|---|---|---|---|
| `input#filter` (key press) | 31,200 | 150 ms | 22 ms | 96 ms | 32 ms |
| `tr input[type=checkbox]` (click, selecting a row) | 27,900 | 640 ms | 498 ms | 81 ms | 61 ms |
| `th button.sort` (click) | 4,300 | 410 ms | 41 ms | 312 ms | 57 ms |

**Row-checkbox clicks by device:** laptops with 4 CPU cores or fewer: INP p75 1,090 ms (38% of these clicks); all others: 240 ms.

**What was running when slow checkbox clicks arrived** (long animation frame attribution, share of slow clicks):
1. 71%: the setInterval callback at RecordsPage.tsx:{L_INTERVAL} (fetchRows, then setRows). A typical frame on a 4-core laptop: `response.json()` 180 ms (4.1 MB body), the filter callback at RecordsPage.tsx over 20,000 rows 410 ms (even with an empty filter box), column width measurement 150 ms, React render and commit 60 ms: about 800 ms, once every 5 seconds.
2. 9%: a third-party analytics script.
3. 20%: other or unattributed.

**Network panel note (the same release):** `GET /api/rows` every 5 s. 94% of these requests are answered "304 Not Modified" (the browser revalidates with the ETag, 0.3 KB transferred). The `version` field in the body was the same as in the previous poll 94% of the time.

(For the interviewer: for the checkbox, 498 of the 640 ms is input delay, the time before any handler of the click can start. The processing time of the click itself is 81 ms.)
'''

entities = [
    repo_entity("e1", "records-page", files),
    image_entity("e2", "trace-typing.png", TRACE),
    code_entity("e3", "pr-speed-up-filter.diff", PR),
    image_entity("e4", "trace-after-pr.png", TRACE_AFTER),
    md_entity("e5", "options-20k-rows.md", OPTIONS),
    image_entity("e6", "field-inp.png", RUM),
]

p3 = probe(
    1,
    "The windowing release is out and lab numbers are good, but the team's real-user monitoring says the page is slow for real users. Show field-inp.png. Ask why real users see slow interactions when the lab test does not, and what they would change. Once they have a plan, say their manager suggests refreshing every 30 seconds instead of every 5 and asks whether that is enough. If they ask what INP is: the time from a user's click or key press until the next frame is painted, reported per page view by its slowest interactions; 200 ms or less counts as good. If they ask whether the rows must refresh every 5 seconds: product wants changes visible within about 10 seconds. If they ask whether the server can send only what changed: it could add an endpoint returning rows changed since a version number.",
    "The slow interaction is the row checkbox, and 498 of its 640 ms is input delay: the click's own handler runs in 81 ms. The main thread is busy when the click arrives. The attribution says what with: 71% of slow clicks land during the polling callback at RecordsPage.tsx: every 5 s it parses a 4.1 MB body (180 ms), and setRows with a brand-new array re-runs everything keyed on rows: the useMemo filter over 20,000 rows with JSON.stringify (410 ms, even with an empty box), the column width measurement (150 ms), and a React render: about 800 ms on a 4-core laptop. A click has roughly a one in six chance of landing in it there. 94% of these polls change nothing (304 Not Modified, same version), but a 304 still hands fetch the cached full body, so the page parses and re-renders anyway. The lab missed it: a fast desktop CPU, a short recording that never caught a poll, and only key presses were measured. Changes, biggest first: skip unchanged data (compare `version` before calling setRows, or a version/delta endpoint returning only changed rows, then merge by id); keep row identity so unchanged rows keep the same object and memoized work only redoes what changed; compute a lowercase search string per row once when it arrives instead of JSON.stringify on every filter run (and search only the visible fields); measure column widths only when the data actually changes; if a big update is unavoidable, split it into chunks and yield to the browser between them (scheduler.yield() or setTimeout chunks) so clicks can run, or move parsing and filtering into a Web Worker; pause polling while the tab is hidden. The sort click (312 ms of processing) is a separate, handler-side problem: sort once into an index, not on every render. The 30-second suggestion: fewer collisions (about six times fewer long frames), but each frame is still about 800 ms, so a click that lands in one still waits as long, and on 4-core laptops the p75 may still be poor; it also breaks the 10-second freshness target. Shrink the work, then choose the interval.",
    ["busy when the click arrives", "row identity", "fewer collisions"],
    ["For the checkbox, which of the three phases is large, and what does that phase measure?",
     "What runs every 5 seconds, and how much of it depends on whether the data changed?",
     "Why would a lab test of typing on a fast laptop never see this?"],
    3, ["e6"])

p2 = probe(
    1,
    "Next quarter the table must handle 20,000 rows. A teammate measured four options. Show options-20k-rows.md. Ask which they would choose, and what each option breaks that they would need to fix before shipping it. If they ask whether the server could filter: yes, the API can take a filter parameter and answers in about 120 ms. If they ask about exporting or printing: export is a separate button and the server builds the file.",
    "C, windowing, is the only option that makes the work proportional to what is on screen (38 ms per key, about 390 cells), but it needs work before shipping: column widths must not come from the rendered rows (212 px vs 318 px while scrolling): compute them once per data load from the data, for example the longest value per column measured with canvas measureText, or fixed widths with ellipsis and a tooltip; Ctrl+F finds only rendered rows, so the filter box must be the find, or the server filters; screen readers need the full size: aria-rowcount on the table and aria-rowindex on each rendered row, and keyboard focus must survive a row being recycled. B (content-visibility) only skips layout and paint of off-screen rows: React still renders and diffs 120,000 cells (1,620 ms per key), and without contain-intrinsic-size the skipped rows have no height, so the scrollbar jumps and resizes, exactly what the note says; adding `contain-intrinsic-size: auto 28px` fixes the jumping, not the render cost. D (useDeferredValue) keeps the box responsive but does the same total work, and the list trails the box by 2.4 s; it does nothing for the 4.1 s first render. It combines well with C. A server-side filter is reasonable at this size too, but needs the same out-of-order handling for its responses. Weak answers pick B because it is one CSS line, or D because typing is smooth.",
    ["contain-intrinsic-size", "measureText", "aria-rowindex"],
    ["For B, which work does the browser skip, and which work does React still do on every key?",
     "For C, where do the column widths come from, and what happens to them while scrolling?",
     "What does a screen reader user learn about a table that only has 45 rows in the page?"],
    2, ["e5"], nxt=[p3])

p1 = probe(
    1,
    "A teammate opened a pull request to fix the typing. Show the diff and the recording made on staging with it applied, with the React Profiler. Ask them to review it as they would on the team: what each change does when the page runs, whether it fixes the problem, and what they would ask for instead. If they ask how it was tested: on a fast desktop machine, typing slowly. If they ask whether hiding columns is common: most users hide one or two columns.",
    "It moves the work without removing it. requestAnimationFrame runs its callback just before the next frame is painted, so fitColumns now does the same work before the next paint: the frame that shows the letter still waits for 12,000 forced layouts (Task 2, 1,296 ms), and the key press is 1,470 ms instead of 1,480. The dependency array [rows, columns] does not stop it running on every key, because `visibleColumns(settings)` returns a new array every render, so `columns` always changes; the same new array every render defeats memo on TableRow (the Profiler: 2,000 renders, \"Props changed: columns\"). useMemo on the filter only matters for renders where rows and filter are unchanged, and the filter was 34 ms. The rAF is never cancelled, so renders close together queue several fitColumns runs. What to ask for: remove the forced layout per cell: read all, then write all (set every cell to auto, read every scrollWidth in one pass, which costs one layout, then write the widths), or better, don't measure the DOM on every filter: compute widths once per data load (from the data, e.g. the longest value per column with canvas measureText, or measure once), and drop `table-layout: fixed` in table.css, which is why columns don't size to their content on their own (table-layout: auto, or a CSS grid with max-content columns, does it in one layout). Make `columns` stable with useMemo on settings so memo works. Then measure on a slower CPU (4x throttling) and with fast typing.",
    ["same work before the next paint", "new array every render", "read all, then write all"],
    ["When does a requestAnimationFrame callback run, relative to the frame that shows the letter?",
     "Read the Profiler line for TableRow. Where does a new columns array come from on every render?",
     "How many forced layouts are in the recording after the change?"],
    3, ["e3", "e4"], nxt=[p2])

question = {
    "name": "Why typing in a table's filter box freezes the page",
    "mode": "open-probe",
    "topics": [
        "Browser rendering performance: forced synchronous layout, long tasks and INP",
        "React rendering and commit: layout effects, memoization and referential identity",
        "Large lists in the browser: windowing, content-visibility and main-thread work",
    ],
    "seniority": "senior",
    "duration": 12,
    "status": "draft",
    "seed_question": "On a page that shows a table of up to 2,000 rows, typing in the filter box freezes the page: the first letter typed takes about **1.5 seconds** to appear in the box. The rows are loaded from the server and filtered in the browser. The page is React 19.3 with TypeScript.\n\nAttached: the page's code and a Chrome Performance recording of typing two letters.\n\n**Where does the time go, and why? Point to the code and the recording.**",
    "entity_refs": [{"id": "e1", "run": None, "editable": False},
                    {"id": "e2", "run": None, "editable": False}],
    "mcq_choices": [],
    "question_prompt": f"Senior front-end engineer, 5 to 8 years, React and TypeScript, who owns web performance. The question follows one table page: why a key press in the filter takes 1.5 s (a layout effect that forces one layout per cell), a teammate's pull request that moves the work into requestAnimationFrame and adds memoization, a choice between four ways to render 20,000 rows, and field data showing slow clicks caused by polling. The first probe is the richest (the pull request, its recording and the React Profiler: why nothing got faster); the last is the hardest (reading INP phases and long-animation-frame attribution from real users, and judging a manager's 30-second suggestion). Press for answers grounded in the files. Strong candidates name specific things: the 12,000 Layout entries and the forced reflow warning at DataTable.tsx:{L_READ}; `cell.style.width = \"auto\"` then `cell.scrollWidth` in the same loop; useLayoutEffect at DataTable.tsx:{L_EFFECT} with no dependency array; 1,150 of 1,460 ms in Layout and only 34 ms in the filter; \"2000 of 2000 rows\" after typing \"a\" because JSON.stringify includes key names; `table-layout: fixed` in table.css; in the pull request, the Animation Frame Fired task of 1,296 ms, and \"Props changed: columns\" from visibleColumns; in the options, the scrollbar note under B and the 212 vs 318 px under C; in the field data, 498 ms of input delay on the checkbox and the 800 ms poll every 5 s with 94% unchanged. If an answer names nothing from the files, ask for one line or one number before moving on. If they ask what users do on the page: filter, select rows with the checkboxes, sort, and leave it open for hours. Don't explain forced layout, layout thrashing, requestAnimationFrame, memoization, windowing or INP phases to the candidate.",
    "answer_key": {
        "red_flags": [
            "proposes memoizing or debouncing the filter as the main fix, though the recording puts 34 ms in the filter and 1,150 ms in Layout",
            "blames React's re-rendering or the virtual DOM in general, without pointing at the Layout entries and fitColumns",
            "proposes moving the work to useEffect or requestAnimationFrame as the fix: it runs after the paint (or just before the next one), and the next frame still waits for the same work",
        ],
        "required_concepts": [
            f"Most of the 1,460 ms task is Layout (1,150 ms, 12,000 entries) forced inside fitColumns: each cell gets `style.width = \"auto\"` (a write that invalidates layout) and then `scrollWidth` is read (DataTable.tsx:{L_READ}), which makes the browser lay out the table at once to answer. Alternating writes and reads gives a forced synchronous layout per cell, 2,000 rows times 6 columns: layout thrashing.",
            "It runs on every render: the useLayoutEffect has no dependency array, so it runs after every commit (every key press, and every 5-second refresh), and a layout effect runs before the browser paints, so the typed letter cannot appear until it finishes.",
            "The cost scales with the rows in the page: \"a\" leaves all 2,000 rows because the filter searches JSON.stringify(row), which includes key names like \"status\" and \"name\", so the first letter is the worst; \"ab\" leaves 214 and costs 190 ms (1,284 layouts). The filter itself is 34 ms.",
        ],
        "good_additional_points": [
            "the fix direction: read every width first, then write every width (one layout), and measure only when the data changes, not on every filter",
            "`table-layout: fixed` in table.css is why the columns don't size to their content without JavaScript; auto layout or a grid with max-content does it in one layout",
            "all 2,000 rows (28,412 DOM nodes) are in the page; rendering only visible rows would cut the work further",
            "the 5-second refresh calls setRows with a new array and triggers the same work every 5 seconds",
            "the filter also matches ids, dates and amounts, not just the visible text",
        ],
    },
    "probes": [p1],
    "seed_hints": hints([
        "In the bottom-up tab, which activity takes most of the 1,460 ms, and which function is it under?",
        "Read the inner loop of fitColumns. What does each pass write, and what does it read right after?",
        "When does that effect run? Look at what follows its callback.",
    ]),
    "withheld_solution_parts": ["forced synchronous layout", "layout thrashing", "no dependency array"],
    "max_probes": 3,
    "seed_duration": 4,
    "description_sections": {
        "task": "A web page shows a table of up to 2,000 rows with a filter box. Typing in the box freezes the page for about a second and a half. The candidate reads the code and a recording of what the browser did, and explains where the time goes. Then they review a colleague's fix, choose how to show 20,000 rows, and explain why real users still find the page slow when the team's own tests say it is fast.",
        "signal": "Can this person read a browser performance recording and the code together and find the real cost, rather than guessing at fixes?",
        "audience": "Senior front-end engineers (5 to 8 years) who build React apps and own their speed. Knowing how the browser lays out and draws a page, and how to read the Chrome performance tools, helps.",
        "implement": "1. Explains, from the code and a recording of the browser's work, where the 1.5 seconds go and why. *(4 min)*\n2. Reviews a colleague's fix and a new recording made with it, and says what they would ask for instead. *(3 min)*\n3. Chooses one of four ways to show 20,000 rows, measured by a colleague, and says what each one breaks. *(2 min)*\n4. Explains, from data collected from real users, why clicks are slow for them, and judges a manager's suggestion. *(3 min)*",
        "starting_state": "- The page's code (a small code folder)\n- A screenshot of a browser performance recording made while typing two letters\n- Later: a colleague's code change with a new recording, a table comparing four ways to show 20,000 rows, and a screenshot of the speed data collected from real users",
    },
    "seed_highlights": [],
}

check_and_write("new-fe-2", question, entities)
print(PR)
