# Flow control

Once the process is stopped, these commands decide what runs next. Use them to land exactly on the interesting instruction, to skip code you do not want to run, and to make a function return something else.

## Basic stepping

```
c                 # process continue
n                 # thread step-over: run the current line, treat calls as black boxes
s                 # thread step-in: enter the call on this line
finish            # thread step-out: run until the current frame returns
si / ni           # one machine instruction, into or over
thread until 120  # run until line 120 in this frame, or until the frame exits
```

Two things people assume are broken:

- `s` steps over, not into, when the callee has no debug info (any UIKit, Foundation, or stripped third-party call). Force it with `s -a0`. The default comes from the setting `target.process.thread.step-in-avoid-nodebug`.
- A line with several calls steps into the first evaluated one, which is often not the one you care about. Either set a column breakpoint on the call you want (Command-click the expression in Xcode) or use `thread step-in -t <functionName>` to step into a named callee.

Skip whole libraries while stepping: `settings set target.process.thread.step-avoid-regexp '^std::|^Swift\.'`, or `settings set target.process.thread.step-avoid-libraries libswiftCore.dylib libobjc.A.dylib`.

Only the current thread: hold Control-Shift while clicking Xcode's step buttons, or add `-m this-thread` to a `thread step-*` command. Every other thread stays frozen, which is the way to step through a race without the other side moving.

Stepping commands stack. If you step over a line and a breakpoint inside the called function fires, inspect what you want and then `continue`: LLDB finishes the original step-over and stops at the end of your starting line. `thread plan list` shows the stack of pending steps, `thread plan discard` drops one.

Xcode's "Continue to here" (hover a line while paused and click the arrow in the gutter) is `thread until` with a one-shot breakpoint.

## Returning early

`thread return` pops the current frame immediately, optionally with a return value:

```
thread return            # void function
thread return false      # Bool
thread return 0          # Int, pointer, nil
thread return $R0        # an object you captured earlier
```

The rest of the function body does not run. Pair it with a breakpoint at the function's first line plus auto-continue and you have stubbed the function for the whole session without touching the source (see `modifying-runtime-state.md`). Cleanup code in the function is skipped too, so for Objective-C under ARC or anything that balances a lock or a counter, return at the top of the function before anything was acquired.

## Skipping lines

`thread jump` moves the program counter and nothing else:

```
thread jump --by 1        # skip the current line
thread jump --line 58     # jump to a line in the same function
thread jump --address 0x1045c2e10
```

In Xcode, drag the green instruction-pointer marker in the gutter to another line. Xcode warns you because the debugger does not know whether the state is still valid.

What makes a jump unsafe:

- Skipping the initialization of a variable that later code reads.
- Skipping a retain, a release, a lock, or a `defer` that the compiler placed in the skipped instructions.
- Jumping backward: the function's locals are not reset, cleanups already ran.
- Jumping over the last statement of a function: the function epilogue may not be where the line table suggests.

Jump forward, one line at a time, and only over a statement you fully understand. When the goal is "replace this line", the robust pattern is a breakpoint on the line with two actions: `thread jump --by 1` and then the replacement `expression`, with auto-continue. When the goal is "do not run this function at all", use `thread return` instead of jumping to the end.

## Running code with breakpoints honored

Expression evaluation ignores breakpoints by default, so calling a method from the console runs it silently. Turn breakpoints back on for one evaluation:

```
expression -i 0 -- self.reloadData()
expression -i 0 -l swift -- $vc.viewDidLoad()
```

Now a breakpoint inside the called method fires and you can step through it as if the app had called it. Call it again with different arguments to exercise each branch. When the called code crashes, `expression -u 0 -- ...` keeps the stack at the crash site instead of unwinding back to the console.

## Pausing on demand

- Xcode pause button, or `process interrupt` in a terminal session.
- `raise(SIGSTOP)` in source stops the process under the debugger as if a breakpoint had fired; useful inside a hot loop guarded by an `if`.
- A watchpoint pauses when memory changes (see `watchpoints-and-memory.md`).
- A one-shot breakpoint created by another breakpoint's action pauses only after a prerequisite ran (see `breakpoints.md`).

## Restarting without rebuilding

- `run` (`r`) in a terminal session relaunches the same binary. LLDB asks to kill the current process first.
- In Xcode use Run Without Building (Control-click the Run button, or Product > Perform Action) when the sources did not change.
- Remember that persistent `$` variables survive across stops in one run but not across relaunches, and watchpoints on addresses become meaningless after a relaunch.
