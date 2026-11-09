# Swift debugging

Swift adds a second failure mode to the debugger: the variables view can be fine while every `po` fails, or the other way around. Understanding which half of LLDB is unhappy tells you what to fix.

## Two halves of LLDB

- The debugger half powers `frame variable` (`v`) and Xcode's variables view. It needs debug info (DWARF from the build or the dSYM) and Swift reflection metadata. It reads memory and never compiles.
- The compiler half powers `expression` and expression-evaluation paths of `p` and `po`. It needs Swift modules: the SDK's textual interfaces, your app's and frameworks' binary `.swiftmodule` files, Clang modules for Objective-C imports, bridging headers. Module problems break the compiler half only.

If `v` works and expressions fail, investigate the evaluator, language, imports, and description code. If both fail, also check frame/scope, optimization, lifetime, and debug information. Neither observation identifies a single cause.

## First response when an expression fails

1. Use `v` for what you need right now.
2. Run `swift-healthcheck` (Xcode 14+). It writes a log of the expression evaluator's configuration and names the module import that failed.
3. Fix the import. Typical causes:
   - A framework's binary `.swiftmodule` missing from the build products or the dSYM; for static libraries the module must be registered with the linker (`-add-ast-path`) so `dsymutil` collects it. Check the build log, or `dsymutil -s MyApp | grep swiftmodule`.
   - Serialized search paths from another machine inside a prebuilt `.swiftmodule`; build vendor modules with `SWIFT_SERIALIZE_DEBUGGING_OPTIONS = NO`, or supply paths in LLDB with `settings set target.swift-module-search-paths` and `target.swift-framework-search-paths`.
   - A module compiled with a different Swift compiler than LLDB's. Rebuild with the current Xcode.
   - A stale module cache. Capture the healthcheck first, then try an isolated build or remove only the affected project cache when the evidence points there; do not erase all DerivedData as the first response.
   - Optimization. `-O` builds inline, reorder, and drop variables; debug the `Debug` configuration, or set `SWIFT_OPTIMIZATION_LEVEL = -Onone` for the target under investigation.

Common messages and what they usually mean: "Couldn't lookup symbols" (the expression references something the module context does not know; import the module or use `v`), "Cannot load Swift type information" / "missing module" (module import failure; healthcheck), `<could not resolve type>` (debug info does not describe the type; often optimization or a stripped framework), "error: use of unresolved identifier 'UIView'" (import the framework in the expression: `e import UIKit`).

## Static versus dynamic types

Declared as a protocol or a superclass, stored as a concrete type: `p activity.name` can fail on the expression path because the compiler only sees the static type `Activity`. Either cast (`p (activity as! Trip).name`) or use `v activity.name`, which resolves the dynamic type at every step of the path.

This distinction applies when `p` uses the expression evaluator. Modern `p` can use the same variable-path lookup as `v`. Neither command can recover data that optimization removed.

## Optimized code

Frames tagged `[opt]` came from optimized compilation. Expect: variables shown as unavailable, breakpoints landing on neighboring lines, inlined functions appearing or disappearing from backtraces, stepping that seems to jump. Options: debug a Debug build; add `@_optimize(none)` to one function temporarily; `settings set target.inline-breakpoint-strategy always` when file-and-line breakpoints in headers or `#include`d sources do not resolve; use `atos -i` and `image lookup -va` to understand inlined frames in a crash.

## Names

- Types are module-qualified in the debugger: `MyApp.CheckoutViewController`, `Swift.Optional<Swift.String>`. Use the qualified name in `type summary add` and in `image lookup -t`.
- Mangled symbols start with `$s`. `xcrun swift-demangle` decodes them. Breakpoints accept demangled forms, partial names, and regexes: `rb 'Checkout.*total\.setter'`.
- A property has `.getter`, `.setter`, and `.modify` accessors with their own symbols. Break on the setter to catch writes that go through it.
- A Swift method exposed to Objective-C can resolve to a thunk and a native body. Inspect `breakpoint list` and the current frame; disable only the unwanted location rather than assuming the hit order.

## Make your types print well

- `po`: conform to `CustomDebugStringConvertible` and implement `debugDescription`. `CustomReflectable` customizes `Mirror` and `dump`; LLDB variable formatters do not generally execute `customMirror` to populate their children.
- `p` and the variables view: the `@DebugDescription` macro (Swift 6, Xcode 16) turns a `debugDescription` built from string interpolation of stored properties into an LLDB type summary. It works without running code, so it also works for values inside collections and in situations where `po` cannot evaluate. Keep the body to literals and stored property paths; computed properties and function calls disqualify the macro.
- Session-only, no code change: `type summary add MyApp.Trip --summary-string "${var.name} (${var.destinations})"`, or a Python summary function (see `custom-commands.md`). Summaries persist until `type summary delete` (remove only the summaries created for the experiment), and survive relaunches within one Xcode session.

## Concurrency

- An `async` function is split into partial functions around each `await`. The backtrace reconstructs the logical chain, so you still see the awaiting caller above the current frame.
- After an `await`, execution may resume on a different thread. Stepping over an `await` can leave you on another thread or lose the thread; prefer a breakpoint on the line after the `await`.
- `bt all` lists threads, not tasks. To understand which task is where, log task-local values or use `Task` names where available.
- Data races can appear as intermittent corruption, wrong values, or crashes; Thread Sanitizer (Simulator and macOS) can identify conflicting accesses in instrumented runs.
- Main Thread Checker detects selected UI API misuse, not arbitrary actor violations. Use Swift concurrency diagnostics and runtime isolation checks for actor issues; Thread Sanitizer does not prove actor correctness or detect every race.

## SwiftUI

- Breakpoints in `body` fire on every evaluation; a line with closures resolves to several locations (the call, each closure). Disable the ones you do not want.
- `let _ = Self._printChanges()` at the top of `body` prints which state change triggered the re-evaluation. `Self._logChanges()` (iOS 17.1, macOS 14.1 and later) sends the same to the unified log.
- `po self` inside a view prints the struct with its property wrappers; `v self` is faster and usually enough.
- View identity bugs: inspect the `id` you pass to `ForEach` and whether the model's `Hashable`/`Identifiable` conformance is stable across updates.

## Combine and reactive code

Insert `.print("label")` into a pipeline to log every event, `.breakpoint(receiveOutput: { $0.isEmpty })` to pause on a condition, or `.breakpointOnError()` to pause when an error flows through.

## Expression performance

The first Swift expression in a session imports modules and can take seconds; later ones are faster. Large projects with many modules can feel slow in `po`; `v` usually avoids that import cost. Conditions are evaluated at hits that reach the condition check; compilation can be cached. Debugger round trips and target execution still make hot conditional breakpoints expensive.
