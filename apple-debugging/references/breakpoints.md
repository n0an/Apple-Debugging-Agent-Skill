# Breakpoints

A breakpoint is not just "stop here". It is a rule: where to pause, under which condition, how many hits to skip, what to run when it fires, and whether to resume on its own. Most debugging time is saved by using the last three.

## Kinds of breakpoints

| Kind | Xcode | LLDB | Use when |
|---|---|---|---|
| Line | click the gutter | `b File.swift:42`, `breakpoint set -f File.swift -l 42` | you know the file and line |
| Column | Command-click an expression > Set Column Breakpoint (Xcode 13+) | `breakpoint set -f File.swift -l 42 -u 18` (`-u` column) | several calls or closures on one line |
| Symbolic | Breakpoint navigator `+` > Symbolic Breakpoint | `breakpoint set -n "-[UILabel setText:]"`, `b -[UILabel setText:]` | no source, Apple code, many subclasses implementing one method |
| Regex | - | `rb <regex>` (`breakpoint set -r`) | Swift mangled names, families of methods |
| Selector | - | `breakpoint set -S viewDidAppear:` | every implementation of an Objective-C selector |
| Method | - | `breakpoint set -M foo` | every C++ method named foo |
| Source pattern | - | `breakpoint set -p "if let" -f A.swift -f B.swift` | you know the code shape but not the location |
| Address | - | `breakpoint set -a 0x100e1234c` | from a crash log or disassembly |
| Exception | `+` > Exception Breakpoint | `breakpoint set -E objc`, `breakpoint set -E c++` | Objective-C `@throw` / C++ `throw`; stop at the throw, not the abort |
| Swift Error | `+` > Swift Error Breakpoint | `breakpoint set -E swift`, optionally `-O MyErrorType` | any Swift `throw`, or only a given error type |
| Runtime Issue | `+` > Runtime Issue Breakpoint | - | Main Thread Checker, Thread Performance Checker, sanitizer reports; enable the checker in the scheme Diagnostics tab |
| Constraint Error | `+` > Constraint Error Breakpoint | `breakpoint set -n UIViewAlertForUnsatisfiableConstraints` | unsatisfiable Auto Layout |
| Test Failure | `+` > Test Failure Breakpoint | - | pause on a failing `XCTAssert` |
| Watchpoint | right-click a variable > Watch | `watchpoint set variable x` | a value changes, see `watchpoints-and-memory.md` |

A logical breakpoint can resolve to several locations (`1.1`, `1.2`, `1.3`). A line with a `Button("...") { action } label: { ... }` call produces one location for the call, one for each closure. `breakpoint list` shows them with line and column; disable the ones you do not want with `breakpoint disable 1.2`.

## Breakpoint flags you will use

| Flag | Meaning |
|---|---|
| `-n <name>` | function or method name (`-[Class sel:]`, `Module.Type.method`, `viewDidLoad`) |
| `-r <regex>` | regex on symbol names (`rb` is the alias) |
| `-s <module>` | restrict to a shared library or the main binary (`-s MyApp`, `-s UIKitCore`) |
| `-f <file>` | restrict to a source file, repeatable |
| `-L <lang>` | restrict by language (`swift`, `objc`) |
| `-c '<expr>'` | **condition**, lowercase; evaluated on every hit |
| `-C '<cmd>'` | **command** to run on hit, uppercase; repeatable |
| `-G1` / `-G0` | auto-continue after the commands, or not |
| `-i <n>` | ignore the first n hits |
| `-o 1` | one-shot: delete after the first hit |
| `-N <name>` | give the breakpoint a name to group it |
| `-q <queue>` / `-T <thread name>` / `-t <tid>` | only stop on that queue or thread (`-q com.apple.main-thread`) |
| `-d` | create disabled |

```
# log every label change with receiver, selector, and value, never stop
breakpoint set -n "-[UILabel setText:]" -C "po $arg1" -C "po (SEL)$arg2" -C "po $arg3" -G1

# stop only in your own module, only the main queue
breakpoint set -n viewDidAppear -s MyApp -q com.apple.main-thread

# every ObjC instance method of UIViewController, including categories
rb '\-\[UIViewController(\ |\()'

# every function in one file, self-deleting, to learn what runs first
rb . -f CheckoutViewController.swift -o 1
```

## The Xcode breakpoint editor

Double-click a breakpoint (or right-click > Edit Breakpoint). Fields:

- **Condition**: any expression valid at that location that yields a Bool. `index == 3`, `self.isSelected`, `(BOOL)[(id)$arg3 containsString:@"error"]`. Slow expressions slow the app on every hit.
- **Ignore**: skip the first N hits. Cheaper than a condition for "the 12th element".
- **Action** (add several): Debugger Command (`expression ...`, `thread return`, `breakpoint set ...`), Log Message (`@expr@` evaluates an expression, `%B` the breakpoint name, `%H` the hit count; can be spoken aloud), Shell Command (host command, expression results can be passed as arguments; a way to toggle an external tool such as a proxy throttle at the exact moment), Sound, AppleScript, Capture GPU Workload.
- **Automatically continue after evaluating actions**: the checkbox that turns a breakpoint into a probe. Same as a trailing `continue` command or `-G1`.
- **Options**: Share (saves into `xcshareddata` for the team). Right-click > Move Breakpoint To: project, workspace, or user level. A user-level Exception breakpoint follows you into every project.

Edits made with `breakpoint command add` on the console replace the actions set in Xcode for that breakpoint.

## Conditions, ignore counts, dependent breakpoints

Three ways to tame a breakpoint that fires too often:

```
breakpoint modify -c 'video.duration > 60' 2
breakpoint modify -i 10 2                      # ignore ten hits
breakpoint modify -c '' 2                      # clear the condition
```

Dependent breakpoints: make breakpoint A set breakpoint B and continue, so B only exists after A runs. For a single investigation, make both one-shot so repeated hits on A do not create duplicate breakpoints. In Xcode this is a Debugger Command action on A: `breakpoint set --one-shot true --name "-[UILabel setText:]"` with auto-continue. On the console:

```
breakpoint set -n jumpCompleted --one-shot true -C "breakpoint set --one-shot true -n '-[UILabel setText:]'" -G1
```

`--one-shot` / `-o` requires a Boolean value, such as `true` or `1`. If A must remain active, reuse and enable an existing disabled B instead of creating a new B on every hit. Arming B establishes ordering, not causality: unrelated asynchronous work can hit it first. Filter by the relevant receiver or request identifier when possible.

`tbreak File.swift:44` creates a one-shot breakpoint directly.

For a line hit millions of times, even an always-false condition is too slow. Recompile with the check in code and let the debugger take over:

```swift
if item.id == suspectID { raise(SIGSTOP) }   // pauses under Xcode or lldb as if a breakpoint fired
```

## Symbolic breakpoints that do not resolve

Xcode 13+ draws an unresolved breakpoint with a dashed icon; hover for the reason. Common causes and fixes:

- Typo or wrong signature. Search first: `image lookup -rn convert MyApp` lists every symbol containing "convert" in your binary. Copy the exact name.
- The library is not loaded yet. The breakpoint resolves later when the framework loads.
- The class does not override the method. `-[MyViewController viewDidAppear:]` has no symbol if only `UIViewController` implements it. Break on the implementation and filter: `breakpoint set -n "-[UIViewController viewDidAppear:]" -c '(BOOL)[(id)$arg1 isKindOfClass:[MyViewController class]]'` (use `$arg1` because there is no `self` in a frame without debug info).
- Swift names: `MyApp.CheckoutViewController.viewDidLoad()`, or just `CheckoutViewController.viewDidLoad`; LLDB matches partial names. Properties: `MyApp.Cart.total.setter`. When in doubt use `rb Cart.total.setter`.
- A Swift method callable from Objective-C can resolve to a thunk and a native body. Inspect the actual locations and frame before disabling one; do not assume location `.1` is always the thunk.
- Spaces matter in Objective-C signatures: `-[UIView hitTest:withEvent:]`, no space after the minus or inside the brackets.

## Finding the symbol before you break

```
image lookup -n "-[UIView hitTest:withEvent:]"      # exact
image lookup -rn 'hitTest' UIKitCore                # regex, one module
image lookup -rn 'becomeFirstResponder'            # use the symbol's actual spelling
image lookup -rn 'Checkout.*total' MyApp            # Swift, your module
```

Read the `Summary:` line and use that spelling in `breakpoint set -n`, or shorten it into an `rb` regex.

## Exception and error breakpoints in practice

- Exception breakpoint: stops at `objc_exception_throw` (or `__cxa_throw`). `po $arg1` prints the `NSException`; `po [$arg1 reason]`, `po [$arg1 userInfo]`, `po [$arg1 callStackSymbols]`. Some frameworks throw and catch internally during normal operation (Core Data, some image decoders); set the editor's Exception field to Objective-C only, or add a condition on the reason.
- Swift Error breakpoint: stops at a throw, including errors that will be handled by `catch` or `try?`. It can stop in a runtime helper such as `swift_willThrow`; use `bt` and select the actual throwing frame rather than assuming a fixed frame index. Filter by type in the editor (Type field) or `breakpoint set -E swift -O NetworkError`.
- Runtime Issue breakpoint: pick the checker type in the editor. Without it Xcode only records the issue in the Issue navigator after the fact.

## Breakpoint names

```
breakpoint set -n foo -N Noisy
breakpoint set -n bar -N Noisy
breakpoint modify -c 'self == nil' -C bt -G1 Noisy       # apply options to the group
breakpoint name configure -c 'self == nil' -C bt -G1 SelfNil   # a reusable, configured name
breakpoint set -n baz -N SelfNil                          # new breakpoints inherit the configuration
```

Names in `~/.lldbinit` give you reusable behaviors across sessions.

## Save and share a setup

```
breakpoint write -f /tmp/checkout-bps.json
breakpoint read -f /tmp/checkout-bps.json
```

A hard-to-reproduce bug's breakpoint configuration becomes a file a teammate can load.

## Stop hooks

Run something every time the process stops, optionally scoped:

```
target stop-hook add --one-liner "frame variable self"
target stop-hook add -n viewDidLoad --one-liner "po self.view"
target stop-hook add -c MyViewController -o "bt 3"
target stop-hook list
target stop-hook delete 1
```

## Managing

```
breakpoint list                 # all, with locations
breakpoint list -b              # brief
breakpoint list -v              # verbose: full paths Xcode used (helps when a path mismatch keeps a breakpoint unresolved)
breakpoint disable 1.2
breakpoint enable 1
breakpoint delete 1
breakpoint delete                # all
breakpoint command add 1         # interactive, end with DONE
breakpoint command add -o "po self" 1
breakpoint command list 1
breakpoint command delete 1
```

Delete every breakpoint that injects code before the next build and run. The fix now lives in source, and the injected line would run twice.
