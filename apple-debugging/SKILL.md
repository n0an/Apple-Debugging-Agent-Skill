---
name: apple-debugging
description: Debugs iOS, iPadOS, macOS, watchOS, tvOS, and visionOS apps with LLDB and Xcode. Use when a bug needs a live debugger session, when po or p fail in Swift, when you want to tweak values or test a fix without rebuilding, when a tap or layout misbehaves, when a value changes and nobody knows who wrote it, when reading or symbolicating a crash log, when memory spikes, when writing .lldbinit aliases or Python LLDB commands, or when tracing a process with DTrace.
license: MIT
metadata:
  author: Anton Novoselov
  version: "1.0.0"
---

Drive LLDB and Xcode to find the cause of a bug fast: stop in the right place, look at real state, change it live, and prove a fix before touching the code. Rebuilding is the last resort, not the first move.

Debugging loop: **run, break, inspect, change, repeat**. Every reference below serves one step of that loop.

Debugging process:

1. Reproduce and get a debugger on the process (Xcode run, Run Without Building, attach by name or PID, batch `lldb` from a terminal) using `references/attaching-and-running.md`.
1. Learn or refresh LLDB's command grammar, print commands, language contexts, and `$` variables using `references/fundamentals.md`.
1. Stop in the right place with the right kind of breakpoint (line, column, symbolic, regex, conditional, one-shot, dependent, exception, Swift error, runtime issue) using `references/breakpoints.md`.
1. Inspect state: variables, objects by raw address, registers and `$arg1` in assembly frames, backtraces, threads, images, memory, using `references/inspecting-state.md`.
1. Move through code: step, finish, `thread return`, `thread jump`, drag the instruction pointer, run functions with breakpoints honored, using `references/flow-control.md`.
1. Change state and inject code without rebuilding: mutate values, call methods, auto-continuing breakpoint actions, replace a line, stub a function, flush Core Animation, using `references/modifying-runtime-state.md`.
1. For UI bugs (layout, hit testing, dark mode, animations, SwiftUI re-renders) use `references/view-debugging.md`.
1. For "who wrote this value" and memory problems (watchpoints, memory graph, malloc history, leaks, vmmap, zombies, sanitizers) use `references/watchpoints-and-memory.md`.
1. For crash logs, dSYMs, UUIDs, `atos`, source maps, and the meaning of exception types use `references/crashes-and-symbolication.md`.
1. When `po` or `p` fail in Swift, types are missing, or variables are optimized out, use `references/swift-debugging.md`.
1. When you type the same command twice, persist it: aliases, regex commands, Python commands, data formatters, `.lldbinit` layout, using `references/custom-commands.md`.
1. To trace a whole process or Apple's code without source (DTrace, breakpoint tracers, stop hooks, unified logging) use `references/tracing-and-dtrace.md`.
1. For step-by-step recipes for the most common situations use `references/playbooks.md`.
1. Before reporting, check `references/anti-patterns.md` for the mistakes that waste the most time.

If doing partial work, load only the relevant reference files.


## Two ways to work

**You hold the debugger.** You have a terminal, the app runs in the Simulator or on the Mac, and you can attach with `xcrun lldb` in batch mode. Do it yourself: attach, run the commands, read the output, detach. See the "Driving LLDB from a terminal or an agent" section in `references/attaching-and-running.md`.

**The user holds the debugger.** The app runs in Xcode on their machine or device. Give exact console commands one at a time, say what output to expect, and keep their session alive: never ask for a rebuild to test a hypothesis that a breakpoint action or an `expression` can test now.

In both modes the deliverable is the same: what you observed, what it proves, the fix, and how it was verified live.


## Task-based routing

Match the user's situation to the read order. Load only what you need.

### "Something is wrong on screen, I don't want to rebuild"
1. `references/attaching-and-running.md` - attach to the running app or Run Without Building
2. `references/view-debugging.md` - find the view, copy its pointer, inspect constraints
3. `references/modifying-runtime-state.md` - mutate, flush, verify, then port the fix to code

### "I want to test a one-line fix live"
1. `references/modifying-runtime-state.md` - auto-continuing breakpoint with an `expression` action, `thread jump` + `expression` to replace a line
2. `references/breakpoints.md` - conditions and actions in Xcode and on the console

### "Who changes this property / label / variable?"
1. `references/breakpoints.md` - symbolic breakpoint on the setter, `po $arg1`, dependent one-shot breakpoints
2. `references/watchpoints-and-memory.md` - watchpoint when no setter is involved (`inout`, direct writes)

### "A tap or gesture does nothing"
1. `references/view-debugging.md` - the hit-testing checklist, `sendEvent:` tracer, responder chain, target-action lookup
2. `references/playbooks.md` - the full recipe

### "po fails / the variables view is empty / types are missing"
1. `references/swift-debugging.md` - `v` first, `swift-healthcheck`, module and dSYM problems, source maps, optimized code
2. `references/fundamentals.md` - language contexts and `$` variables

### "I have a crash log"
1. `references/crashes-and-symbolication.md` - open it in Xcode against the project, `atos`, UUID matching, exception types
2. `references/breakpoints.md` - exception and Swift error breakpoints to catch it live

### "Memory is too high / the app gets killed"
1. `references/watchpoints-and-memory.md` - footprint model, memory graph, `vmmap`, `heap`, `leaks`, `malloc_history`

### "I have no source for this code"
1. `references/inspecting-state.md` - `image lookup`, registers, `$arg1`, calling conventions
2. `references/breakpoints.md` - symbolic and regex breakpoints scoped to a module
3. `references/tracing-and-dtrace.md` - trace every method of a class with a breakpoint tracer or DTrace

### "Make this repeatable" (aliases, scripts, formatters)
1. `references/custom-commands.md` - `.lldbinit`, `command alias`, `command regex`, Python commands, `type summary`

### "Drive the debugger for me from the terminal"
1. `references/attaching-and-running.md` - batch mode, attach by name, launch suspended, always detach


## Decision trees

### Which print command?

```
Need to see a variable or a field of it, in Swift?
  -> v <expr>            (frame variable: no compile, dynamic types resolved per step)

Need to evaluate an expression, call a method, or compute something?
  -> p <expr>            (dwim-print since Xcode 15: tries frame variable, then expression)

Need the object's own description (debugDescription / description)?
  -> po <expr>

Stopped in Swift but holding a raw address or need an Objective-C API?
  -> expression -l objc -O -- (id)0x...   (alias it as cpo)

Expression fails with type or module errors?
  -> v first, then swift-healthcheck, then references/swift-debugging.md
```

### Which way to stop?

```
Know the file and line?                  -> line breakpoint; column breakpoint for closures on one line
Know the symbol but not the file?        -> symbolic breakpoint (-n), scope with --shlib
Know only a pattern (Swift mangling)?    -> rb <regex> [-s Module], find it first with image lookup -rn
Fires too often?                         -> condition (-c), ignore count (-i), one-shot (-o 1),
                                            dependent tbreak from an auto-continue action,
                                            or raise(SIGSTOP) in code for million-hit loops
Value changes, no setter called?         -> watchpoint
Uncaught NSException or C++ throw?       -> Exception breakpoint (po $arg1 at objc_exception_throw)
Swift throw?                             -> Swift Error breakpoint
Main thread / layout / sanitizer issue?  -> Runtime Issue breakpoint (enable the checker in the scheme)
Only need a log, not a stop?             -> breakpoint action + auto-continue (-C "..." -G1)
```

### Who changed this value?

```
Setter exists and is called?        -> symbolic breakpoint on the setter, po $arg1 / bt
Swift property?                     -> rb Module.Type.prop.setter
Written through inout or raw ptr?   -> watchpoint on the ivar address (class-table dump for the offset)
Object created where?               -> Malloc Stack Logging + malloc_history / memory graph creation backtrace
```

### Rebuild or not?

```
Change a constant, color, frame, flag?            -> expression + CATransaction flush, no rebuild
Add a missing call or line?                       -> auto-continuing breakpoint with expression action
Skip or replace a line?                           -> thread jump --by 1 (or drag the PC) + expression
Stub a function's return?                         -> breakpoint at entry, thread return <value>, auto-continue
Hypothesis confirmed live?                        -> now edit the code, delete the injecting breakpoints, rebuild
Hot path hit millions of times?                   -> rebuild with an if + raise(SIGSTOP)
```

### Where does a repeated command live?

```
Static text, maybe %1 arguments?   -> command alias (in ~/.lldbinit)
Needs regex dispatch on input?     -> command regex (chain patterns, catch-all last)
Needs logic, options, output?      -> Python command via command script import
Needs to change how a type prints? -> type summary add (string, or Python), @DebugDescription in Swift 6
```


## Core Instructions

- Prefer the live process over a rebuild. Tweak values, inject the missing line, stub the return, and confirm the hypothesis in the running app. Edit source only after the debugger proved the fix, then delete every injecting breakpoint before the next run so the fix does not execute twice.
- In Swift, reach for `v` first. It reads memory with debug info and never compiles. Use `p` for expressions and `po` only when you need the object's description or a side effect. When `po` fails, `v` usually still works.
- Know the language context. Stopped in Swift means Swift expressions; stopped in Objective-C or paused with the pause button means Objective-C. A raw address like `0x7f...` is an integer in Swift and an object in Objective-C: use `expression -l objc -O -- (id)0x...` (alias `cpo`) or `unsafeBitCast(0x..., to: T.self)` in Swift.
- Persistent debugger variables start with `$` (`e let $vc = ...`, `e id $view = (id)0x...`). Results are auto-named `$R0`, `$R1`, `$0`. They do not cross language contexts.
- Put `--` before arguments that start with `-`, and use backticks to splice a frame value into another context: `expression -l objc -O -- [`self.view` recursiveDescription]`.
- Capital `-C` is a breakpoint command, lowercase `-c` is a condition. `-G1` auto-continues. `-o 1` makes a breakpoint one-shot.
- A symbolic breakpoint on a method the class does not override never resolves. Break on the implementing superclass and add a class condition, or use the Xcode breakpoint editor's module field plus a condition on `$arg1`.
- In frames without source, arguments live in registers: `$arg1` is the receiver, `$arg2` the selector (cast with `(SEL)`), `$arg3` the first parameter. Read them at the function entry, before the body runs.
- After mutating UI from the console, flush Core Animation: `e CATransaction.flush()` in Swift, `e (void)[CATransaction flush]` in Objective-C. The render server is a separate process and keeps running while you are paused.
- `thread jump` only moves the program counter. Skipping a line that initializes a variable or releases an object corrupts state. Jump over one line at a time, never backward, and prefer `thread return` or a breakpoint action when you can.
- Hot breakpoints slow the app even when they do not stop. Use conditions and ignore counts for hundreds of hits, a dependent one-shot breakpoint for "only after X", and for millions of hits recompile with `if condition { raise(SIGSTOP) }`.
- Hardware gives you about four watchpoints of at most 8 bytes each. Watch the exact ivar size (a `Bool` is 1 byte). `watchpoint modify` without an id applies to every watchpoint.
- A crash log is only useful with the matching dSYM: compare the UUID in Binary Images with `dwarfdump --uuid`. Open the log in Xcode against the project before reaching for `atos -i`.
- Inside Python scripts, never use `lldb.frame`, `lldb.target`, or `lldb.process`. They are REPL conveniences and go stale mid-script. Walk from the `debugger` or `frame` you were handed.
- DTrace needs SIP disabled, `sudo`, and runs on macOS or the Simulator only. Always list probes with `-l` before running an action so you know how many will fire.
- When you drive LLDB yourself, use `xcrun lldb --batch -o ...`, end the command list with `detach` for an attached process, wrap the call in a timeout, and never leave a process stopped when you are done.
- Report what the debugger showed, not what you assumed. A hypothesis is confirmed when the live process behaves differently after your injected change.


## Output Format

When you drove the debugger, report in this order:

1. **Observed**: the exact state you saw (values, backtrace frames, view addresses), quoted from the console.
2. **Cause**: the single sentence that explains the bug.
3. **Verified live**: what you changed in the running process and what happened.
4. **Code fix**: the diff to apply, plus "delete these breakpoints before rerunning" if any inject code.

When the user drives Xcode, give a numbered list of actions. Each step is one console command or one click, followed by what they should see. Keep Objective-C and Swift contexts explicit in each command. Example:

1. Pause the app, then in the console run `expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]`. Find the `UIButton` whose frame width is wrong and copy its address.
2. `e -l objc -O -- (id)0x600003a1c2e0` to confirm it is the right button.
3. `e -l objc -- (void)[(UIView *)0x600003a1c2e0 setBackgroundColor:[UIColor redColor]]` then `e -l objc -- (void)[CATransaction flush]`. The button turns red in the Simulator while still paused.
4. Now the fix: `e -l objc -- [(NSLayoutConstraint *)0x600002d11f00 setConstant:328]` and flush again. The layout matches the design, so change the constant in `LoginViewController.swift` and rebuild.

End of example.


## References

- `references/fundamentals.md` - how LLDB works, command grammar, help, print commands (`v`, `p`, `po`, `expression`), language contexts, `$` variables, formats, settings, Xcode UI to LLDB mapping.
- `references/attaching-and-running.md` - Run Without Building, attach by name/PID/wait-for, stdout trade-off, launch arguments and environment, scheme diagnostics, per-project `.lldbinit`, driving LLDB in batch mode from a terminal or an agent.
- `references/breakpoints.md` - every breakpoint kind, Xcode breakpoint editor fields, conditions, actions, auto-continue, one-shot and dependent breakpoints, names, unresolved breakpoint diagnosis, stop hooks, `breakpoint write/read`.
- `references/inspecting-state.md` - frames, threads, variables, raw addresses, registers and calling conventions, `image lookup`, memory and disassembly, Objective-C runtime introspection.
- `references/flow-control.md` - stepping, `step -a0`, `thread until`, `thread return`, `thread jump`, dragging the PC, stepping one thread, `expression -i0`.
- `references/modifying-runtime-state.md` - mutate values, call methods, declare variables and functions in the debugger, inject fixes with breakpoint actions, replace a line, stub a function, flush Core Animation, prototype layout.
- `references/view-debugging.md` - Xcode view debugger techniques, console equivalents, Auto Layout diagnosis, hit testing, target-action, animations, appearance overrides, SwiftUI notes.
- `references/watchpoints-and-memory.md` - watchpoints, memory graph, Malloc Stack Logging, `vmmap`/`heap`/`leaks`/`malloc_history`, zombies, sanitizers, `memory history`.
- `references/crashes-and-symbolication.md` - crash log anatomy, dSYM and UUID matching, `atos`, ASLR slide, `crashlog`, source maps, exception types, catching exceptions live.
- `references/swift-debugging.md` - why `po` fails while `v` works, `swift-healthcheck`, modules and dSYMs, optimized code, type names and mangling, `@DebugDescription`, concurrency and SwiftUI specifics.
- `references/custom-commands.md` - `.lldbinit` locations, `command alias`, `command regex`, Python commands, breakpoint callbacks, type summaries and synthetic children, a starter `.lldbinit`.
- `references/tracing-and-dtrace.md` - breakpoint tracers, stop hooks, unified logging, DTrace providers and scripts, static probes.
- `references/playbooks.md` - step-by-step recipes for the common cases.
- `references/anti-patterns.md` - mistakes that cost the most time, with fixes.

WWDC sessions behind this material: WWDC18 412 "Advanced Debugging with Xcode and LLDB", WWDC18 416 "iOS Memory Deep Dive", WWDC19 429 "LLDB: Beyond po", WWDC21 10209 "Discover breakpoint improvements", WWDC21 10211 "Symbolication: Beyond the basics", WWDC22 110370 "Debug Swift debugging with LLDB", WWDC24 10198 "Run, Break, Inspect: Explore effective debugging in LLDB".
