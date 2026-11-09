---
name: apple-debugging
description: Debugs iOS, iPadOS, macOS, watchOS, tvOS, and visionOS apps with LLDB and Xcode. Use when a bug needs a live debugger session, when po or p fail in Swift, when you want to tweak values or test a fix without rebuilding, when a tap, focus change, or layout misbehaves, when a value changes and nobody knows who wrote it, when reading or symbolicating a crash log, when memory spikes or the app hangs, when a framework has no source and you need registers, assembly, Mach-O, or Objective-C runtime lookup, when attach fails or the app exits under the debugger, when testing a hook, interposed call, or swizzled method in your own app, when writing .lldbinit aliases or Python LLDB commands, or when tracing a process with DTrace.
license: MIT
metadata:
  author: Anton Novoselov
  version: "1.1.0"
---

Drive LLDB and Xcode to find the cause of a bug fast: stop in the right place, look at real state, change it live, and prove a fix before touching the code. Rebuilding is the last resort, not the first move. Once the live experiment confirms the cause, fix the source and verify it in a clean run without the injected behavior.

Debugging loop: **run, break, inspect, change, repeat**. Every reference below serves one step of that loop.

Debugging process:

1. Reproduce and get a debugger on the process (Xcode run, Run Without Building, attach by name or PID, batch `lldb` from a terminal) using `references/attaching-and-running.md`.
1. Learn or refresh LLDB's command grammar, print commands, language contexts, and `$` variables using `references/fundamentals.md`.
1. Stop in the right place with the right kind of breakpoint (line, column, symbolic, regex, conditional, one-shot, dependent, exception, Swift error, runtime issue) using `references/breakpoints.md`.
1. Inspect state: variables, objects by raw address, registers and `$arg1` in assembly frames, backtraces, threads, images, memory, using `references/inspecting-state.md`.
1. Move through code: step, finish, `thread return`, `thread jump`, drag the instruction pointer, run functions with breakpoints honored, using `references/flow-control.md`.
1. Change state and inject code without rebuilding: mutate values, call methods, auto-continuing breakpoint actions, replace a line, stub a function, flush Core Animation, using `references/modifying-runtime-state.md`.
1. For UI bugs (scene and window selection, layout, hit testing, keyboard focus, dark mode, animations, SwiftUI re-renders) use `references/view-debugging.md`.
1. For "who wrote this value" and memory problems (watchpoints, memory graph, malloc history, leaks, vmmap, zombies, sanitizers, jetsam) use `references/watchpoints-and-memory.md`.
1. For crash logs, dSYMs, UUIDs, `atos`, source maps, core files, and the meaning of exception types use `references/crashes-and-symbolication.md`.
1. When `po` or `p` fail in Swift, types are missing, or variables are optimized out, use `references/swift-debugging.md`.
1. For code without source: identify the binary and slice, translate addresses, find inherited Objective-C implementations, read Mach-O structure, using `references/debugging-without-source.md`. For registers, calling conventions, arm64 instructions, stack frames, and DWARF locations use `references/assembly-and-abi.md`.
1. For blocks, class dumps per image, stripped Objective-C stacks, heap instances, singleton storage, cross-references, and Simulator system processes use `references/runtime-memory.md`.
1. To load a diagnostic library, interpose a C call, swizzle an Objective-C method in your own app, or forward a Simulator launch environment use `references/dynamic-loading-and-interposition.md`.
1. When attach fails, a library is rejected, or the app exits under a debugger (signing, entitlements, hardened runtime, `PT_DENY_ATTACH`) use `references/signing-and-attach-diagnostics.md`.
1. When you type the same command twice, persist it: aliases, regex commands, Python commands, data formatters, `.lldbinit` layout, third-party command packages, using `references/custom-commands.md`. For structured `SBValue` work, allocation histories, and the bundled helper commands use `references/advanced-python.md`.
1. To trace a whole process or Apple's code without source (DTrace, breakpoint tracers, stop hooks, unified logging, hang sampling) use `references/tracing-and-dtrace.md`. For recursion-aware timing, syscall arguments, and destructive DTrace actions use `references/advanced-dtrace.md`.
1. For remote `debugserver` sessions, `lldb-dap`, LLDB's MCP server, custom breakpoint resolvers, and scripted processes or thread plans use `references/remote-and-tooling.md`.
1. For step-by-step recipes for the most common situations use `references/playbooks.md`.
1. Before reporting, check `references/anti-patterns.md` for the mistakes that waste the most time.

If doing partial work, load only the relevant reference files.


## Two ways to work

**You hold the debugger.** You have a terminal, the app runs in the Simulator or on the Mac, and you can attach with `xcrun lldb`. Do it yourself: attach, run the commands, read the output, detach. A finite snapshot is a batch call; a trace that waits for the user is a batch call with an in-LLDB deadline. See "Driving LLDB from a terminal or an agent" in `references/attaching-and-running.md`. If Xcode already debugs the process, do not attach a second debugger: work through the user's console instead.

**The user holds the debugger.** The app runs in Xcode on their machine or device. Give exact console commands one at a time, say what output to expect, and keep their session alive: never ask for a rebuild to test a hypothesis that a breakpoint action or an `expression` can test now.

In both modes the deliverable is the same: what you observed, what it proves, the fix, and how it was verified live and then in a clean run.


## Task-based routing

Match the user's situation to the read order. Load only what you need.

### "Something is wrong on screen, I don't want to rebuild"
1. `references/attaching-and-running.md` - attach to the running app or Run Without Building
2. `references/view-debugging.md` - select the scene's window, find the view, copy its pointer, inspect constraints
3. `references/modifying-runtime-state.md` - mutate, flush, verify, then port the fix to code

### "I want to test a one-line fix live"
1. `references/modifying-runtime-state.md` - auto-continuing breakpoint with an `expression` action, `thread jump` + `expression` to replace a line
2. `references/breakpoints.md` - conditions and actions in Xcode and on the console

### "Who changes this property / label / variable?"
1. `references/breakpoints.md` - symbolic breakpoint on the setter, `po $arg1` at entry, dependent one-shot breakpoints
2. `references/watchpoints-and-memory.md` - watchpoint when no setter is involved (`inout`, direct writes)

### "A tap or gesture does nothing" / "focus jumps to the wrong field"
1. `references/view-debugging.md` - the hit-testing checklist, `sendEvent:` tracer, responder chain, target-action lookup, `becomeFirstResponder` tracing
2. `references/playbooks.md` - the full recipe

### "po fails / the variables view is empty / types are missing"
1. `references/swift-debugging.md` - `v` first, `swift-healthcheck`, module and dSYM problems, source maps, optimized code
2. `references/fundamentals.md` - language contexts and `$` variables

### "I have a crash log"
1. `references/crashes-and-symbolication.md` - open it in Xcode against the project, `atos`, UUID matching, exception types
2. `references/breakpoints.md` - exception and Swift error breakpoints to catch it live

### "Memory is too high / the app gets killed"
1. `references/watchpoints-and-memory.md` - footprint model, memory graph, `vmmap`, `heap`, `leaks`, `malloc_history`, jetsam reports
2. `references/advanced-python.md` - allocation stack logging and its limits

### "The app hangs"
1. `references/tracing-and-dtrace.md` - sample first, compare repeated stacks
2. `references/playbooks.md` - the hang recipe, then targeted LLDB inspection

### "I have no source for this code"
1. `references/debugging-without-source.md` - loaded image, slice, UUID, address spaces, runtime method lookup
2. `references/assembly-and-abi.md` - arguments and returns per ABI, arm64 instructions, frames
3. `references/breakpoints.md` - symbolic and regex breakpoints scoped to a module
4. `references/runtime-memory.md` - class dumps, stripped stacks, blocks, heap instances, singletons
5. `references/tracing-and-dtrace.md` - trace every method of a class with a breakpoint tracer or DTrace

### "I need to hook this call in my app"
1. `references/dynamic-loading-and-interposition.md` - pick the mechanism, then the `dlopen`, interposing, or saved-IMP recipe
2. `references/signing-and-attach-diagnostics.md` - when the library is not loaded or is rejected

### "Attach is denied / the app quits as soon as the debugger is on"
1. `references/signing-and-attach-diagnostics.md` - diagnose the failing layer, inspect signatures, own-app anti-debug checks
2. `references/attaching-and-running.md` - prerequisites and Developer Mode

### "Make this repeatable" (aliases, scripts, formatters)
1. `references/custom-commands.md` - `.lldbinit`, `command alias`, `command regex`, Python commands, `type summary`
2. `references/advanced-python.md` - `SBValue` discipline, expression ownership, the bundled `adb-*` commands

### "Drive the debugger for me from the terminal"
1. `references/attaching-and-running.md` - batch mode, command files, deadlines, detach and ownership rules

### "Debug over the network, from an editor, or through MCP"
1. `references/remote-and-tooling.md` - `debugserver`, `lldb-dap`, `protocol-server start MCP`, resolvers, scripted processes


## Decision trees

### Which print command?

```
Need to see a variable or a field of it, in Swift?
  -> v <expr>            (frame variable: no compile, dynamic types resolved per step)

Need to evaluate an expression, call a method, or compute something?
  -> p <expr>            (dwim-print since Xcode 15: tries frame variable, then expression)

Need the object's own description (debugDescription / description)?
  -> po <expr>           (runs description code: avoid it in deadlock or lifetime investigations)

Stopped in Swift but holding a raw address of a live Objective-C object?
  -> expression -l objc -O -- (id)0x...   (alias it as cpo; the cast does not validate the pointer)

Must not run any target code (corruption, locks, lifetime)?
  -> frame variable -d no-run-target -R <expr>

Expression fails with type or module errors?
  -> v first, then swift-healthcheck, then references/swift-debugging.md
```

### Which way to stop?

```
Know the file and line?                  -> line breakpoint; column breakpoint for closures on one line
Know the symbol but not the file?        -> symbolic breakpoint (-n), scope with --shlib
Know only a pattern (Swift mangling)?    -> rb <regex> [-s Module], find it first with image lookup -rn
Need the arguments in registers?         -> add -K false to stop before the prologue
Fires too often?                         -> condition (-c), ignore count (-i), one-shot (--one-shot true),
                                            dependent one-shot breakpoint armed from an auto-continue action,
                                            or raise(SIGSTOP) in code for million-hit loops
Value changes, no setter called?         -> watchpoint
Uncaught NSException or C++ throw?       -> Exception breakpoint (po $arg1 at objc_exception_throw)
Swift throw?                             -> Swift Error breakpoint (also stops on throws that get caught)
Main thread / layout / sanitizer issue?  -> Runtime Issue breakpoint (enable the checker in the scheme)
Only need a log, not a stop?             -> breakpoint action + auto-continue (-C "..." -G1)
```

### Who changed this value?

```
Setter exists and is called?        -> symbolic breakpoint on the setter, po $arg1 at entry / bt
Swift property?                     -> rb Module.Type.prop.setter
Written through inout or raw ptr?   -> watchpoint on the field address, sized to the field
Singleton set up somewhere?         -> watchpoint on the static pointer storage, before first access
Object created where?               -> Malloc Stack Logging + malloc_history / memory graph creation backtrace
```

### Rebuild or not?

```
Change a constant, color, frame, flag?            -> expression + CATransaction flush, no rebuild
Add a missing call or line?                       -> auto-continuing breakpoint with expression action
Skip or replace a line?                           -> check disassembly, then thread jump --by 1 + expression
Stub a function's return?                         -> breakpoint at entry, thread return <value>, auto-continue
                                                     (simple synchronous functions only)
Observe a C call or method without source?        -> breakpoint action first; interpose or swizzle in a lab build
Hypothesis confirmed live?                        -> now edit the code, delete the injecting breakpoints, rebuild
Hot path hit millions of times?                   -> rebuild with an if + raise(SIGSTOP)
```

### No source: where to start?

```
Which binary and slice?           -> image list -o -f, file / lipo -archs, dwarfdump --uuid
Which symbol?                     -> image lookup -rn 'pattern' Module
Objective-C method, no symbol?    -> class_getInstanceMethod + method_getImplementation, break on the IMP
Arguments?                        -> stop with -K false, read registers per ABI (references/assembly-and-abi.md)
Who calls it?                     -> bt, then disassemble the caller frame
Every method of a class?          -> rb tracer with -G1, or DTrace objc provider
```

### Where does a repeated command live?

```
Static text, maybe %1 arguments?   -> command alias (in ~/.lldbinit)
Needs regex dispatch on input?     -> command regex (chain patterns, catch-all last)
Needs logic, options, output?      -> Python command via command script import
Needs to change how a type prints? -> type summary add (string, or Python), @DebugDescription in Swift 6
```


## Core Instructions

- Prefer the live process over a rebuild. Tweak values, inject the missing line, stub the return, and confirm the hypothesis in the running app. Edit source only after the debugger proved the fix, then delete every injecting breakpoint before the next run so the fix does not execute twice, and verify once more in a clean run.
- In Swift, reach for `v` first. It reads memory with debug info and never compiles. Use `p` for expressions and `po` only when you need the object's description. Descriptions run code: they can take locks or change state.
- Know the language context. It comes from the selected frame: Swift code gives Swift, anything else gives Objective-C++. Pausing usually lands in a system frame, so it is Objective-C even in a pure Swift app. A raw address like `0x7f...` is an integer in Swift: use `expression -l objc -O -- (id)0x...` (alias `cpo`) for a live Objective-C object, or `unsafeBitCast(0x..., to: T.self)` when you know the type. Neither validates the pointer.
- Persistent debugger variables start with `$` (`e let $vc = ...`, `e id $view = (id)0x...`). Results are auto-named `$R0`, `$R1`, `$0`. They do not cross language contexts, they keep objects alive (mind that in a leak hunt), and their addresses mean nothing after a relaunch.
- Put `--` before arguments that start with `-`. Use backticks to splice a frame value into another context, and cast the spliced pointer: `expression -l objc -O -- [(id)`self.view` recursiveDescription]`.
- Capital `-C` is a breakpoint command, lowercase `-c` is a condition. `-G1` auto-continues. `--one-shot true` (or `-o 1`) makes a breakpoint one-shot; the option takes a Boolean.
- A symbolic breakpoint on a method the class does not override never resolves. Break on the implementing superclass and add a class condition, or resolve the inherited IMP through the runtime and break on its address.
- At an Objective-C method entry, `$arg1` is the receiver, `$arg2` the selector (cast with `(SEL)`), `$arg3` the first integer or pointer parameter. Stop before the prologue (`-K false`) so the registers still hold them. Floating-point arguments use their own registers, Swift native calls use their own convention, and `$arg1` is not the return value: after `finish`, read `x0` on arm64 or `rax` on x86_64.
- In UIKit, select the window of the scene that shows the bug: `UIApplication.keyWindow` is deprecated and can belong to another scene or be nil. Store it once as `$window` (see `references/view-debugging.md`).
- After mutating UI from the console, flush Core Animation: `e CATransaction.flush()` in Swift, `e (void)[CATransaction flush]` in Objective-C. The render server is a separate process and keeps running while you are paused. Make UIKit calls on the main thread; find it with `thread list`, it is not always thread 1.
- `thread jump` only moves the program counter. One source line can hold initialization, a release, or cleanup. Read the disassembly first, jump forward one line at a time, never across an `await`, and prefer `thread return` or a breakpoint action when you can.
- Hot breakpoints slow the app even when they do not stop. Use conditions and ignore counts for hundreds of hits, a dependent one-shot breakpoint for "only after X", and for millions of hits recompile with `if condition { raise(SIGSTOP) }`.
- Hardware watchpoints are few (often four on Apple silicon) and each covers a small aligned range; `watchpoint list` shows the resources. Watch the exact field size (a `Bool` is 1 byte). Always pass the ID to `watchpoint modify`, and clear a condition with `watchpoint modify -c "" <id>`.
- A crash log is only useful with the matching dSYM: compare the UUID in Binary Images with `dwarfdump --uuid`. Open the log in Xcode against the project before reaching for `atos -i`. A report has no heap: never `po` its addresses.
- Inside Python scripts, use the five-argument command signature and its `exe_ctx`, or the `frame` a breakpoint callback receives. Never use `lldb.frame`, `lldb.target`, or `lldb.process`; they are REPL conveniences and go stale mid-script. Report through `result.SetError` and `result.AppendMessage`.
- DTrace runs on macOS and on Simulator processes from the host, with `sudo`. SIP restricts some providers and protected targets. Always list probes with `-l` before adding an action so you know how many will fire, and report a permission failure instead of disabling SIP.
- When you drive LLDB yourself, use `xcrun lldb --batch`. The first failing `-o` command ends the batch, so put a read-only snapshot in a command file run with `command source -e false`. A `continue` that may never stop needs a deadline inside LLDB: a Python timer that calls `SendAsyncInterrupt()`, followed by `breakpoint delete -f` and `process detach`. Killing LLDB from outside loses the trace output. When LLDB exits, an attached process is detached and keeps running, and a process LLDB launched is killed. Never leave a process stopped when you are done.
- Interposing, swizzling, `dlopen`, patching an anti-debug check, and destructive DTrace are debugging tools for your own app or a disposable lab. Record what you changed, restore it, and relaunch clean before you trust the result. Disabling SIP, re-signing, or changing a global launch environment is a separate step: ask first.
- Report what the debugger showed, not what you assumed. A hypothesis is confirmed when the live process behaves differently after your injected change. If nothing changes, the theory is wrong or the change hit the wrong object, thread, or moment: find out which before moving on.


## Output Format

When you drove the debugger, report in this order:

1. **Observed**: the exact state you saw (values, backtrace frames, view addresses), quoted from the console.
2. **Cause**: the single sentence that explains the bug.
3. **Verified live**: what you changed in the running process and what happened.
4. **Code fix**: the diff to apply, plus "delete these breakpoints before rerunning" if any inject code.
5. **Clean run**: the result after the fix without injected behavior, and whether you detached, resumed, or left the user's session as it was.

When the user drives Xcode, give a numbered list of actions. Each step is one console command or one click, followed by what they should see. Keep Objective-C and Swift contexts explicit in each command. Example:

1. Pause the app, then in the console run `expression -l objc -O -- [[UIApplication sharedApplication] connectedScenes]` and copy the address of the foreground-active `UIWindowScene`. Then `expression -l objc -O -- [(UIWindowScene *)0x600003b0c000 windows]` and `expression -l objc -- UIWindow *$window = (UIWindow *)0x600003a08100` with the window that shows the login screen.
2. `expression -l objc -O -- [$window recursiveDescription]`. Find the `UIButton` whose frame width is wrong and copy its address.
3. `e -l objc -O -- (id)0x600003a1c2e0` to confirm it is the right button.
4. `e -l objc -- (void)[(UIView *)0x600003a1c2e0 setBackgroundColor:[UIColor redColor]]` then `e -l objc -- (void)[CATransaction flush]`. The button turns red in the Simulator while still paused.
5. Now the fix: `e -l objc -- (void)[(NSLayoutConstraint *)0x600002d11f00 setConstant:328]` and flush again. The layout matches the design, so change the constant in `LoginViewController.swift` and rebuild.

End of example.


## References

- `references/fundamentals.md` - how LLDB works, command grammar, help, print commands (`v`, `p`, `po`, `expression`), language contexts, `$` variables, formats, settings, Xcode UI to LLDB mapping.
- `references/attaching-and-running.md` - Run Without Building, attach by name/PID/wait-for, stdout trade-off, launch arguments, environment, I/O and signals, scheme diagnostics, per-project `.lldbinit`, driving LLDB in batch mode from a terminal or an agent.
- `references/breakpoints.md` - every breakpoint kind, Xcode breakpoint editor fields, conditions, actions, auto-continue, one-shot and dependent breakpoints, names, unresolved breakpoint diagnosis, stop hooks, `breakpoint write/read`.
- `references/inspecting-state.md` - frames, threads, variables, raw addresses, registers and calling conventions, `image lookup`, memory and disassembly, Objective-C runtime introspection.
- `references/flow-control.md` - stepping, `step -a0`, `thread until`, `thread return`, `thread jump`, dragging the PC, stepping one thread, `expression -i0`.
- `references/modifying-runtime-state.md` - mutate values, call methods, declare variables and functions in the debugger, inject fixes with breakpoint actions, replace a line, stub a function, flush Core Animation, prototype layout.
- `references/view-debugging.md` - scene and window selection, Xcode view debugger techniques, console equivalents, Auto Layout diagnosis, hit testing, keyboard focus, target-action, animations, appearance overrides, SwiftUI notes.
- `references/watchpoints-and-memory.md` - watchpoints, memory graph, Malloc Stack Logging, `vmmap`/`heap`/`leaks`/`malloc_history`, zombies, sanitizers, `memory history`, jetsam.
- `references/crashes-and-symbolication.md` - crash log anatomy, dSYM and UUID matching, `atos`, ASLR slide, `crashlog`, core files, source maps, exception types, catching exceptions live.
- `references/swift-debugging.md` - why `po` fails while `v` works, `swift-healthcheck`, modules and dSYMs, optimized code, type names and mangling, `@DebugDescription`, concurrency and SwiftUI specifics.
- `references/debugging-without-source.md` - binary and slice identification, runtime versus unslid versus file-offset addresses, inherited Objective-C implementations, Mach-O load commands and bindings, shared cache, disassembler workflows.
- `references/assembly-and-abi.md` - arm64 and x86_64 argument and return registers, Objective-C and Swift differences, arm64 instruction patterns, stack frames, DWARF locations, pointer authentication limits.
- `references/runtime-memory.md` - classes and methods per image, stripped Objective-C backtraces, block layout, heap instances, singleton storage, cross-references, Simulator system processes.
- `references/dynamic-loading-and-interposition.md` - `dlopen`/`dlsym` protocol, a complete C interposing lab, saved-IMP method replacement, URLSession observation, Simulator launch environments.
- `references/signing-and-attach-diagnostics.md` - which layer failed, `codesign` and profile inspection, entitlements, re-signing rules, own-app `ptrace` and `sysctl` checks.
- `references/custom-commands.md` - `.lldbinit` locations and precedence, `command alias`, `command regex`, Python commands, breakpoint callbacks, type summaries and synthetic children, third-party command packages, a starter `.lldbinit`.
- `references/advanced-python.md` - the bundled `adb-lookup`, `adb-methods`, `adb-block`, `SBValue` discipline, expression ownership, allocation stack logging, debugging the debugger script.
- `references/tracing-and-dtrace.md` - breakpoint tracers, stop hooks, unified logging, hang sampling, DTrace providers and scripts, static probes.
- `references/advanced-dtrace.md` - thread-local and recursion-aware correlation, syscall arguments, `copyin`/`copyinstr`, `stop`, `raise`, `copyout`, `system`.
- `references/remote-and-tooling.md` - `debugserver` and platform connections, `lldb-dap`, LLDB MCP, custom breakpoint resolvers, scripted processes, threads, and thread plans.
- `references/playbooks.md` - step-by-step recipes for the common cases.
- `references/anti-patterns.md` - mistakes that cost the most time, with fixes.
- `scripts/apple_debug_tools.py` - session-local `adb-lookup`, `adb-methods`, `adb-block` commands. `scripts/uitools.py` - `vmove` and `fview` for UIKit layout work while paused.

WWDC sessions behind this material: WWDC18 412 "Advanced Debugging with Xcode and LLDB", WWDC18 416 "iOS Memory Deep Dive", WWDC19 429 "LLDB: Beyond po", WWDC21 10209 "Discover breakpoint improvements", WWDC21 10211 "Symbolication: Beyond the basics", WWDC22 110370 "Debug Swift debugging with LLDB", WWDC24 10198 "Run, Break, Inspect: Explore effective debugging in LLDB".

Commands were checked against Apple LLDB `lldb-2103.0.34.407` with Swift 6.4.2 on arm64 macOS. When a spelling differs on another Xcode, the installed debugger's `help` wins.
