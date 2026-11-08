# Tracing

Tracing answers "what runs, in which order, how often" without stopping at every hit. Three levels: breakpoint tracers inside LLDB, the unified log, and DTrace across the whole process.

## Breakpoint tracers

A breakpoint with a command and auto-continue is a log statement you did not have to compile in:

```
breakpoint set -n "-[UIViewController viewDidAppear:]" -C "po NSStringFromClass([$arg1 class])" -G1
breakpoint set -n "-[UILabel setText:]" -C "po $arg1" -C "po $arg3" -G1
rb 'Checkout' -s MyApp -C "bt 3" -G1          # every symbol containing Checkout in your module, with callers
rb . -f PaymentCoordinator.swift -o 1          # which function in this file runs first? one-shot
```

Keep the location count small: each resolved location is a memory write when the breakpoint is set, and each hit costs a round trip to the debugger even when it auto-continues. Scope with `-s <module>` or `-f <file>`, tighten the regex, and prefer the Simulator for anything broad.

Log instead of printing: in the Xcode breakpoint editor, a Log Message action with `@expression@` placeholders and "Automatically continue" does the same with no console typing.

Stop hooks run on every stop regardless of the reason: `target stop-hook add -o "bt 3"`, `target stop-hook add -c CheckoutViewController -o "po self.cart"`.

## The unified log

`os_log` and `Logger` output does not depend on the debugger and is the right channel for anything the app should report on its own. Read it live:

```
log stream --process MyApp --level debug
log stream --predicate 'subsystem == "com.example.myapp" AND category == "network"'
log show --last 10m --predicate 'process == "MyApp"' --info --debug
```

Console.app shows the same stream with filters. When you attach instead of launching from Xcode, `print` output is lost but the unified log is not, which is one reason to prefer `Logger` over `print` in code you will debug later.

`thread info` in LLDB shows the current `os_activity` and its trace messages when the code uses activity tracing, which ties a crash or a stop on a background queue back to the user action that started it.

Signposts (`OSSignposter`) and the Instruments "Points of Interest" track are the way to trace timing across threads; Instruments is the GUI for whole-process profiling and is outside this file.

## DTrace

DTrace observes a running process (or the whole system) from the kernel with almost no overhead and without a debugger attached. On Apple platforms it runs on macOS and inside the Simulator only, needs `sudo`, and needs System Integrity Protection disabled on that Mac. Treat it as a tool for a dedicated research machine or a VM.

A DTrace program is a list of clauses:

```
provider:module:function:name
/ predicate /
{ action }
```

One-liners with `-n`, scripts with `-s file.d`, and `-p <pid>` or `-c <command>` to target a process (`$target` inside the program). Always list first with `-l` to see how many probes a description matches before you add an action:

```
sudo dtrace -ln 'objc$target:MyApp*::entry' -p $(pgrep -x MyApp) | wc -l
sudo dtrace -n 'objc$target:CheckoutViewController::entry { printf("%s %s", probemod, probefunc); }' -p $(pgrep -x MyApp)
sudo dtrace -n 'objc$target:::entry { @[probemod] = count(); }' -p $(pgrep -x MyApp)      # calls per class, printed on Ctrl-C
sudo dtrace -n 'pid$target:MyApp::entry { @[probefunc] = count(); }' -p $(pgrep -x MyApp) # C and Swift functions in the main binary
sudo dtrace -n 'syscall::open*:entry /pid == $target/ { printf("%s", copyinstr(arg0)); }' -p $(pgrep -x MyApp)
```

The `objc` provider spells a method as `objc$target:Class:-method?:entry`, where the module field is the class, the function field is the method with `-` or `+` and `?` standing in for each colon of the selector, and the name is `entry` or `return`. Predicates filter (`/ arg0 == 0x600003a1c2e0 /` traces one receiver); aggregations (`@[key] = count()`, `sum()`, `quantize()`) summarize instead of streaming; `ustack()` prints the user stack at the probe; `self->ts = timestamp` in an entry clause and `timestamp - self->ts` in the matching return clause measures duration per call.

Static probes in your own code: declare a provider in a `.d` file (`provider myapp { probe sync_state(int); };`), add it to the target as a DTrace source so Xcode generates the header, call the generated `MYAPP_SYNC_STATE(value)` macro from C or Objective-C (wrap it in a small inline function to call it from Swift), and guard expensive argument preparation with `MYAPP_SYNC_STATE_ENABLED()`. The probes cost nothing when nobody is listening and give you a stable tracing interface in production builds.

Reach for DTrace when you want a histogram of calls across a process, timing per method without a profiler, or to see system calls and I/O for one app; reach for breakpoints when you want to stop and look at state.
