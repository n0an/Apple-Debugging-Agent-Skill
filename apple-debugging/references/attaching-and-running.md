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
(lldb) settings set target.env-vars DEBUG=1 OS_ACTIVITY_MODE=disable
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
| `OS_ACTIVITY_MODE=disable` | silence system log noise in the console |
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
- Attaching to Apple-signed processes (SpringBoard, Finder, system daemons) requires System Integrity Protection to be disabled on that Mac. Do that on a dedicated machine or VM, not your daily driver.
- Apps that call `ptrace(PT_DENY_ATTACH, ...)` refuse debuggers. Catch them at launch: `sudo lldb -n App -w`, `rb ptrace -s libsystem_kernel.dylib`, then `thread return 0` when it stops and `continue`.
- On a device, "Developer Mode" must be on (Settings > Privacy & Security) and the device must be paired with the Mac.

## Driving LLDB from a terminal or an agent

An interactive `lldb` session waits for keyboard input. Scripts and agents must use batch mode: every command is given up front, LLDB runs them in order, synchronously, and quits.

```
xcrun lldb --batch \
  -o "process attach --name MyApp" \
  -o "thread backtrace all" \
  -o "expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]" \
  -o "detach"
```

Rules:

- `-o` commands run after the target is set up; `-O` commands run before. `-s file.lldb` reads commands from a file, one per line. `-Q` (`--source-quietly`) hides the echo of each command.
- Commands run synchronously. `continue` returns when the process stops again (breakpoint, crash, signal), so the sequence `attach, breakpoint set, continue, bt, v, detach` works as a script. If nothing stops the process, `continue` blocks forever: wrap the whole call in `timeout 60 xcrun lldb --batch ...` or run it in the background with a deadline.
- Always end with `detach` for a process you attached to, or `kill` for one you launched. Quitting LLDB with a live process kills it.
- A process stays frozen while LLDB is attached and stopped. Do not leave it that way between steps; detach, then attach again for the next experiment.
- Capture everything with `> /tmp/lldb-out.txt 2>&1` and read the file. Errors from one command do not stop the batch; check the output for `error:` lines before trusting later results.
- Breakpoint actions can also be set in batch: `-o "breakpoint set -n '-[UILabel setText:]' -C 'po \$arg1' -C 'po (SEL)\$arg2' -G1"`. Escape `$` for the shell.
- Prefer `v` and `frame variable` in scripts; expression evaluation is slower and fails in more ways.

Example: find which label gets a wrong string without touching Xcode.

```
timeout 90 xcrun lldb --batch \
  -o "process attach --name MyApp" \
  -o "breakpoint set -n '-[UILabel setText:]' -c '(BOOL)[(id)\$arg3 containsString:@\"0 ft\"]'" \
  -o "continue" \
  -o "po \$arg1" \
  -o "bt 8" \
  -o "detach" > /tmp/label.txt 2>&1
```

The user taps the control in the Simulator during the `continue`; the output file has the receiver and the eight frames that led to the call.

## Detach, kill, restart

```
process detach            # leave the process running without a debugger
process kill              # terminate
run                       # relaunch (asks to kill the current process first)
process status            # where is it stopped and why
```
