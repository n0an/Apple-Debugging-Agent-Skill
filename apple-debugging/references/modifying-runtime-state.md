# Modifying runtime state

The debugger can change the program while it runs: values, objects, UI, control flow, even which code a function executes. Use this to confirm a hypothesis in seconds instead of rebuilding to find out.

## Change a value

```
expression didReachSelectedHeight = false          # Swift frame
expression self.cart.discount = 0.2
expression -l objc -- [(NSLayoutConstraint *)0x600002d11f00 setConstant:328]
expression -l objc -- [$v setHidden:YES]
expression -l swift -- $v.alpha = 0.3
```

In Swift, mutating a struct property through a path works (`e self.model.count += 1`). Properties with `didSet` observers run the observer. Objective-C properties go through their setters, so KVO and `didSet`-style side effects fire. KVC reaches things the type system hides: `expression -l objc -- [$v setValue:@"Done" forKey:@"title"]`.

If an Objective-C expression fails with "no known method" or an unknown return type, tell the compiler what it needs:

```
expression -l objc -- @import UIKit;          # once per session for UIKit types
expression -l objc -- (void)[$v setNeedsLayout]   # cast when the return type is unknown
```

In Swift, if a type is unresolved, import its module: `expression import UIKit` or `expression import MyFeatureModule`.

## Make UI changes visible while paused

The render server is a separate process; it keeps compositing while your app is paused, but your app only hands it new content when a Core Animation transaction commits, which normally happens at the end of a run loop turn. Commit by hand:

```
expression -l swift -- CATransaction.flush()
expression -l objc -- (void)[CATransaction flush]
```

On macOS AppKit views, `[view display]` or `[view displayIfNeeded]` forces a redraw of that view; flushing Core Animation covers layer-backed changes.

Chain the change and the flush in one command with `;` so Enter repeats both:

```
expression -l objc -- [$label setText:@"Hello"]; (void)[CATransaction flush]
```

Alias the flush (`command alias flush expression -l objc -- (void)[CATransaction flush]`) and keep it in `~/.lldbinit`.

## Keep handles to objects

Select `$window` using [View debugging](view-debugging.md) before the UIKit example.

```
expression -l objc -- id $vc = [[$window rootViewController] presentedViewController]
expression -l swift -- let $vc = unsafeBitCast(0x600001234560, to: DetailViewController.self)
expression -l swift -- let $savedSelf = self   # explicit persistent handle
```

Persistent object variables and results can retain objects, altering a lifetime investigation. They belong to the current process and language context; `$R0` from `viewDidLoad` still drives the controller when you pause minutes later (switch to the same language context to use it).

## Call code

```
expression self.reloadData()
expression -l objc -- (void)[$tableView reloadData]
expression -l objc -O -- [[UIApplication sharedApplication] openURL:[NSURL URLWithString:@"myapp://cart"] options:@{} completionHandler:nil]
expression -l swift -- $nav.pushViewController(UIViewController(), animated: true)
```

Then flush to see the result, or `continue`. Calling into UIKit from a thread that is not the main thread while paused on a background thread can wedge things; use `thread list` to identify the main thread, then select its actual index. Do not assume it is thread 1 or synchronously dispatch to a main queue frozen by the debugger.

## Define things in the debugger

Variables, functions, and types declared with a `$` prefix persist for the session:

```
expression -l swift -- func $fakeTotal(_ items: Int) -> Double { Double(items) * 9.99 }
expression -l swift -- var $results: [String] = []
expression -l swift -- struct $Stub { var name: String }
expression -l objc -- NSMutableArray *$log = [NSMutableArray new]
```

In the Xcode console each `expression` is one line; a multi-line type must be entered as several one-line expressions. For bigger helpers, write a Python command or a `.lldbinit`-sourced script (see `custom-commands.md`). Pasting a long multi-line block into one expression has been known to hang the console.

## Inject a fix with a breakpoint action

The core move for testing a hypothesis without rebuilding. In Xcode: set a breakpoint on the line where the missing code belongs, Edit Breakpoint, add a Debugger Command action with the `expression`, check "Automatically continue after evaluating actions". On the console:

```
breakpoint set -f JumpViewController.swift -l 88 -C "expression animator.delegate = self" -G1
```

Every time execution reaches that line, the expression runs as if it were in the code. The same works for logging (`-C "po items.last?.title"`), for forcing a branch (`-C "expression didReachSelectedHeight = false"`), and for feeding test data:

```
breakpoint set -n reloadSites -C "expression sites.append(Site(url: URL(string: \"https://example.com\")!))" -G1
```

Rules:

- Expressions in actions run in the language context of that line.
- One action is one line. Use several actions, or `;` for Objective-C statements.
- When you finally change the code, delete these breakpoints. Otherwise the fix runs twice on the next build.

## Replace a line

Breakpoint on the line, two actions, auto-continue:

1. `thread jump --by 1`
2. `expression jumpAstronaut(animated: false)`

If line mappings and machine state permit this jump, the replacement executes instead. Inspect disassembly first; a one-line jump is not intrinsically safe and can skip ownership or initialization instructions. This is how you swap a call for a variant, remove an animation, or patch a wrong argument during a session.

## Stub a function

Breakpoint at the function's first line, action `thread return <value>`, auto-continue. The function returns your value immediately for the rest of the session. Limit this to simple synchronous functions whose return ABI and cleanup you understand. It is not a general stub for async functions, coroutines, throwing functions, or complex Swift value returns.

## Prototype layout live

With a view handle, move and resize while paused and flush after each change:

```
expression -l swift -- $v.center = CGPoint(x: 200, y: 120); CATransaction.flush()
expression -l swift -- $v.frame.size.width += 10; CATransaction.flush()
expression -l objc -- [(NSLayoutConstraint *)0x600002d11f00 setConstant:16]; (void)[CATransaction flush]
```

Press Enter to repeat the last nudge. When it looks right, read the final values back (`p $v.frame`, `po constraint`) and move them into the code or storyboard.

## Patch memory and registers

For the rare case where there is no symbol to call:

```
register write x0 0x0             # change an argument or a return value at the right moment
memory write --size 1 0x600003a1c2f8 0x01  # write exactly one byte
register write pc 0x1045c2e10     # redirect execution (same risks as thread jump)
```

## Keep the session honest

- Every injected change is temporary. Note what you injected so the fix you commit matches what you verified.
- Changing state in the debugger does not change what the code would have done on its own. Verify a fix by removing the injected breakpoint, applying the source change, rebuilding, and reproducing once more.
