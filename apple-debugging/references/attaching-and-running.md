# Attaching and running

Getting a debugger on the process is the first step of every loop. The fastest option is rarely a rebuild.

## Ways to get LLDB on your app

| Way | How | stdout in console? | Rebuild? |
|---|---|---|---|
| Run | Cmd+R in Xcode | yes | yes (incremental) |
| Run Without Building | Product > Perform Action > Run Without Building (Ctrl+Cmd+R), or Control-click the Run button | yes | no, reinstalls and relaunches the last build |
| Relaunch from the console | `run` / `r` in the LLDB console (macOS targets) | yes | no |
| Attach to a running process | Debug > Attach to Process > pick the app, or Attach to Process by PID or Name | **no** | no |
| Wait for launch | Debug > Attach to Process by PID or Name, enter the name before launching; or `xcrun lldb -n AppName --waitfor` | no | no |
| Terminal | `xcrun lldb -p <pid>`, `xcrun lldb -n <name>`, `xcrun lldb /path/to/binary -- args` | yes for launched, no for attached | no |

The stdout trade-off: when you attach, the process already has its stdout wired somewhere else, so `print` and `NSLog` do not show up in the console. `os_log` / `Logger` output is unaffected: read it with `log stream --process AppName --level debug` in a terminal or in Console.app. If you need `print` output and a debugger, use Run or Run Without Building.

Simulator processes are macOS processes, so every macOS attach method works on them. Physical devices need Xcode (Debug > Attach to Process) or the Xcode device workflow; command-line attach to a device is not something to rely on.

## Launching under control

```
# from a terminal
xcrun lldb /path/to/MyApp.app/Contents/MacOS/MyApp
(lldb) process launch --stop-at-entry -- --flag value   # stop before main
(lldb) settings set target.run-args --flag value         # or persist the args
(lldb) settings set target.env-vars DEBUG=1
(lldb) process launch -E MallocStackLogging=1            # one-off environment
(lldb) run

# simulator: launch suspended, then attach
xcrun simctl launch --wait-for-debugger booted com.example.MyApp     # prints the pid
xcrun lldb -p <pid> -o "breakpoint set -n viewDidLoad" -o continue
```

`--wait-for-debugger` keeps the app stopped until a debugger attaches, so you can set breakpoints that must fire during launch.

Find a Simulator process: `pgrep -x MyApp`, or `pgrep -f "MyApp.app/MyApp"` when several apps share a name.

## Xcode scheme settings that matter for debugging

Edit Scheme (Cmd+<), Run action:

**Options tab**
- LLDB Init File: a per-project init file, sourced after `~/.lldbinit`. Put `settings set target.source-map`, project-specific aliases, and `command script import` lines here (Xcode 14+).
- Console: disable "Debug executable" only if you want the app to launch without the debugger.

**Arguments tab** (Arguments Passed On Launch, Environment Variables)

| Argument or variable | Effect |
|---|---|
| `-com.apple.CoreData.SQLDebug 1` | log Core Data SQL |
| `-com.apple.CoreData.ConcurrencyDebug 1` | assert on Core Data context misuse |
| `-NSDoubleLocalizedStrings YES` | stretch strings to test layout |
| `-NSShowNonLocalizedStrings YES` | uppercase unlocalized strings |
| `-AppleLanguages (de)` / `-AppleLocale de_DE` | run in another language |
| `-UIViewLayoutFeedbackLoopDebuggingThreshold 100` | catch layout feedback loops |
| `OS_ACTIVITY_MODE=disable` | suppresses useful diagnostics too; remove it while investigating logs |
| `CFNETWORK_DIAGNOSTICS=3` | verbose URL loading logs |
| `DYLD_PRINT_LIBRARIES=1` | log every loaded image |

**Diagnostics tab**
- Runtime Sanitization: Address Sanitizer (bad memory access, use after free), Thread Sanitizer (data races), Undefined Behavior Sanitizer.
- Runtime API Checking: Main Thread Checker (UI from background threads), Thread Performance Checker (priority inversions, blocking on the main thread).
- Memory Management: Malloc Scribble, Malloc Guard Edges, Guard Malloc, Zombie Objects (messages to deallocated Objective-C objects become reported instead of random crashes).
- Logging: Malloc Stack Logging with "Live Allocations Only" or "All Allocations and Free History". Required for creation backtraces in the view debugger and memory graph and for `malloc_history`.

Most of these also have a matching Runtime Issue breakpoint type so you can stop when the checker reports (see `breakpoints.md`).

## Xcode behaviors

Xcode > Settings > Behaviors > Running > Pauses: show a tab named "Debug", show the debug navigator, show the console. The debug layout stays out of your editing tabs and comes back on every stop.

## Prerequisites and permissions

- Your own debug builds carry the `get-task-allow` entitlement, which is what lets a debugger (and Instruments) attach. App Store and ad hoc builds do not. Check with `codesign -d --entitlements - MyApp.app`.
- Attach failures come from different layers: debugger authorization, process ownership, hardened runtime, signing entitlements, or SIP protection of Apple-signed processes. Record the exact error and diagnose it with `signing-and-attach-diagnostics.md` before changing anything. `sudo` is not a universal fix.
- Apps that call `ptrace(PT_DENY_ATTACH, ...)` refuse debuggers. For your own app, stop before the call and test the check: see `signing-and-attach-diagnostics.md`. Changing SIP or re-signing someone else's binary is a separate, persistent experiment: ask first.
- On a device, "Developer Mode" must be on (Settings > Privacy & Security) and the device must be paired with the Mac.

## Driving LLDB from a terminal or an agent

An interactive `lldb` session waits for keyboard input. Scripts and agents use batch mode: every command is given up front, LLDB runs them in order, synchronously, and quits.

```sh
xcrun lldb --batch \
  -o 'process attach --name MyApp' \
  -o 'thread backtrace all' \
  -o 'process detach'
```

Rules (checked on Apple LLDB `lldb-2103` with an attached macOS process):

- `-o` commands run after the target is set up; `-O` commands run before. `-s file.lldb` reads commands from a file, one per line. `-Q` hides the echo of each command. Add `--no-lldbinit` for an isolated run that ignores the user's init files.
- **The first failing `-o` command ends the batch.** Everything after it, including your `process detach`, is skipped. For a read-only snapshot where a missing variable must not stop the rest, put the commands in a file and source it with errors allowed: `-o 'command source -e false /tmp/snapshot.lldb'`. Do not use that for commands that depend on each other.
- Commands run synchronously. `continue` returns when the process stops again (breakpoint, crash, signal), so `attach, breakpoint set, continue, bt, v, detach` works as a script. If nothing stops the process (the breakpoint never hits, or every action auto-continues), `continue` blocks forever.
- **Give a waiting batch a deadline inside LLDB.** Before `continue`, start a timer that interrupts the process: `-o "script import threading; threading.Timer(90, lambda p=lldb.debugger.GetSelectedTarget().GetProcess(): p.SendAsyncInterrupt()).start()"`. When it fires, `continue` returns with `stop reason = signal SIGSTOP` and the remaining commands run, so put `breakpoint delete -f` and `process detach` after it. A timer that has not fired yet does not delay LLDB's exit. Sending SIGINT to a batch LLDB does not interrupt `continue`.
- **Add an outer deadline only as a safety net** for a debugger that hangs: `perl -e 'alarm shift; exec @ARGV' 180 xcrun lldb --batch ...` (stock macOS has no `timeout`; `gtimeout` exists only with coreutils). A killed LLDB loses its buffered output, including everything breakpoint actions printed, so never use the outer kill as the normal way to end a trace.
- **What happens when LLDB exits.** A process you attached to is detached and keeps running, whether the batch finished, stopped on an error, or was killed. A process LLDB launched with `run` is killed. Still end with an explicit `process detach` (or `process kill`) so the output says what happened, then check the process with `ps -o stat= -p <pid>`: `T` means it is still stopped.
- Only one debugger can own a process. If Xcode is debugging it, the attach fails: work through the user's Xcode console instead.
- `--name` picks one process; with several matches (two booted simulators) attach by a PID you verified with `pgrep -fl MyApp`.
- Capture everything with `> /tmp/lldb-out.txt 2>&1` and read the file. Search it for `error:` before trusting later results, and check the exit status: the outer kill exits with 142.
- Breakpoint actions work in batch: `-o "breakpoint set -n '-[UILabel setText:]' -C 'po \$arg1' -C 'po (SEL)\$arg2' -G1"`. Escape `$` for the shell, or keep complex commands in a file so neither `$` nor backticks get expanded.
- Prefer `v` and `frame variable` in scripts; expression evaluation is slower and fails in more ways.

Example: find which label gets a wrong string without touching Xcode.

```sh
xcrun lldb --batch \
  -o "process attach --name MyApp" \
  -o "breakpoint set -n '-[UILabel setText:]' -K false -c '(BOOL)[(id)\$arg3 containsString:@\"0 ft\"]'" \
  -o "script import threading; threading.Timer(90, lambda p=lldb.debugger.GetSelectedTarget().GetProcess(): p.SendAsyncInterrupt()).start()" \
  -o "continue" \
  -o "po \$arg1" \
  -o "bt 8" \
  -o "process detach" > /tmp/label.txt 2>&1
```

The user taps the control in the Simulator during the `continue`; the output file has the receiver and the eight frames that led to the call. If the 90 seconds pass first, the file shows `signal SIGSTOP` instead of `breakpoint 1.1`: the `po` and `bt` describe wherever the app was, not the label, and the process is detached and keeps running.

When the agent's tools keep a terminal open (a PTY session it can type into and interrupt), an interactive session works too: interrupt with Ctrl-C at the deadline, remove your breakpoints, `process detach`, and verify the process is running.

## Detach, kill, restart

```
process detach            # leave the process running without a debugger
process kill              # terminate
run                       # relaunch (asks to kill the current process first)
process status            # where is it stopped and why
```

## Launch I/O and signals

`process launch -w /path/to/work -i /path/to/input -o /tmp/probe.out -e /tmp/probe.err -- arguments` sets this launch's working directory and standard streams. `-n` launches without terminal I/O; `-X true` requests shell argument expansion where supported. Inspect local help and use only the option combination needed by the target.

`process handle SIGUSR1` shows the debugger's stop/pass/notify policy. To observe and then deliver an app-handled signal, record that policy before changing it, for example with `process handle -s true -p true -n true SIGUSR1`. A debugger stop and the app's receipt of the signal are separate events. Restore the original policy afterward. SIGSTOP and SIGKILL cannot be caught by an application signal handler.

For attach denials, app anti-debug checks, and signing/entitlement evidence, read [Signing and attach diagnostics](signing-and-attach-diagnostics.md).
