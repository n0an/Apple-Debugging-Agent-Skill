# Custom commands

Any command typed twice belongs in `~/.lldbinit`. LLDB offers three tiers: aliases for fixed text, regex commands for input you need to place inside a template, and Python for anything with logic, options, or formatted output.

## Where init files live

| File | Loaded when |
|---|---|
| `~/.lldbinit-Xcode` | only when Xcode drives LLDB |
| `~/.lldbinit-lldb` | only for the terminal `lldb` |
| `~/.lldbinit` | always, after the contextual file |
| scheme > Run > Options > LLDB Init File | per project, after the global files (Xcode 14+) |

Init files run before the process is attached, so they cannot evaluate expressions against the target. They can define aliases, import scripts, set settings, and configure breakpoint names. Syntax errors in them are reported quietly at startup; reload during a session to see them:

```
command alias reload command source ~/.lldbinit
```

## command alias

```
command alias cpo expression -l objc -O --
command alias spo expression -l swift -O --
command alias sp expression -l swift --
command alias flush expression -l objc -- (void)[CATransaction flush]
command alias args register read arg1 arg2 arg3 arg4 arg5 arg6
command alias bfl breakpoint set -f %1 -l %2                     # bfl Foo.swift 42
command alias -H "Print the key window's view tree" -h "Dump views" -- pviews expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]
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
- Input that starts with `[`, `@`, `$`, or a digit is almost always Objective-C; everything else is probably Swift. That heuristic is how `getcls` above picks a language.
- One line only. Join statements with `;`.
- Iterate against a live process by redefining the command, then paste the final version into `~/.lldbinit`.

## Python commands

A command is a function with a fixed signature, registered from the module's init hook:

```python
# ~/lldb/uitools.py
import lldb
import shlex
import argparse


def flush(debugger):
    debugger.HandleCommand("expression -l objc -- (void)[CATransaction flush]")


def vmove(debugger, command, result, internal_dict):
    """vmove <dx> <dy> <view-expression>: nudge a view and redraw while paused."""
    parser = argparse.ArgumentParser(prog="vmove")
    parser.add_argument("dx", type=float)
    parser.add_argument("dy", type=float)
    parser.add_argument("view", nargs="+")
    try:
        args = parser.parse_args(shlex.split(command))
    except SystemExit:
        result.SetError("usage: vmove <dx> <dy> <view-expression>")
        return
    view = " ".join(args.view)
    expr = ("expression -l objc -- CGPoint $c = [(UIView *)(%s) center]; "
            "[(UIView *)(%s) setCenter:CGPointMake($c.x + %f, $c.y + %f)]"
            % (view, view, args.dx, args.dy))
    debugger.HandleCommand(expr)
    flush(debugger)
    result.AppendMessage("moved %s by (%g, %g)" % (view, args.dx, args.dy))


def fview(debugger, command, result, internal_dict):
    """fview <regex>: list views in the key window whose description matches."""
    import re
    res = lldb.SBCommandReturnObject()
    interp = debugger.GetCommandInterpreter()
    interp.HandleCommand(
        "expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]", res)
    if not res.Succeeded():
        result.SetError(res.GetError())
        return
    pattern = re.compile(command.strip())
    for line in res.GetOutput().splitlines():
        if pattern.search(line):
            result.AppendMessage(line.strip(" |"))


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f uitools.vmove vmove")
    debugger.HandleCommand("command script add -f uitools.fview fview")
```

Load it from `~/.lldbinit`: `command script import ~/lldb/uitools.py`. During development, re-import the file (`command script import` again) or `command source ~/.lldbinit` to pick up changes.

Conventions:

- `command` is the raw argument string; parse it with `shlex` plus `argparse` or `optparse`.
- Write output through `result.AppendMessage` and errors through `result.SetError`, not `print`, so the output composes with other commands and Xcode.
- Capture another command's output with your own `SBCommandReturnObject`, as `fview` does, instead of letting it hit the console.
- Never use `lldb.frame`, `lldb.thread`, `lldb.process`, or `lldb.target` inside a command; they are snapshots for the interactive `script` REPL and go stale while a script runs. Walk from `debugger.GetSelectedTarget()` down to the process, thread, and frame.
- Prototype API calls in the REPL (`script`), then move them into the file. `script help(lldb.SBFrame)` and `script dir(lldb.SBValue)` show what is available.
- LLDB's Python is the one bundled with Xcode, Python 3. Check with `script import sys; print(sys.version)`.

The object model, top to bottom: `SBDebugger` > `SBTarget` (the executable and its modules) > `SBProcess` (memory, threads) > `SBThread` (frames, stepping) > `SBFrame` (variables, registers) > `SBValue` (any value, with children, type, summary, and `GetValueForExpressionPath`). `target.EvaluateExpression("...")` returns an `SBValue`; always check `.error.Success()` because a failed evaluation still returns an object.

## Breakpoint callbacks in Python

```
breakpoint set -n "-[UILabel setText:]" -N labels
breakpoint command add -s python labels
> text = frame.EvaluateExpression("(id)$arg3", lldb.SBExpressionOptions())
> print("label text:", text.GetObjectDescription())
> return False          # False continues, True stops
> DONE
```

Or in a file:

```python
def log_label(frame, bp_loc, internal_dict):
    opts = lldb.SBExpressionOptions()
    opts.SetLanguage(lldb.eLanguageTypeObjC)
    receiver = frame.EvaluateExpression("(id)$arg1", opts).GetObjectDescription()
    text = frame.EvaluationExpression if False else frame.EvaluateExpression("(id)$arg3", opts).GetObjectDescription()
    print("%s <- %s" % (receiver, text))
    return False
```

Attach with `breakpoint command add -F uitools.log_label labels`. The callback receives the `SBFrame` and `SBBreakpointLocation`; get the thread, process, and debugger from the frame when you need them. Set `debugger.SetAsync(False)` before stepping inside a callback so the step completes before the next line runs.

## Data formatters

Change how a type prints in `v`, `p`, and the Xcode variables view.

```
type summary add --summary-string "${var.name} / ${var.age}" MyApp.Person
type summary add -x --summary-string "${svar%#} items" "^MyApp\.Queue<.+>$"     # regex type name
type filter add MyApp.Cart --child items --child total                           # show only some children
type summary delete MyApp.Person
type summary clear
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
        return True

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
command alias -h "Dump the key window's views" -- pviews expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]
command alias -h "Dump the view controller tree" -- pvc expression -l objc -O -- [[[[UIApplication sharedApplication] keyWindow] rootViewController] _printHierarchy]
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
command script import ~/lldb/uitools.py
```

Keep it short and commented; the file is read at every launch and errors are easy to miss.
