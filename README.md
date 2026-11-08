<h1 align="center">Apple Debugging Agent Skill</h1>

<p align="center">
    <img src="https://img.shields.io/badge/platforms-iOS%20%7C%20macOS%20%7C%20watchOS%20%7C%20tvOS%20%7C%20visionOS-2980b9.svg" alt="Apple platforms" />
    <img src="https://img.shields.io/badge/LLDB-Xcode%2015%2B-F05138.svg" alt="LLDB in Xcode 15+" />
    <img src="https://img.shields.io/badge/version-1.0.0-blueviolet.svg" alt="Version 1.0.0" />
    <img src="https://img.shields.io/badge/license-MIT-lightgrey.svg" alt="MIT License" />
    <a href="https://agentskills.io/home">
        <img src="https://img.shields.io/badge/Agent%20Skills-Compatible-purple.svg" alt="Agent Skills Compatible" />
    </a>
</p>

An agent skill that teaches AI coding agents like Claude Code, Codex, Cursor, and Gemini to debug Apple platform apps the way an experienced iOS engineer does: with LLDB and Xcode, in the running process, without rebuilding to test every guess.

It uses the [Agent Skills](https://agentskills.io/home) format, so it works with Claude Code, Codex, Gemini, Cursor, and more.


## What It Covers

- **Fundamentals** - how LLDB is wired (debugger plus embedded compiler), command grammar, `--` and backticks, `help`/`apropos`, the five command families, `v` vs `p` vs `po` vs `expression`, language contexts (Swift vs Objective-C, the pause-button trap), `$` variables and `$R0` results, format shorthands, settings, and a map from Xcode's UI to LLDB commands
- **Attaching and running** - Run Without Building, attach by name, PID, or wait-for, the lost-stdout trade-off, launch arguments and environment variables that unlock diagnostics, scheme Diagnostics (sanitizers, Main Thread Checker, Zombies, Malloc Stack Logging), per-project LLDB init files, and driving LLDB in batch mode from a terminal or an agent with `detach` discipline
- **Breakpoints** - line, column, symbolic, regex, selector, source-pattern, address, Exception, Swift Error, Runtime Issue, Constraint Error, and Test Failure breakpoints; the Xcode breakpoint editor (conditions, ignore counts, log messages, shell commands, auto-continue); dependent one-shot breakpoints; breakpoint names; `raise(SIGSTOP)` for hot loops; diagnosing unresolved symbolic breakpoints; stop hooks; `breakpoint write`/`read`
- **Inspecting state** - frames, threads, `bt all`, objects by raw address in both languages, registers and `$arg1`/`$arg2` in assembly frames with the arm64 and x86_64 conventions, `image lookup`, Objective-C runtime introspection (`_ivarDescription`, `_methodDescription`, `class-table dump`), memory reads and dumps, disassembly, globals reachable from a cold pause
- **Flow control** - stepping into code without debug info, stepping one thread, the stepping plan stack, `thread until`, `thread return` to stub a function, `thread jump` and dragging the instruction pointer with the rules that keep them safe, `expression -i0` to honor breakpoints inside called code
- **Modifying runtime state** - mutate values and properties, call methods, flush Core Animation to see changes while paused, declare `$` variables, functions, and types, inject a fix with an auto-continuing breakpoint action, replace a line, stub a return, prototype layout live, and verify before touching source
- **View debugging** - the Xcode view debugger (click-through, clipped content, constraints, creation backtraces, multiple windows, macOS active-state capture), Environment Overrides, console equivalents (`recursiveDescription`, `_printHierarchy`, `_autolayoutTrace`), the touch-delivery checklist (`sendEvent:` tracer, hit testing, responder chain, target-action), images and colors via Quick Look or disk, animation slow-down, SwiftUI `_printChanges`
- **Watchpoints and memory** - watchpoints on variables and on computed ivar addresses with hardware limits, the dirty-plus-compressed footprint model, the memory graph, `vmmap`, `heap`, `leaks --traceTree`, `malloc_history`, `memory history`, Zombies and sanitizers, turning Malloc Stack Logging on mid-session
- **Crashes and symbolication** - where reports live, opening `.ips`/`.crash` in Xcode against the project, `crashlog` in LLDB, UUID matching with `dwarfdump` and `mdfind`, `atos -i`, ASLR slide, source maps and `-debug-prefix-map`, a table of exception types and termination codes, catching exceptions and Swift errors live, deadlocks from `bt all`
- **Swift debugging** - why `v` works when `po` fails, `swift-healthcheck`, module and dSYM pitfalls (static libraries, serialized search paths, stale module cache), static vs dynamic types, optimized code, module-qualified names and mangling, `@DebugDescription` and `CustomDebugStringConvertible`, concurrency and SwiftUI specifics, Combine debugging operators
- **Custom commands** - `.lldbinit` locations and the per-scheme init file, `command alias` with help and `%1`, `command regex` with dispatch patterns, Python commands with argument parsing and `__lldb_init_module`, breakpoint callbacks, type summaries, filters, synthetic children, a starter `~/.lldbinit`
- **Tracing** - breakpoint tracers, stop hooks, the unified log (`log stream`, `log show`), `thread info` with activities, DTrace clause anatomy, the `objc`, `pid`, and `syscall` providers, aggregations, static probes
- **Playbooks** - 16 step-by-step recipes: fix a constant live, test a one-line fix, feed test data, find who changes a label, who dismissed a controller, a tap that does nothing, a value with no setter, stub or skip, reproduce from a crash report, memory growth, `po` failures, Apple code without source, attach instead of rebuild, hot loops, prototype layout, drive LLDB from a terminal
- **Anti-patterns** - the mistakes that burn the most time, grouped by workflow, printing, breakpoints, flow control, UI, memory, crashes, and scripts


## Installing

You can install this skill into Claude Code, Codex, Gemini, Cursor, and more by using `npx`:

```bash
npx skills add https://github.com/n0an/Apple-Debugging-Agent-Skill --skill apple-debugging
```

If you get the error `npx: command not found`, you do not have Node installed. Install it through Homebrew (use Node.js 22.23.4+, 24.22.1+, or 26.12.1+; older releases ship a certificate bundle that is no longer trusted):

```bash
brew install node
```

And if *that* fails it usually means you need to [install Homebrew](https://brew.sh) first.

When using `npx`, you can select exactly which agents you want to use during the installation. You can also select whether the skill should be installed just for one project, or whether it should be made available for all your projects.

### Alternative install methods

**Claude Code:**

```bash
/plugin install n0an/Apple-Debugging-Agent-Skill
```

**Gemini:**

```bash
gemini extensions install https://github.com/n0an/Apple-Debugging-Agent-Skill.git --consent
```

Alternatively, you can clone this whole repository and install it however you want.


## Using Apple Debugging

The skill is called Apple Debugging, and can be triggered in various ways. For example, in Claude Code you would use this:

> /apple-debugging

And in Codex you would use this:

> $apple-debugging

In both cases you can provide specific instructions. For example, `/apple-debugging the Pay button ignores taps on the checkout screen` on Claude, or `$apple-debugging here is a crash report, find the cause` in Codex.

You can also trigger the skill using natural language:

> Use the Apple Debugging skill to find out why the price label shows 0 after refresh.

The skill works in two modes. When the agent has a terminal and the app runs in the Simulator or on the Mac, it attaches with `xcrun lldb` in batch mode and runs the commands itself. When you are driving Xcode, it gives you exact console commands one step at a time and tells you what to expect.


## Why Use an Agent Skill for Debugging?

Agents default to the slowest loop there is: add a `print`, rebuild, reproduce, read, repeat. They also tend to:

- Use `po` for everything in Swift and give up when the expression evaluator fails, even though `frame variable` would have answered instantly
- Paste a raw address into a Swift expression and conclude the object is gone
- Create a symbolic breakpoint on a method the class never overrides, and wait forever
- Drag the instruction pointer or `thread jump` across initialization and corrupt the process
- Change a view from the console and conclude it did not work because nothing flushed Core Animation
- Symbolicate a crash with a dSYM from a different build
- Set a regex breakpoint across all of UIKit on a device and stall the session

This skill:

- **Prefers the live process** over a rebuild: mutate, inject, stub, verify, then edit source once
- **Picks the right print command** (`v`, `p`, `po`, `expression -l`) and the right language context every time
- **Covers the whole toolbox**: breakpoints with actions, watchpoints, the view debugger, the memory graph, crash symbolication, Python commands, DTrace
- **Gives recipes**, not only commands, for the situations that actually come up
- **Knows how an agent should drive LLDB** non-interactively, with timeouts and a guaranteed `detach`

WWDC sessions behind the material: WWDC18 412 "Advanced Debugging with Xcode and LLDB", WWDC18 416 "iOS Memory Deep Dive", WWDC19 429 "LLDB: Beyond po", WWDC21 10209 "Discover breakpoint improvements", WWDC21 10211 "Symbolication: Beyond the basics", WWDC22 110370 "Debug Swift debugging with LLDB", WWDC24 10198 "Run, Break, Inspect: Explore effective debugging in LLDB".


## Contributing

Contributions are welcome - whether adding new recipes, fixing a command that changed in a newer Xcode, or correcting typos.

- Keep Markdown concise. There is a token cost to using skills, so respect the token budgets of users.
- Do not repeat things LLMs already know. Focus on edge cases, surprises, and common mistakes.
- Every command should be one you have run in a current Xcode.
- All work must be licensed under the MIT license.


## License

Available under the [MIT License](LICENSE), which permits commercial use, modification, distribution, and private use.
