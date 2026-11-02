import difflib
from common import *

README = '''# items page: add labels

Users select rows on the items page and press **Add labels** to open a dialog.
In the dialog they search the labels, pick one or more, and press **Save**.

- `Modal` is the app's shared dialog component (used by 9 dialogs).
- `LabelPicker` is the search box with its list of matching labels.
- The team's target is WCAG 2.2 level AA for every page.

React 19.3, TypeScript 7.0, Vite. End-to-end tests use Playwright.
'''

MODAL = '''import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ open, title, onClose, children }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <div className="icon-button" onClick={onClose}>
            <svg aria-hidden="true" viewBox="0 0 16 16">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </div>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
'''

PICKER = '''import { useState } from "react";
import type { Label } from "./types";

interface LabelPickerProps {
  labels: Label[];
  selected: string[];
  onToggle: (id: string) => void;
}

export function LabelPicker({ labels, selected, onToggle }: LabelPickerProps) {
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const matches = labels.filter((l) => l.name.toLowerCase().includes(text.toLowerCase()));

  return (
    <div className="picker">
      <input
        className="picker-input"
        placeholder="Search labels"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setActive(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((i) => Math.min(i + 1, matches.length - 1));
          if (e.key === "ArrowUp") setActive((i) => Math.max(i - 1, 0));
        }}
      />
      {text && (
        <div className="picker-list">
          {matches.map((l, i) => (
            <div
              key={l.id}
              className={i === active ? "option active" : "option"}
              onClick={() => onToggle(l.id)}
            >
              <span className="swatch" style={{ background: l.color }} />
              {l.name}
              {selected.includes(l.id) && <span className="check">✓</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
'''

DIALOG = '''import { useState, type FormEvent } from "react";
import { Modal } from "../components/Modal";
import { LabelPicker } from "./LabelPicker";
import { saveLabels } from "./api";
import { ALL_LABELS } from "./labels";

interface AddLabelsDialogProps {
  open: boolean;
  itemIds: string[];
  onClose: () => void;
}

export function AddLabelsDialog({ open, itemIds, onClose }: AddLabelsDialogProps) {
  const [chosen, setChosen] = useState<string[]>([]);

  const toggle = (id: string) =>
    setChosen((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await saveLabels(itemIds, chosen);
    setChosen([]);
    onClose();
  };

  return (
    <Modal open={open} title="Add labels" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <LabelPicker labels={ALL_LABELS} selected={chosen} onToggle={toggle} />
        <p className="hint">{chosen.length} labels selected</p>
        <div className="actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit">Save</button>
        </div>
      </form>
    </Modal>
  );
}
'''

LABELS = '''import type { Label } from "./types";

export const ALL_LABELS: Label[] = [
  { id: "l1", name: "bug", color: "#d73a4a" },
  { id: "l2", name: "build", color: "#5319e7" },
  { id: "l3", name: "budget", color: "#fbca04" },
  { id: "l4", name: "blocked", color: "#b60205" },
  { id: "l5", name: "backend", color: "#0e8a16" },
  { id: "l6", name: "database", color: "#1d76db" },
  { id: "l7", name: "design", color: "#c5def5" },
  { id: "l8", name: "docs", color: "#0075ca" },
  { id: "l9", name: "frontend", color: "#e99695" },
  { id: "l10", name: "security", color: "#ee0701" },
];
'''

TYPES = '''export interface Label {
  id: string;
  name: string;
  color: string;
}

export interface Item {
  id: string;
  title: string;
  labels: string[];
}
'''

API = '''export async function saveLabels(itemIds: string[], labelIds: string[]): Promise<void> {
  const res = await fetch("/api/items/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ itemIds, labelIds }),
  });
  if (!res.ok) throw new Error(`save failed: ${res.status}`);
}
'''

PAGE = '''import { useState } from "react";
import { AddLabelsDialog } from "../labels/AddLabelsDialog";
import type { Item } from "../labels/types";

export function ItemsPage({ items }: { items: Item[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const toggleRow = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="toolbar">
        <button onClick={() => setDialogOpen(true)} disabled={selected.length === 0}>
          Add labels
        </button>
        <button>Export</button>
      </header>
      <main id="main">
        <h1>Items</h1>
        <table>
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  aria-label="Select all"
                  checked={selected.length === items.length}
                  onChange={(e) => setSelected(e.target.checked ? items.map((i) => i.id) : [])}
                />
              </th>
              <th>Title</th>
              <th>Labels</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, i) => (
              <tr key={item.id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select row ${i + 1}`}
                    checked={selected.includes(item.id)}
                    onChange={() => toggleRow(item.id)}
                  />
                </td>
                <td>{item.title}</td>
                <td>{item.labels.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
      <AddLabelsDialog open={dialogOpen} itemIds={selected} onClose={() => setDialogOpen(false)} />
    </>
  );
}
'''

CSS = '''.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: grid;
  place-items: center;
}

.modal {
  background: #fff;
  border-radius: 8px;
  width: 420px;
  padding: 16px;
}

.icon-button {
  cursor: pointer;
  width: 24px;
  height: 24px;
}

.picker-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #c9ced6;
}

.picker-input:focus {
  outline: none;
}

.option {
  display: flex;
  gap: 8px;
  padding: 4px 8px;
  cursor: pointer;
}

.option.active {
  background: #eef3ff;
}

.option .check {
  margin-left: auto;
  color: #2f6fed;
}
'''

files = {
    "README.md": README,
    "src/components/Modal.tsx": MODAL,
    "src/labels/AddLabelsDialog.tsx": DIALOG,
    "src/labels/LabelPicker.tsx": PICKER,
    "src/labels/api.ts": API,
    "src/labels/labels.ts": LABELS,
    "src/labels/types.ts": TYPES,
    "src/pages/ItemsPage.tsx": PAGE,
    "src/styles/modal.css": CSS,
}

names = ["bug", "build", "budget", "blocked", "backend", "database", "design", "docs", "frontend", "security"]
m = lambda t: [n for n in names if t in n]
assert m("bu") == ["bug", "build", "budget"]
assert m("b") == ["bug", "build", "budget", "blocked", "backend", "database"]
assert m("do") == ["docs"]


def lum(hexc):
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


ratio = (1.05) / (lum("#eef3ff") + 0.05)
assert 1.05 < ratio < 1.15

SR_LOG = '''NVDA 2026.2 speech viewer, Chrome 142, Windows 11. Items page with 40 rows; rows 1 and 2 are
already selected, so "Add labels" is enabled. Each line: the keys pressed, then what NVDA said.
"(nothing)" means NVDA said nothing. NVDA was in focus mode unless the line says browse mode.

Session 1: keyboard only
 1  [Tab]                     Add labels  button
 2  [Enter]                   (nothing)                       the dialog appears on screen
 3  [Tab]                     Export  button
 4  [Tab]                     Select all  check box  not checked
 5  [Tab] x40                 Select row 1  check box  checked ... Select row 40  check box  not checked
                              (40 announcements, shortened here)
 6  [Tab]                     Search labels  edit  blank
 7  [b] [u]                   b  u
 8  [Down Arrow]              bu
 9  [Down Arrow]              bu
10  [Enter]                   Items  document                 the dialog has closed
11  [Tab]                     Skip to content  link

Session 2: mouse, then keyboard
12  mouse: Add labels, then a click in the dialog's search box
                              Search labels  edit  blank
13  [b] [u]                   b  u
14  mouse: click on "bug"     (nothing)                       a check mark appears next to "bug"
15  [Escape]                  Items  document                 the dialog has closed
16  [Tab]                     Skip to content  link

Session 3: browse mode (NVDA's reading cursor), dialog open
17  [Ctrl+Home]               Skip to content  link
18  [H]                       Items  heading  level 1
19  [H]                       no next heading
20  [Ctrl+End]                Save  button
21  [Up Arrow]                Cancel  button
22  [Up Arrow]                0 labels selected
23  [Up Arrow]                Search labels  edit  blank
24  [Up Arrow]                Add labels

Network, same sessions: step 10 sent POST /api/items/labels with {"itemIds":["i1","i2"],"labelIds":[]}.
Step 15 sent nothing.
'''

SCREENSHOT = f'''Two screenshots side by side, taken during session 1 of the speech log (desktop Chrome, 100% zoom).

**Left, after step 3:** the items page is dimmed by a dark overlay. A white dialog is centred on top of it. Behind the overlay, in the toolbar at the top of the page, the "Export" button has a thick blue focus ring; it is the only focus ring on screen. The dialog shows, top left, the text "Add labels" in bold; top right, an "×" icon; below, an empty search box with the grey placeholder "Search labels"; under it "0 labels selected"; at the bottom right two buttons, "Cancel" and "Save" (Save is blue).

**Right, after step 9:** the same dialog. The search box contains "bu". The box has a thin grey border, the same as when it is not focused; there is no focus ring anywhere on screen. Under the box a list of three rows, each with a small coloured square and a name: "bug" (red square), "build" (purple square), "budget" (yellow square). The "budget" row has a very light blue background (#eef3ff on the white dialog); the other rows are white. Nothing else marks it.

(For the interviewer: #eef3ff against white is a contrast ratio of about {ratio:.2f} to 1.)
'''


def udiff(path, before, after):
    return f"diff --git a/{path} b/{path}\n" + "\n".join(difflib.unified_diff(
        before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", n=3, lineterm=""))


MODAL_PR = MODAL.replace('import { useEffect, type ReactNode } from "react";',
                         'import { useEffect, useRef, type ReactNode } from "react";').replace(
'''export function Modal({ open, title, onClose, children }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };''', '''export function Modal({ open, title, onClose, children }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current!;
    const focusable = dialog.querySelectorAll<HTMLElement>("button, input");
    focusable[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      // Keep Tab inside the dialog.
      if (e.key === "Tab" && document.activeElement === focusable[focusable.length - 1]) {
        e.preventDefault();
        focusable[0].focus();
      }
    };''').replace(
'''      <div className="modal" onClick={(e) => e.stopPropagation()}>''',
'''      <div
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >''').replace(
'''          <div className="icon-button" onClick={onClose}>''',
'''          <div className="icon-button" aria-label="Close" onClick={onClose}>''')

PICKER_PR = PICKER.replace('''        <div className="picker-list">''', '''        <div className="picker-list" aria-live="assertive">''').replace(
'''            <div
              key={l.id}
              className={i === active ? "option active" : "option"}
              onClick={() => onToggle(l.id)}
            >''', '''            <div
              key={l.id}
              tabIndex={0}
              className={i === active ? "option active" : "option"}
              onClick={() => onToggle(l.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onToggle(l.id);
              }}
            >''')
assert MODAL_PR.count("aria-modal") == 1 and PICKER_PR.count("tabIndex") == 1

PR = '''Pull request: "Make the Add labels dialog accessible"

Description: The dialog now has role="dialog" and aria-modal, moves focus into
itself when it opens and keeps Tab inside. The close icon has a label. Labels in
the list can be reached with Tab and chosen with Enter, and the list is a live
region so screen readers hear the matches. axe: 0 violations.

Checks: typecheck passed; e2e/a11y.spec.ts passed.

''' + udiff("src/components/Modal.tsx", MODAL, MODAL_PR) + "\n" + udiff("src/labels/LabelPicker.tsx", PICKER, PICKER_PR) + "\n"

SR_AFTER = '''NVDA 2026.2 speech viewer, Chrome 142, Windows 11, staging with the pull request applied.
Items page with 40 rows; rows 1 and 2 selected. Each line: the keys pressed, then what NVDA said.
NVDA was in focus mode.

Session 1: keyboard only
 1  [Tab]                     Add labels  button
 2  [Enter]                   Add labels  dialog   Search labels  edit  blank
 3  [b]                       b  bug  build  budget  blocked  backend  database
 4  [u]                       bug  build  budget             (cut in while the previous list was being read)
 5  [Down Arrow]              bu
 6  [Tab]                     bug
 7  [Tab]                     build
 8  [Enter]                   (nothing)                       a check mark appears next to "build"
 9  [Tab]                     budget
10  [Tab]                     Cancel  button
11  [Tab]                     Save  button
12  [Tab]                     Search labels  edit  bu
13  [Shift+Tab]               Select row 40  check box  not checked
14  [Tab]                     Search labels  edit  bu
15  [Escape]                  Items  document                 the dialog has closed
16  [Tab]                     Skip to content  link

Session 2: keyboard only
17  [Tab] [Enter]             Add labels  button   Add labels  dialog   Search labels  edit  blank
18  [d] [o]                   d  docs  o  docs
19  [Enter]                   Items  document                 the dialog has closed

Network, same sessions: step 15 sent nothing. Step 19 sent POST /api/items/labels with
{"itemIds":["i1","i2"],"labelIds":[]}.
'''

AXE = '''Proposal from the team: make this test the accessibility gate for the dialog in CI.
When it passes, the dialog can ship. The team must state at the release in two weeks
whether the dialog meets WCAG 2.2 level AA.

// e2e/a11y.spec.ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("items page has no accessibility violations", async ({ page }) => {
  await page.goto("/items");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

$ npx playwright test e2e/a11y.spec.ts --reporter=list
Running 1 test using 1 worker
  ✓  1 [chromium] › e2e/a11y.spec.ts:4:1 › items page has no accessibility violations (2.1s)
  1 passed (3.4s)

Summary from the same run (results.json, @axe-core/playwright 4.11):
  url:           http://localhost:4173/items
  violations:    0
  passes:        23 rules
  incomplete:    1 rule   color-contrast: 2 elements need review
  inapplicable:  64 rules, among them aria-dialog-name, aria-required-children,
                 aria-required-parent, aria-valid-attr-value, nested-interactive
'''

entities = [
    repo_entity("e1", "items-labels", files),
    code_entity("e2", "screen-reader-log.txt", SR_LOG),
    image_entity("e3", "dialog-screenshots.png", SCREENSHOT),
    code_entity("e4", "pr-dialog-a11y.diff", PR),
    code_entity("e5", "screen-reader-log-after-pr.txt", SR_AFTER),
    code_entity("e6", "LabelPicker.tsx", PICKER),
    code_entity("e7", "a11y-ci-gate.txt", AXE),
]

p3 = probe(
    1,
    "The team proposes an automated check as the accessibility gate for the dialog. Show a11y-ci-gate.txt. Ask whether they would accept it as the gate, what it does and does not tell them, and what they would put in place instead before the team states whether the dialog meets WCAG 2.2 AA. If they ask how many dialogs use Modal: 9. If they ask which screen readers users have: NVDA and JAWS on Windows with Chrome, VoiceOver on macOS and iOS with Safari. If they ask what the test data looks like: the items page loads 40 rows with nothing selected.",
    "Not as the gate. The test loads /items and scans it straight away: nothing is selected, so Add labels is disabled and the dialog was never opened; it isn't in the page, which is why aria-dialog-name, aria-required-children and the other dialog and listbox rules are inapplicable. It passes on the original broken code too. The incomplete color-contrast result is ignored because only violations fail the test. Even run with the dialog open, axe checks the page at one moment: whether roles, names and attribute values are present and valid, and some contrast. It cannot check what this bug is about: where focus goes on open, whether Tab and Shift+Tab stay inside, whether focus returns to Add labels on close, whether Enter submits the form, whether Escape closes the list or the whole dialog, what a screen reader announces and when. Automated rules find a minority of WCAG failures. Instead: (1) scan with the dialog open, and again with the list open, and fail on incomplete results that aren't reviewed; (2) keyboard tests in Playwright that assert behaviour: select a row, focus Add labels, press Enter, expect the search box (getByRole('combobox', {name: ...})) toBeFocused; Tab and Shift+Tab cycle within the dialog; type 'bu', ArrowDown, expect aria-activedescendant to point at the option and aria-expanded true; Enter toggles aria-selected and does not send a request; Escape closes the list first, a second Escape closes the dialog and expect the Add labels button toBeFocused; (3) an ARIA snapshot of the open dialog (toMatchAriaSnapshot) so roles and names can't regress; (4) a manual screen-reader pass before the release with NVDA plus Chrome and VoiceOver plus Safari, scripted from the speech logs, and a check at 200% zoom; (5) since Modal serves 9 dialogs, test the shared component once and each dialog's content. Only (2) to (4) let the team state AA honestly for this dialog; the statement should say which tests back it.",
    ["never opened", "keyboard tests", "manual screen-reader"],
    ["What state is the page in when the scan runs? Can the dialog be in it?",
     "Which steps of the speech logs could any automated scan observe?",
     "What would a test have to do to catch focus going to the page after Escape?"],
    3, ["e7"])

p2 = probe(
    1,
    "Show LabelPicker.tsx, a copy of the picker before the pull request, which they can edit. Ask them to change it so a keyboard user and a screen-reader user can search and choose labels, then walk through their version. Then ask about their code only, one question at a time, choosing what their version leaves open: what a screen reader says when they press Down Arrow; what Enter does when nothing matches, and when an option is active; what Escape does when the list is open; where focus is while they move through the options; how a mouse click on an option affects focus. Ask them to attach the lines they mean.",
    "A good version follows the combobox pattern with a listbox and keeps DOM focus on the input. The input gets role=\"combobox\", aria-expanded (true when the list shows), aria-controls pointing at the list's id, aria-autocomplete=\"list\", a real accessible name (a <label> or aria-labelledby, not only the placeholder), and aria-activedescendant set to the active option's id (or removed when the list is closed or empty). The list gets role=\"listbox\" with an id and aria-multiselectable=\"true\"; each option gets role=\"option\", a stable id and aria-selected reflecting `selected.includes(l.id)`; the check mark can stay as decoration. onKeyDown: ArrowDown and ArrowUp move `active` (and open the list); Enter calls e.preventDefault() so the form is not submitted, then toggles the active option if there is one; Escape, when the list is open, closes the list and calls e.stopPropagation() (and the Modal's listener must respect that, or listen on the dialog rather than the document) so the dialog stays open; a second Escape closes the dialog. `active` is reset or clamped when matches change. Options keep onClick, with onMouseDown preventDefault so a click doesn't take focus out of the input. The active option has a visible style beyond a pale background (an outline or border, 3:1 against its neighbours), and the input gets its focus outline back. Optional: a polite status such as \"3 labels found\" after typing pauses. Weak versions: tabIndex on each option, an assertive live region on the list, or roles added with no keyboard handling.",
    ["aria-activedescendant", "preventDefault", "stopPropagation"],
    ["How does a screen reader know which option is active if focus stays in the box?",
     "The box is inside a form. What does Enter do there by default?",
     "Two parts of the page listen for Escape. Which one should win when the list is open?"],
    2, ["e6"], editable=["e6"], nxt=[p3])

p1 = probe(
    1,
    "A teammate opened a pull request to fix the dialog. Show the diff and the speech log recorded on staging with it applied. Ask them to review it as they would on the team: what each change does for a keyboard user and a screen-reader user, what they would approve or reject, and what they would ask for instead. If they ask how it was tested: with the keyboard in Chrome, and axe reported no violations. If they ask which browsers must be supported: current Chrome, Edge, Firefox and Safari.",
    "Approve the role, aria-modal and name (step 2 now says \"Add labels dialog\") and moving focus into the dialog. Reject the rest. The focus trap's list is computed once, when the dialog opens, from \"button, input\": it never sees the options added later, it only handles Tab on the last element, and it ignores Shift+Tab, so Shift+Tab from the search box leaves the dialog (step 13, Select row 40). aria-modal tells assistive technology the rest is inert but doesn't make it so; the page behind is still focusable and reachable in browse mode. The close control is still a div: aria-label on a div with no role is not reliably announced, and it still can't be reached or pressed with the keyboard. It must be a <button type=\"button\" aria-label=\"Close\">. tabIndex={0} on every option turns one control into a Tab stop per label (steps 6 to 9), and NVDA announces no role or state (\"bug\", \"build\"): no \"option\", no \"selected\". The pattern is a single tab stop: focus stays in the box, arrows move an active option announced through aria-activedescendant. aria-live=\"assertive\" on the whole list reads every match on every key press and cuts itself off (steps 3 and 4); a polite count is enough. Still broken: Enter in the search box submits the form and saves nothing (steps 17 to 19); Escape closes the whole dialog; focus is not returned to Add labels on close (step 15, then Skip to content); the focus outline is still removed. Ask for: the native <dialog> element opened with showModal(): it puts the dialog in the top layer, makes the rest of the page inert (no hand-made trap), handles Escape through the cancel event, and focuses the first focusable element; plus, on close, focus back on the Add labels button explicitly; or the inert attribute on the app root if Modal must stay a div. Then the combobox pattern in the picker.",
    ["computed once", "single tab stop", "top layer"],
    ["Which elements does the focus trap know about, and when does it find them?",
     "In the new log, how many Tab presses does it take to get through three labels, and what does NVDA say for each?",
     "Which complaints from the opening question still happen in the new log?"],
    3, ["e4", "e5"], nxt=[p2])

L_FOCUS = line_of(CSS, "outline: none;")

question = {
    "name": "Why keyboard and screen-reader users can't use a dialog",
    "mode": "open-probe",
    "topics": [
        "Keyboard accessibility and focus management in modal dialogs",
        "ARIA roles, states and properties: dialog, combobox and listbox",
        "Testing accessibility: what automated checks find and what they miss",
    ],
    "seniority": "senior",
    "duration": 12,
    "status": "draft",
    "seed_question": "Keyboard and screen-reader users report that they can't use the **Add labels** dialog on the items page. Pressing Enter on a suggestion closes the dialog without adding the label, and when the dialog closes they are sent back to the top of the page. The page is React 19.3 with TypeScript.\n\nAttached: the code, a screen reader's speech log of one tester's sessions (NVDA with Chrome), and two screenshots taken during them.\n\n**What is wrong, for a keyboard user and for a screen-reader user? Point to the code and the log.**",
    "entity_refs": [{"id": "e1", "run": None, "editable": False},
                    {"id": "e2", "run": None, "editable": False},
                    {"id": "e3", "run": None, "editable": False}],
    "mcq_choices": [],
    "question_prompt": "Senior front-end engineer, 5 to 8 years, React and TypeScript, responsible for the accessibility of shared components. The question follows one dialog with a label search box: what is broken for keyboard and screen-reader users, a teammate's pull request that adds ARIA, a focus trap and tab stops, the candidate's own rewrite of the picker in an editable file, and a proposal to use an automated scan as the accessibility gate. The first probe is the richest (the pull request and the speech log recorded with it: what helps, what is wrong, what is still broken); the last is the hardest (judging the automated gate and planning tests that can back a WCAG 2.2 AA statement). Press for answers grounded in the files. Strong candidates name specific things: the Export focus ring behind the overlay and step 3 of the log; the 40 row check boxes before the search box is reached (the portal at the end of body); the `if (!open) return null` in Modal.tsx removing the focused element, then \"Items document\" and \"Skip to content\" (steps 10 and 11, 15 and 16); the dialog div with no role or name and the span title (browse mode reads \"Add labels\" as plain text, step 24, and the page behind, steps 17 to 19); the close div with an aria-hidden svg; Down Arrow saying \"bu\" (steps 8 and 9) because the active option is only a CSS class; Enter submitting the form with an empty labelIds; `.picker-input:focus { outline: none; }`; the #eef3ff highlight; in the pull request, the trap's querySelectorAll at open, Shift+Tab escaping at step 13, \"bug\", \"build\" with no role, the assertive list cutting itself off, and Enter still submitting at step 19; in the gate, the disabled Add labels button and the inapplicable dialog rules. If an answer names nothing from the files, ask for one line or one step number before moving on. Don't explain focus management, the dialog or combobox patterns, aria-modal, live regions, or what automated tools can check to the candidate.",
    "answer_key": {
        "red_flags": [
            "proposes adding aria-label or tabIndex to elements as the fix, without naming where focus goes or what the keyboard does",
            "proposes a positive tabIndex to fix the order, or treats the close icon as fine because it has an svg",
            "says running an automated checker would have caught all of this, or treats a screen reader's silence as a screen-reader bug",
        ],
        "required_concepts": [
            "Focus: opening the dialog doesn't move focus into it, so Tab goes to Export behind the overlay (step 3, the screenshot's focus ring), and nothing keeps focus inside: the dialog is rendered at the end of body, so the keyboard only reaches the search box after Export, Select all and all 40 row check boxes (steps 3 to 6). On close Modal returns null and removes the focused element, so focus falls to body (\"Items document\", then \"Skip to content\" on Tab, steps 10 to 11 and 15 to 16); it is never returned to Add labels.",
            "Semantics: the dialog is a plain div, with no role=\"dialog\", no aria-modal and no name (the title is a span), so NVDA says nothing when it opens (step 2) and browse mode reads the page behind (steps 17 to 19). The close control is a div with an aria-hidden svg: no role, no name, not focusable, no keyboard.",
            "The picker: the box is not a combobox (no role, aria-expanded, aria-controls or aria-activedescendant) and the options are divs with no role or aria-selected; the active option is only a CSS class, so Down Arrow says \"bu\" (steps 8 and 9). The input has no Enter handling, so Enter submits the form: the dialog saves with labelIds [] and closes. Escape on the document closes the whole dialog.",
        ],
        "good_additional_points": [
            "`.picker-input:focus { outline: none; }` in modal.css removes the focus indicator, so there is no focus ring after step 9",
            "the active option's #eef3ff background is about 1.1 to 1 against white, and colour is its only marker",
            "\"0 labels selected\" changes silently: no status message for screen readers",
            "the search box is named only by its placeholder",
            "clicking the overlay closes the dialog and loses the choices, with no confirmation",
            "Modal is shared by 9 dialogs, so fixing it fixes all of them, and breaking it breaks all of them",
        ],
    },
    "probes": [p1],
    "seed_hints": hints([
        "After step 2, where is keyboard focus? Look at step 3 and the left screenshot.",
        "What happens to the focused element when Modal returns null?",
        "When the tester presses Down Arrow, how would NVDA know which label is highlighted?",
    ]),
    "withheld_solution_parts": ["focus falls to body", "aria-activedescendant", "Enter submits the form"],
    "max_probes": 3,
    "seed_duration": 4,
    "description_sections": {
        "task": "A web app has a small window (a dialog) for adding labels to items, with a search box that suggests labels. People who use only a keyboard, or a screen reader (software that reads the screen aloud), can't use it: pressing Enter closes the window without adding the label, and they lose their place on the page. The candidate works out what is wrong from the code and a record of what the screen reader said, reviews a colleague's fix, rewrites the search box, and judges a plan to check accessibility automatically.",
        "signal": "Does this person know how keyboard focus and screen-reader announcements actually work in a dialog, beyond adding attributes?",
        "audience": "Senior front-end engineers (5 to 8 years) who build shared React components. Knowing the WCAG accessibility guidelines, ARIA (the attributes that describe a page to screen readers), and how to test with a screen reader helps.",
        "implement": "1. Explains what is broken for keyboard users and screen-reader users, pointing to the code and the screen reader's log. *(4 min)*\n2. Reviews a colleague's fix and a new screen-reader log recorded with it: what helps, what is wrong, what is still broken. *(3 min)*\n3. Rewrites the label search box so keyboard and screen-reader users can use it, then explains it. *(2 min)*\n4. Judges a plan to use one automated check as the team's accessibility gate, and says what testing they would do instead. *(3 min)*",
        "starting_state": "- The dialog's code (a small code folder)\n- A record of what the screen reader said, key by key, during a tester's sessions\n- Two screenshots of the dialog taken during those sessions\n- Later: a colleague's code change with a new screen-reader record, a copy of the search box code they can edit, and the automated accessibility test the team proposes",
    },
    "seed_highlights": [],
}

check_and_write("new-fe-3", question, entities)
print(PR)
