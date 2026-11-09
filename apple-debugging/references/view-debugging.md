# View debugging

Most UI bugs are one of: the wrong view is on screen, the right view has the wrong frame, a constraint is wrong, a view does not receive touches, or an appearance (dark mode, dynamic type) was not handled. Each has a fast path.

## The Xcode view debugger

Open it with the Debug View Hierarchy button in the debug bar, or Debug > View Debugging > Capture View Hierarchy. The process pauses and Xcode snapshots every window.

Techniques that save the most time:

- Rotate into 3D to see overlapping views; drag the range slider to peel layers; filter by class name in the navigator's search field.
- Command-click to click through the front-most view and select the one behind it.
- Select a view and use Navigate > Reveal in Debug Navigator to see its ancestors and children.
- Show Clipped Content (debug bar button) reveals views whose frames extend beyond their superview. A view centered "wrong" is often centered in a superview that is wider than the window.
- Show Constraints draws the constraints that affect the selected view. Select a constraint to see its first item, second item, constant, and priority in the inspector.
- The Object inspector shows the class, the address, and the `debugDescription`. Edit > Copy with a view selected puts its pointer on the clipboard, ready for the console.
- With Malloc Stack Logging enabled in the scheme, the inspector shows the creation backtrace of a view or constraint. Click the jump arrow to open the line that created it; hold Shift-Control-Option while clicking to open it in a new window.
- Apps with several windows (popovers, alerts, scenes, macOS panels) show each window as its own root item in the navigator. If a view seems missing from the capture, collapse the first root and look for the others.
- Asset color names help identify configured variants. A color without an asset name may still be a semantic or dynamic color; verify behavior under both appearances.
- macOS: to capture an app in its active state (a popover that closes when Xcode activates), Command-click the capture button in Xcode's debug bar. Command-click sends the click without activating Xcode.

SwiftUI: the view debugger shows the hosting hierarchy and the SwiftUI view tree. For "why did this body re-run", put `let _ = Self._printChanges()` at the top of `body` (or `Self._logChanges()` on recent OS versions to route it through the unified log).

## Environment overrides

The Environment Overrides button in the debug bar switches appearance (light/dark), dynamic type size, and accessibility options (bold text, increased contrast, reduce motion, and others) for the debugged app only. Verify every appearance after a color change instead of toggling the whole system.

## Select the actual scene and window

UIKit apps can have several active scenes and windows. The deprecated application-level `keyWindow` may be nil or belong to another scene. Inspect the scenes and choose the window containing the symptom, rather than selecting the first window automatically:

```text
expression -l objc -- @import UIKit;
expression -l objc -O -- [[UIApplication sharedApplication] connectedScenes]
expression -l objc -O -- [(UIWindowScene *)0xSCENE windows]
expression -l objc -- UIWindow *$window = (UIWindow *)0xWINDOW
```

Replace the illustrative addresses with live addresses from those results or the view debugger. Verify the scene's activation state, window visibility, and root controller. `$window` examples below assume this selection. App extensions may not have access to `UIApplication.shared`; use a known view's `window` instead. AppKit uses `[NSApp windows]`, then a selected `NSWindow` and its `contentView`.

## Console equivalents

```
# iOS, Objective-C context
expression -l objc -O -- [$window recursiveDescription]
expression -l objc -O -- [[$window rootViewController] _printHierarchy]
expression -l objc -O -- [$v recursiveDescription]
expression -l objc -O -- [(id)`self.view` recursiveDescription]      # from a Swift frame, splice the Swift value in

# macOS
expression -l objc -O -- [[[NSApp keyWindow] contentView] _subtreeDescription]
```

`recursiveDescription` prints every subview with class, address, frame, and a few flags (hidden, alpha, userInteractionEnabled, layer). `_printHierarchy` prints the view controller tree with presentation and appearance state. Both are private debugging helpers; call them from an Objective-C expression.

Highlight a view to prove you have the right one:

```
expression -l objc -- [$v.layer setBorderWidth:2]; [$v.layer setBorderColor:[UIColor redColor].CGColor]; (void)[CATransaction flush]
expression -l objc -- [$v setHidden:![$v isHidden]]; (void)[CATransaction flush]
```

On macOS, call `[view setWantsLayer:YES]` first, then set the border on `view.layer`, and `[view display]` to redraw.

## Auto Layout

Diagnose from the console:

```
expression -l objc -O -- [$v _autolayoutTrace]                 # the hierarchy with AMBIGUOUS LAYOUT markers
expression -l objc -O -- [$v hasAmbiguousLayout]
expression -l objc -- [$v exerciseAmbiguityInLayout]            # cycles through valid solutions so you see the ambiguity
expression -l objc -O -- [$v constraintsAffectingLayoutForAxis:0]   # 0 horizontal, 1 vertical
expression -l swift -- $v.constraintsAffectingLayout(for: .horizontal)
expression -l objc -O -- [$v constraints]
```

Unsatisfiable constraints: the console log names the constraints by address. Set a Constraint Error breakpoint, or `breakpoint set -n UIViewAlertForUnsatisfiableConstraints`, then `po (id)0x...` each constraint from the log and `po [(id)0x... firstItem]` to find the views. Fix it live with `setConstant:`, `setActive:`, or `setPriority:` plus a flush to confirm the layout before editing code.

Layout loops: launch with `-UIViewLayoutFeedbackLoopDebuggingThreshold 100` to get a diagnostic when a view keeps invalidating itself.

Common findings: a swapped first and second item (the constant has the wrong sign), a constraint added before the view was in the hierarchy (crash), `translatesAutoresizingMaskIntoConstraints` left on for a programmatic view (ambiguous or conflicting), a hidden stack view arranged subview that still takes space because of a spacing constraint.

## Touches that do not arrive

Work through the delivery chain:

1. Which view gets the touch? Symbolic breakpoint with an action, auto-continue:
   `breakpoint set -n "-[UIApplication sendEvent:]" -C "po [[[$arg3 allTouches] anyObject] view]" -G1`
   Tap. The console names the hit view for the touch began and ended phases. If it names the wrong view, something in front is catching the touch.
2. Hit testing: `breakpoint set -n "-[UIView hitTest:withEvent:]" -c '(BOOL)[NSStringFromClass((id)[$arg1 class]) containsString:@"Toolbar"]'` to stop when your view is asked, then inspect the receiver and step out. For a pointer return, inspect `x0` on arm64 or `rax` on x86_64 immediately after return, casting to the correct type. `$arg1` is not a portable return-value alias.
3. Properties that silently block touches: `isUserInteractionEnabled == false` on the view or any ancestor, `isHidden`, `alpha <= 0.01`, `isEnabled == false` on a `UIControl`, a frame outside the superview bounds (visible because clipping is off, but untouchable).
4. Gesture recognizers on ancestors with `cancelsTouchesInView` or `delaysTouchesBegan`, and scroll views that delay content touches.
5. The responder chain: walk it from the console.
   `expression -l objc -O -- ({ id r = $v; NSMutableString *s = [NSMutableString new]; while (r) { [s appendFormat:@"%@\n", r]; r = [r nextResponder]; } s; })`

## Unexpected keyboard focus changes

Search before assuming `UITextField` implements the method on this OS:

```text
image lookup -rn 'becomeFirstResponder' UIKitCore
breakpoint set -S becomeFirstResponder -K false -C 'expression -l objc -O -- (id)$arg1' -C 'bt 8' -G1
breakpoint list
```

The selector breakpoint traces implementations across classes; narrow it to a discovered symbol or receiver if noisy. `-K false` stops before the prologue so the Objective-C receiver register is still meaningful. Reproduce the focus change and follow the caller back to application code. Trace `resignFirstResponder` separately if focus disappears.

A call is a request, not proof of success. If needed, disable auto-continue, step out of the relevant method, and inspect its Boolean result using the return ABI. Check the view's window, `canBecomeFirstResponder`, and whether the current responder can resign.

## Which code handles a control

```
expression -l objc -O -- [$button allTargets]
expression -l objc -O -- [$button actionsForTarget:(id)0x600001e2a3c0 forControlEvent:UIControlEventTouchUpInside]
expression -l swift -O -- $button.allTargets
expression -l swift -O -- $button.actions(forTarget: target, forControlEvent: .touchUpInside)
expression -l objc -O -- [$v gestureRecognizers]
```

Then set a symbolic breakpoint on the action selector and tap.

## Images, colors, data

Quick Look in the Variables view (the eye icon) renders images, colors, paths, data, strings, and URLs. From the console, write an image to disk and open it:

```
expression -l swift -- try! $image.pngData()!.write(to: URL(fileURLWithPath: "/tmp/snap.png"))
platform shell open /tmp/snap.png
```

For a device, copy the bytes out with `memory read -o /tmp/snap.png -b -c <length> <bytes-address>`, where length and address come from `[$data length]` and `[$data bytes]`.

Snapshot a view: `expression -l objc -O -- [[$v snapshotViewAfterScreenUpdates:NO] description]` is not an image; use `UIGraphicsImageRenderer` in a Swift expression to render `$v.layer` into an image, then write it out as above.

## Animations

- Simulator: Debug > Slow Animations (Command-T) slows every animation in the Simulator.
- Any target: `expression -l objc -- [[$window layer] setSpeed:0.1]` slows the window's layer tree; set it back to 1.
- To see the state mid-animation, pause and inspect `$v.layer.presentationLayer`, which has the on-screen values while `$v.layer` has the model values.
- `UIView.areAnimationsEnabled` and `UIView.setAnimationsEnabled(false)` switch animations off for a session when they get in the way.

## Dark mode and traits

Read the trait collection of a view (`po $v.traitCollection`), the effective appearance on macOS (`po [$view effectiveAppearance]`), and compare with the override you set in the debug bar. A view that looks right in one appearance and wrong in another usually has a hard-coded color somewhere in its creation backtrace.
