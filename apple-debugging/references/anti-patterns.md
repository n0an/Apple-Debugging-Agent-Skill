# Anti-patterns

Mistakes that cost the most time in debugging sessions, with the fix for each.

## Workflow

- **Rebuilding to test a guess.** Adding a `print`, rebuilding, and re-reproducing costs minutes per iteration. Pause, `expression` the change, or inject it with an auto-continuing breakpoint, and only rebuild once the hypothesis is confirmed. The exceptions are hot paths that need compiled instrumentation and state the debugger cannot reach.
- **Leaving injecting breakpoints enabled after fixing the code.** The fix runs twice: once from source, once from the breakpoint. Delete or disable them before the next run.
- **Stopping where the symptom is instead of where the decision is.** A wrong label value stops you in `setText:`; the bug is one or two frames up. Read the backtrace and move up before poking at state.
- **Trusting a conclusion the live process did not confirm.** If you changed something and the behavior did not change, the theory is wrong, or the change hit the wrong object, thread, or moment. Find out which before building on it.

## Printing

- **`po` for everything in Swift.** `po` evaluates the expression and then runs the object's description code, so it is the slowest option and the first to break. Use `v` for variables and paths; `p` for expressions; `po` only for descriptions. When `po` errors out, `v` usually still works.
- **Raw address in the Swift context.** `po 0x600003a1c2e0` prints a number. Use `expression -l objc -O -- (id)0x600003a1c2e0` (alias `cpo`) or `unsafeBitCast(0x600003a1c2e0, to: UIView.self)`.
- **Pausing and typing Swift.** The pause button usually selects a system frame, so the expression language is Objective-C even in a pure Swift app, and Swift syntax and Swift `$` variables fail. Select your Swift frame with `frame select N`, use `-l swift`, or stop at a breakpoint in Swift code instead.
- **A `$`-less debugger variable.** `expression let vc = ...` is gone after that line. Use `$vc`.
- **Expecting a `$` variable in the other language.** They do not cross contexts; recreate it.
- **Missing `--` before an expression that starts with `-`.** LLDB parses it as an option.
- **Objective-C expression fails with an unknown method or type.** Add `@import UIKit;` to the expression, or cast the receiver and the return type.

## Breakpoints

- **`-c` when you meant `-C`.** Lowercase is a condition, uppercase is a command. Both are accepted silently.
- **A symbolic breakpoint on a method the class does not implement.** It never resolves (dashed icon). Break on the implementing superclass with a class condition on `$arg1`.
- **A typo in a symbol.** Find the exact spelling with `image lookup -rn` before creating the breakpoint.
- **Regex breakpoints without a module scope.** `rb .` over UIKit resolves to hundreds of thousands of locations and takes minutes on a device. Add `-s MyApp` or a file filter.
- **Expensive conditions on hot paths.** Condition evaluation and debugger round trips add overhead; compiled expressions can be cached. Use an ignore count or a dependent one-shot breakpoint; for millions of hits, `raise(SIGSTOP)` behind an `if` in code.
- **Exception breakpoint catching internal throws.** Some frameworks throw and catch as part of normal operation. Narrow it to Objective-C, add a condition on the reason, or disable it until you need it.
- **Expecting the Exception breakpoint to catch Swift errors.** Swift `throw` needs the Swift Error breakpoint.
- **Surprised by two hits on one Swift method.** The thunk and body can be separate locations. Inspect and disable only the unwanted location.
- **Breakpoint on a path Xcode cannot match.** Moved the project or built elsewhere? `breakpoint list -v` shows the path used; `settings set target.source-map` fixes it, or set breakpoints by basename.

## Flow control

- **Jumping over initialization or cleanup.** `thread jump` and dragging the instruction pointer only move the pc. Even one line can include initialization or cleanup. Inspect disassembly; use a reversible data change where possible.
- **`thread return` mid-function.** Skipped cleanup (locks, counters, ARC releases) leaks or deadlocks later. Return at the first line of the function.
- **Calling a method from the console and wondering why the breakpoint inside did not fire.** Expressions ignore breakpoints by default; add `-i 0`.
- **`finish` at the top frame.** There is nothing to return to; the process just resumes.

## UI

- **Changed a view, nothing happened.** Flush: `expression -l objc -- (void)[CATransaction flush]` (or `CATransaction.flush()` in Swift). On macOS also `[view display]`.
- **Not seeing the popover or second window in the view debugger.** Each window is a separate root item; collapse the first one.
- **A view "centered wrong" that is actually clipped.** Enable Show Clipped Content; the superview extends past the window.
- **Colors that break in dark mode.** An unnamed color can still be dynamic or semantic. Verify the actual trait-dependent behavior. Check the creation backtrace.
- **Capturing a macOS app's hierarchy after its popover closed.** Command-click the capture button so Xcode does not activate.

## Memory and watchpoints

- **Too many or too wide watchpoints.** Hardware gives only a few (often four on Apple silicon), and a wide or unaligned range uses several. Watch the exact field size; `watchpoint list` shows what is left.
- **`watchpoint modify` without an id.** Default selection has changed across versions. Always specify the ID and use `-c ""` to clear a condition.
- **Watchpoint from a previous run.** Addresses change on relaunch; set it again.
- **Memory warnings handled by clearing a compressed cache.** Touching compressed pages decompresses them and uses more memory at the worst moment; change policy (stop caching for a while) instead.
- **Judging image memory by file size.** Cost is width times height times bytes per pixel after decoding.
- **Reading `isa` directly.** Its spare bits hold reference counts and flags; use `object_getClass`.

## Crashes

- **Symbolicating with the wrong dSYM.** Compare UUIDs first. Download the dSYM for that exact build.
- **Ignoring `-i` on `atos`.** Inlined frames disappear from optimized backtraces without it.
- **Reading only the crashed frame.** The cause is often several frames up or in another thread (`bt all`).
- **Treating `0xbaaaaaad` as a crash.** It is a stackshot.

## Scripts and setup

- **Using `lldb.frame` or `lldb.target` inside a Python command.** They are stale during a script; walk from the `debugger` or `frame` parameter.
- **Not checking `SBValue.GetError()`.** A failed expression still returns a value object.
- **Putting target-dependent commands in `.lldbinit`.** Init files run before attach. Use a stop hook or a per-scheme init file sourced later for things that need the process.
- **Pasting a long multi-line expression into the Xcode console.** It can hang. One line per expression, or a Python command.
- **Disabling SIP just to try DTrace.** Probe/provider availability and target protections vary. Inspect the error and use a supported alternative; security changes need explicit approval.
- **Assuming a trailing `detach` always runs.** Batch errors can abort it and an auto-continuing tracer can block forever. Use an interruptible session and verify cleanup.
