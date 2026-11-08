# Playbooks

Step-by-step recipes for the situations that come up most. Each assumes the app is running under a debugger (see `attaching-and-running.md`).

## 1. Fix a layout constant without rebuilding

1. Capture the view hierarchy (debug bar button) and select the misplaced view.
2. Show Constraints; select the suspicious constraint; note its constant and items.
3. Edit > Copy with the constraint selected gives its pointer. In the console: `expression -l objc -O -- (id)0x600002d11f00` to confirm.
4. `expression -l objc -- [(NSLayoutConstraint *)0x600002d11f00 setConstant:-30]; (void)[CATransaction flush]`. The Simulator updates while paused.
5. Repeat until it looks right (Enter re-runs the last command after you edit the value). Copy the final constant into code or the storyboard.

## 2. Test a one-line fix live

1. Set a breakpoint on the line after which the missing code belongs.
2. Edit Breakpoint > Add Action > Debugger Command: `expression animator.delegate = self` (Swift frame) and check "Automatically continue".
3. Trigger the flow. The injected line runs every time; verify the behavior.
4. Apply the change in source, delete the breakpoint, rebuild.

## 3. Feed test data into a screen

1. Break where the data is assembled (for example where results are appended to an array).
2. Action: `expression results.append(Result(title: "Test", score: 42))`, auto-continue.
3. For several variants, keep a `$` variable: `expression -l swift -- var $fixtures = [...]` once, then the action reads from it. Change `$fixtures` between runs to drive different states without rebuilding.

## 4. Find the code that changes a label or property

1. Symbolic breakpoint on the setter: `-[UILabel setText:]` (Objective-C) or `rb Cart.total.setter` (Swift).
2. It fires too often? Add a condition on the value (`(BOOL)[(id)$arg3 containsString:@"0 ft"]`) or on the receiver, or make it dependent: a breakpoint on the function that runs right before the interesting update with the action `breakpoint set --one-shot true --name "-[UILabel setText:]"` and auto-continue.
3. When it stops: `po $arg1` to confirm the receiver, then `bt` or click the next frame up to land in your code.
4. No setter is ever called? Use a watchpoint (playbook 7).

## 5. Find who presented or dismissed a view controller

1. Symbolic breakpoint on `-[UIViewController dismissViewControllerAnimated:completion:]` or `presentViewController:animated:completion:`.
2. On stop: `po $arg1` (the controller the message was sent to), `bt`. The frames above UIKit name your code or the UIKit gesture (dimming view tap, swipe) that triggered it.
3. If it fires twice for one user action, compare `po $arg1` between hits.

## 6. A tap does nothing

1. `breakpoint set -n "-[UIApplication sendEvent:]" -C "po [[[$arg3 allTouches] anyObject] view]" -G1`, then tap. Which view receives the touch?
2. If it is an ancestor or a sibling, check that view in the view debugger: something transparent in front, or the target outside its superview's bounds (Show Clipped Content).
3. On the intended view: `isUserInteractionEnabled`, `isHidden`, `alpha`, `isEnabled` for controls, and the same on every ancestor. `po [$v _ivarDescription]` shows them all at once.
4. Gesture recognizers on ancestors: `po [$v gestureRecognizers]` up the chain; look for `cancelsTouchesInView`.
5. Fix it live (`[$v setUserInteractionEnabled:YES]`) and tap again before touching code.

## 7. Catch a value overwritten with no setter

1. Get the object's address (memory graph, view debugger, or `p self`).
2. Offset of the field: `language objc class-table dump MyClass -v` for Objective-C classes; for Swift, pause with the object in scope and use the Variables view: expand the object, right-click the property, Watch.
3. `watchpoint set expression -s <size> -w write -- <address + offset>`.
4. Continue, reproduce. The stop shows the writer; `bt` for the caller.

## 8. Stub a function or skip a line

- Stub: breakpoint at the function's first line, action `thread return <value>`, auto-continue.
- Skip one line: breakpoint on the line, action `thread jump --by 1`, auto-continue. Add a second action with an `expression` to replace it.
- Never jump backward or over a line that initializes something the rest of the function uses.

## 9. Reproduce a crash from a report

1. Confirm the UUID in the report matches your dSYM (`dwarfdump --uuid`).
2. Open the `.ips` or `.crash` file in Xcode with the project selected; read the crashed thread top down and the exception type.
3. For a Swift trap read the `Fatal error` message in the report's Application Specific Information; for an `NSException` read the reason and the Last Exception Backtrace.
4. Set the matching breakpoint (Swift Error, Exception, or a line breakpoint on the trapping line) and reproduce under the debugger.

## 10. Memory grows until the app is killed

1. Reproduce with Malloc Stack Logging (Live Allocations) enabled in the scheme.
2. Watch the memory gauge; when it climbs, open the memory graph. Filter for leaks, then for your own classes; count instances.
3. Export the memgraph. `vmmap --summary` to see which region type is dirty; `heap --sortBySize` for the biggest objects; `malloc_history --fullStacks <address>` for who allocated them.
4. Images: check pixel dimensions, not file size; downsample on load and drop decoded images that are off screen.

## 11. po fails in Swift

1. `v <path>` for the value you need now.
2. `swift-healthcheck`; read which module failed to import.
3. Fix the module (rebuild with the current toolchain, register static library modules with the linker, remove serialized search paths, clear the module cache).
4. Source shows as disassembly: `settings set target.source-map <build path> <local path>` in the scheme's LLDB Init File.

## 12. Debug Apple's code without source

1. `image lookup -rn 'keyword' UIKitCore` to find the method names; copy the exact spelling.
2. Symbolic breakpoint with `-s UIKitCore` to limit the scope.
3. At the stop: `po $arg1`, `po (SEL)$arg2`, `po $arg3`; `bt` to see which of your calls led there; `finish` and read `$x0` (arm64) in an Objective-C expression for the return value.
4. Move the breakpoint up the chain until you reach the decision your code controls.

## 13. Attach instead of rebuilding

1. The app is already installed and running? Debug > Attach to Process (or `xcrun lldb -n MyApp`).
2. Not running yet? Attach to Process by PID or Name with the name, then launch the app; or `xcrun simctl launch --wait-for-debugger booted <bundle id>` and attach to the printed pid.
3. Expect no `print` output in the console after attaching; use `log stream` in a terminal if you need logs.

## 14. A breakpoint in a hot loop

1. Condition: `index == 1203`. Ignore count: `-i 1200`. One-shot after a prerequisite: breakpoint on the prerequisite with the action `breakpoint set --one-shot true -f File.swift -l 44`.
2. Still too slow (millions of hits)? Add `if condition { raise(SIGSTOP) }` to the code and rebuild once; the debugger stops exactly there with no per-hit cost.

## 15. Prototype a layout change

1. Get the views: `pviews` alias (recursive description), copy the addresses.
2. `expression -l objc -- id $a = (id)0x...; id $b = (id)0x...`.
3. Nudge with `[$a setCenter:CGPointMake(200, 120)]; (void)[CATransaction flush]`, or a `nudge` Python command (see `custom-commands.md`); Enter repeats.
4. Read back `po [$a frame]` and transfer the numbers to constraints.

## 16. Drive the debugger from a terminal for someone else

```
timeout 120 xcrun lldb --batch \
  -o "process attach --name MyApp" \
  -o "breakpoint set -n '-[UIViewController viewDidAppear:]' -C 'po NSStringFromClass([\$arg1 class])' -G1" \
  -o "continue" \
  -o "detach" > /tmp/trace.txt 2>&1
```

The person reproduces in the Simulator while `continue` runs; the file holds the sequence of controllers that appeared. End every batch with `detach`.
