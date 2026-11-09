# Custom commands

Any command typed twice deserves a name. Try it for the session first, then persist it in `~/.lldbinit` (ask before editing someone else's init file). LLDB offers three tiers: aliases for fixed text, regex commands for input you need to place inside a template, and Python for anything with logic, options, or formatted output.

## Where init files live

| File | Loaded when |
|---|---|
| `~/.lldbinit-Xcode` | only when Xcode drives LLDB |
| `~/.lldbinit-lldb` | only for the terminal `lldb` |
| `~/.lldbinit` | fallback when no application-specific init file exists |
| scheme > Run > Options > LLDB Init File | per project, after the global files (Xcode 14+) |

The application-specific init file takes precedence, not additive ordering. To share common settings, explicitly source `~/.lldbinit` from that file. A working-directory `.lldbinit` is normally not trusted automatically; source a reviewed file explicitly instead of enabling arbitrary project init files globally.

Init files normally run before the process is attached, so they cannot evaluate expressions against the target. They can define aliases, import scripts, set settings, and configure breakpoint names. Syntax errors in them are reported quietly at startup; reload during a session to see them:

```
command alias reload command source ~/.lldbinit
```

UI aliases below require a live `$window` selected as described in [View debugging](view-debugging.md).

## command alias

```
command alias cpo expression -l objc -O --
command alias spo expression -l swift -O --
command alias sp expression -l swift --
command alias flush expression -l objc -- (void)[CATransaction flush]
command alias args register read arg1 arg2 arg3 arg4 arg5 arg6
command alias bfl breakpoint set -f %1 -l %2                     # bfl Foo.swift 42
command alias -H "Print the selected window's view tree" -h "Dump views" -- pviews expression -l objc -O -- [$window recursiveDescription]
```

- `%1`, `%2` substitute positional arguments. Anything after the alias name that is not consumed is appended to the end of the expansion.
- `-h` is the one-line help shown in `help`, `-H` the long help for `help <alias>`; both go before the `--`.
- An alias that ends in `--` cannot take further options, because they would land inside the expression.

## command regex

For arguments that must land in the middle of a template, or when one command should dispatch on the shape of its input:

```
command regex rlook 's/(.+)/image lookup -rn %1/'
command regex tv 's/(.+)/expression -l objc -- [%1 setHidden:![%1 isHidden]]; (void)[CATransaction flush]/'
command regex getcls 's/(([0-9]|\$|\@|\[).*)/cpo [%1 class]/' 's/(.+)/expression -l swift -O -- type(of: %1)/'
```

- Patterns are tried in order; the first match wins. Unmatched input is discarded with a bare error, so finish with a catch-all `s/(.+)/.../`.
- The `getcls` dispatch above is only a heuristic. Swift persistent variables also start with `$`; use explicit `cpo` or `spo` when the language is known.
- One line only. Join statements with `;`.
- Iterate against a live process by redefining the command, then paste the final version into `~/.lldbinit`.

## Python commands

A command is a function with the five-argument signature, registered from the module's init hook. `exe_ctx` is the context the command runs in, including when a breakpoint action calls it. This is the shape of `scripts/uitools.py`, shipped with this skill:

```python
# uitools.py (excerpt)
import argparse
import shlex
import lldb


class Parser(argparse.ArgumentParser):
    def error(self, message):                  # argparse would call sys.exit inside LLDB
        raise ValueError(self.format_usage().strip())


def vmove(debugger, command, exe_ctx, result, internal_dict):
    """vmove <dx> <dy> <view-expression>: move a view's center and redraw while paused."""
    try:
        parser = Parser(prog="vmove", add_help=False)
        parser.add_argument("dx", type=float)
        parser.add_argument("dy", type=float)
        parser.add_argument("view", nargs="+")
        args = parser.parse_args(shlex.split(command))
        frame = exe_ctx.GetFrame()
        if not frame.IsValid():
            raise ValueError("Pause the process and select a frame first.")
        options = lldb.SBExpressionOptions()
        options.SetLanguage(lldb.eLanguageTypeObjC_plus_plus)
        options.SetTimeoutInMicroSeconds(3000000)
        view = " ".join(args.view)
        # Return a value: an expression whose result is void reports "unknown error".
        value = frame.EvaluateExpression(
            "@import UIKit; UIView *v = (UIView *)({}); CGPoint c = [v center]; "
            "[v setCenter:CGPointMake(c.x + {}, c.y + {})]; [CATransaction flush]; "
            "NSStringFromCGRect([v frame])".format(view, args.dx, args.dy), options)
        if value.GetError().Fail():
            raise ValueError(str(value.GetError()))
        result.AppendMessage("moved, frame is now " + value.GetObjectDescription())
    except ValueError as error:
        result.SetError(str(error))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -o -f {}.vmove vmove".format(__name__))
```

The full file also has `fview <regex>`, which filters `[$window recursiveDescription]` down to matching lines. Load it with `command script import /absolute/path/apple-debugging/scripts/uitools.py`, for the session or from `~/.lldbinit`. Re-running `command script import` reloads the file after an edit; `-o` on `command script add` lets the reload replace the command.

Conventions:

- `command` is the raw argument string; parse it with `shlex` plus `argparse`, and override `error` so a bad argument reports through `result.SetError` instead of raising `SystemExit` inside LLDB.
- Write output through `result.AppendMessage` and errors through `result.SetError`, not `print`, so the output composes with other commands and Xcode.
- For `EvaluateExpression`, set the language, a timeout in microseconds, and check `GetError()`: a failed evaluation still returns an `SBValue`. An expression whose result is `void` also reports an error ("unknown error"), so end the expression with a value you can check. To capture another command's output, run it into your own `SBCommandReturnObject` and check `Succeeded()`.
- Never use `lldb.frame`, `lldb.thread`, `lldb.process`, or `lldb.target` inside a command; they are snapshots for the interactive `script` REPL and go stale while a script runs. Use `exe_ctx`, or the `frame` a breakpoint callback receives.
- Do not evaluate expressions from a formatter merely to display a value. It can recurse, deadlock, or change the process being inspected.
- Prototype API calls in the REPL (`script`), then move them into the file. `script help(lldb.SBFrame)` and `script dir(lldb.SBValue)` show what is available. LLDB's Python is the one bundled with Xcode; check it with `script import sys; print(sys.version)`.

The object model, top to bottom: `SBDebugger` > `SBTarget` (the executable and its modules) > `SBProcess` (memory, threads) > `SBThread` (frames, stepping) > `SBFrame` (variables, registers) > `SBValue` (any value, with children, type, summary, and `GetValueForExpressionPath`).

## Breakpoint callbacks in Python

```
breakpoint set -n "-[UILabel setText:]" -N labels
breakpoint command add -s python labels
> text = frame.EvaluateExpression("(id)$arg3")
> print("label text:", text.GetObjectDescription() if text.GetError().Success() else text.GetError())
> return False          # False continues, True stops
> DONE
```

Or in `labeltools.py` (import it before registering the callback):

```python
import lldb

def log_label(frame, bp_loc, internal_dict):
    opts = lldb.SBExpressionOptions()
    opts.SetLanguage(lldb.eLanguageTypeObjC)
    receiver = frame.EvaluateExpression("(id)$arg1", opts)
    text = frame.EvaluateExpression("(id)$arg3", opts)
    if any(not v.IsValid() or v.GetError().Fail() for v in (receiver, text)):
        print("Could not inspect label arguments; stopping for diagnosis")
        return True
    print("%s <- %s" % (receiver.GetObjectDescription(), text.GetObjectDescription()))
    return False
```

Attach with `breakpoint command add -F labeltools.log_label labels`. The callback receives the `SBFrame` and `SBBreakpointLocation`; get the thread, process, and debugger from the frame when you need them. Avoid stepping or resuming from a stop callback. Return its stop decision and let the controlling session resume. If another script changes debugger async mode, restore the previous mode in `finally`.

## Data formatters

Change how a type prints in `v`, `p`, and the Xcode variables view.

```
type summary add --summary-string "${var.name} / ${var.age}" MyApp.Person
type summary add -x --summary-string "${svar%#} items" "^MyApp\.Queue<.+>$"     # regex type name
type filter add MyApp.Cart --child items --child total                           # show only some children
type summary delete MyApp.Person
type summary delete "^MyApp\.Queue<.+>$"
type filter delete MyApp.Cart
```

Python summary and synthetic children:

```python
import lldb

def trip_summary(valobj, internal_dict):
    dests = valobj.GetChildMemberWithName("destinations")
    n = dests.GetNumChildren()
    if n == 0:
        return "empty trip"
    first = dests.GetChildAtIndex(0).GetSummary()
    last = dests.GetChildAtIndex(n - 1).GetSummary()
    return "%s -> %s (%d stops)" % (first, last, n)


class PairChildren:
    def __init__(self, valobj, internal_dict):
        self.valobj = valobj

    def update(self):
        self.first = self.valobj.GetChildMemberWithName("first")
        self.second = self.valobj.GetChildMemberWithName("second")
        return False  # invalidate cached children after each update

    def num_children(self):
        return 2

    def get_child_index(self, name):
        return {"first": 0, "second": 1}.get(name, -1)

    def get_child_at_index(self, index):
        return [self.first, self.second][index] if index in (0, 1) else None

    def has_children(self):
        return True


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("type summary add -F formatters.trip_summary MyApp.Trip")
    debugger.HandleCommand("type synthetic add --python-class formatters.PairChildren MyApp.Pair")
```

Recent LLDB versions also accept decorators (`@lldb.summary("MyApp.Trip")`, `@lldb.synthetic("MyApp.Pair")`) that register on import. Use fully qualified Swift type names. Summaries affect `v` and `p`; `po` keeps using the type's own description.

## Settings worth persisting

```
settings set target.skip-prologue false
settings set stop-disassembly-display no-debuginfo
settings set target.max-string-summary-length 10000
settings set target.max-children-count 512
settings set target.process.thread.step-avoid-libraries libswiftCore.dylib libobjc.A.dylib
```

## A starter ~/.lldbinit

```
# language shortcuts
command alias cpo expression -l objc -O --
command alias spo expression -l swift -O --
command alias sp expression -l swift --
command alias cp expression -l objc --

# UI
command alias flush expression -l objc -- (void)[CATransaction flush]
command alias -h "Dump the selected window's views" -- pviews expression -l objc -O -- [$window recursiveDescription]
command alias -h "Dump the view controller tree" -- pvc expression -l objc -O -- [[$window rootViewController] _printHierarchy]
command regex tv 's/(.+)/expression -l objc -- [%1 setHidden:![%1 isHidden]]; (void)[CATransaction flush]/'
command regex border 's/(.+)/expression -l objc -- [[%1 layer] setBorderWidth:2]; [[%1 layer] setBorderColor:[[UIColor redColor] CGColor]]; (void)[CATransaction flush]/'

# introspection
command regex ivars 's/(.+)/expression -l objc -O -- [%1 _ivarDescription]/'
command regex methods 's/(.+)/expression -l objc -O -- [%1 _shortMethodDescription]/'
command regex rlook 's/(.+)/image lookup -rn %1/'
command alias args register read arg1 arg2 arg3 arg4 arg5 arg6

# session
command alias reload command source ~/.lldbinit
settings set target.max-string-summary-length 10000
command script import /absolute/path/apple-debugging/scripts/uitools.py
```

Keep it short and commented; the file is read at every launch and errors are easy to miss.

## Third-party command packages

Public LLDB command collections add view-tree, heap-search, class-dump, and tracing commands. Before writing your own, check what is installed: `command script list`, then `help <command>`. Before importing one, read its source: these packages run Python in the debugger, and many commands evaluate code in the target or act on every match (some search commands run an action on each found object). Import a package by absolute path for the session; installing it or adding it to a global init file is a separate change. Older packages can assume Python 2, Intel registers, or `keyWindow`; read the import error instead of reinstalling. Keep them as dependencies: a link or an original explanation does not relicense their code under this skill's license.

Built-in equivalents for the common package commands:

| Need | Built-in way |
|---|---|
| View tree | `[$window recursiveDescription]`, AppKit `[[window contentView] _subtreeDescription]` |
| Find a view or controller | view debugger, or `fview <regex>` from `scripts/uitools.py` |
| Break on an inherited method | runtime IMP lookup, then `breakpoint set -a` (see `debugging-without-source.md`) |
| Watch an Objective-C ivar | ivar offset from `_ivarDescription` or debug info, then `watchpoint set expression` |
| Responder chain | follow `nextResponder` from the selected object (see `view-debugging.md`) |
| Highlight or hide a view | `border` and `tv` regex commands in the starter file above |
| Accessibility labels | Accessibility Inspector, or the element's `accessibilityLabel` and `accessibilityIdentifier` |
| UI-test element tree | `XCUIElement.debugDescription` in the UI-test process |
| Which view got the touch | an auto-continuing `sendEvent:` breakpoint that logs (see `view-debugging.md`) |

A tap logger built on `thread return` swallows the event it reports, so the tap never reaches the app. Use a logging breakpoint that continues instead.

For bounded symbol/method/block helpers, structured SBValue inspection, malloc history, and embedded Python troubleshooting, read [Advanced Python](advanced-python.md). For custom breakpoint resolvers and multi-stage stepping, read [Remote and tooling](remote-and-tooling.md).
