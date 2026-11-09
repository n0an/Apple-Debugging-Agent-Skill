# Tracing

Tracing answers "what runs, in which order, how often" without stopping at every hit. Three levels: breakpoint tracers inside LLDB, the unified log, and DTrace across the whole process.

## Breakpoint tracers

A breakpoint with a command and auto-continue is a log statement you did not have to compile in:

```
breakpoint set -n "-[UIViewController viewDidAppear:]" -C "po (Class)[(id)$arg1 class]" -G1
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

Console.app shows the same stream with filters. When you attach instead of launching from Xcode, existing stdout/stderr generally remain connected to their original destinations rather than moving into Xcode, which is one reason to prefer `Logger` over `print` in code you will debug later.

`thread info` in LLDB shows the current `os_activity` and its trace messages when the code uses activity tracing, which ties a crash or a stop on a background queue back to the user action that started it.

Signposts (`OSSignposter`) and the Instruments "Points of Interest" track are the way to trace timing across threads; Instruments is the GUI for whole-process profiling and is outside this file.

## Hangs: sample before injecting code

For an accessible macOS or Simulator PID, `sample <pid> 5 -file /tmp/app-sample.txt` collects stacks over time. Compare repeated samples; a single thread waiting on a lock or semaphore is not proof of a deadlock. Establish the owner and dependency cycle, or look for sustained CPU work and repeated stacks. Device investigations use Xcode/Instruments and device diagnostics.

Avoid `po`, UI traversal, or synchronous dispatch when paused inside allocator/runtime locks. Use stacks, registers, and raw variables first. Resume and compare with a run without the debugger when timing changes the symptom.

## DTrace

DTrace observes a running macOS process (Simulator apps included, from the host) from the kernel, without a debugger attached. It needs `sudo`. SIP restricts some providers and protected targets, so a probe can be missing or denied on a stock Mac: list the probes first, and when one is unavailable switch to LLDB, Instruments, or unified logging instead of disabling SIP. Broad probes and expensive actions add real overhead.

A DTrace program is a list of clauses:

```
provider:module:function:name
/ predicate /
{ action }
```

One-liners with `-n`, scripts with `-s file.d`, and `-p <pid>` or `-c <command>` to target a process (`$target` inside the program). Replace 12345 below with one verified target PID; an unfiltered name lookup can return several processes. Always list first with `-l` to see how many probes a description matches before you add an action:

```
sudo dtrace -l -n 'objc$target:MyApp*::entry' -p 12345 | wc -l
sudo dtrace -n 'objc$target:CheckoutViewController::entry { printf("%s %s", probemod, probefunc); }' -p 12345
sudo dtrace -n 'objc$target:::entry { @[probemod] = count(); }' -p 12345      # calls per class, printed on Ctrl-C
sudo dtrace -n 'pid$target:MyApp::entry { @[probefunc] = count(); }' -p 12345 # C and Swift functions in the main binary
sudo dtrace -n 'syscall::open:entry /pid == $target/ { printf("%s", copyinstr(arg0)); }' -p 12345
```

The `objc` provider spells a method as `objc$target:Class:-method?:entry`, where the module field is the class, the function field is the method with `-` or `+` and `?` standing in for each colon of the selector, and the name is `entry` or `return`. Predicates filter (`/ arg0 == 0x600003a1c2e0 /` traces one receiver); aggregations (`@[key] = count()`, `sum()`, `quantize()`) summarize instead of streaming; `ustack()` prints the user stack at the probe; `self->ts = timestamp` in an entry clause and `timestamp - self->ts` in the matching return clause measures a non-recursive synchronous call. Use a depth-indexed timestamp for recursion and clear it on return.

Static probes in your own code: declare a provider in a `.d` file (`provider myapp { probe sync_state(int); };`), add it to the target as a DTrace source so Xcode generates the header, call the generated `MYAPP_SYNC_STATE(value)` macro from C or Objective-C (wrap it in a small inline function to call it from Swift), and guard expensive argument preparation with `MYAPP_SYNC_STATE_ENABLED()`. Disabled probes have low overhead; guard expensive argument preparation and give you a stable tracing interface in production builds.

Reach for DTrace when you want a histogram of calls across a process, timing per method without a profiler, or to see system calls and I/O for one app; reach for breakpoints when you want to stop and look at state.

For recursion-aware timing, `openat` argument differences, `copyin`/`copyout`, `stop`, `raise`, and `system`, read [Advanced DTrace](advanced-dtrace.md).
