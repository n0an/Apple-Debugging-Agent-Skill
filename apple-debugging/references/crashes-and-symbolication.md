# Crashes and symbolication

A crash report is a frozen debugging session. With the right symbols you get function names, files, and lines; without them you get addresses. Most of the work is making sure the symbols match the binary.

## Where crash reports come from

- Xcode Organizer > Crashes (App Store and TestFlight builds, symbolicated with uploaded dSYMs).
- Window > Devices and Simulators > View Device Logs for a connected device.
- On the device: Settings > Privacy & Security > Analytics & Improvements > Analytics Data.
- On the Mac: Console.app > Crash Reports, or `~/Library/Logs/DiagnosticReports`.
- Simulator crashes land in `~/Library/Logs/DiagnosticReports` too.
- MetricKit delivers crash diagnostics to the app on the next launch.

Formats: `.ips` (JSON, current) and `.crash` (text, older). Xcode opens both.

## Open a crash log in Xcode

Double-click the file (or File > Open) and choose the project when Xcode asks. Xcode uses LLDB to build a session-like view: the crashed thread is selected, the backtrace is in the Debug navigator, and the crashing line is highlighted when the project is checked out at the commit that built the binary and the matching dSYM is on disk. Walk up the backtrace to see how the crash site was reached; the frames tell you what was happening, not only where it died.

From the command line:

```
xcrun lldb
(lldb) command script import lldb.macosx.crashlog
(lldb) crashlog /path/to/report.ips          # symbolicates, loads the images at their crash-time addresses
(lldb) crashlog -i /path/to/report.ips       # interactive: a target you can run image lookup against
```

A symbolicated crash report reconstructs addresses and frames, not the full heap. Do not evaluate `po` against report addresses as though a live process were attached. If a core file is available, load it with `target create --core /path/to/core /path/to/binary`; memory inspection is limited to what the core contains, and target execution is unavailable.

## Anatomy of a report

- Header: app version, OS version, hardware, the binary's UUID.
- `Exception Type`, `Exception Codes`, `Exception Subtype`, `Termination Reason`: what killed the process (see the table below).
- `Triggered by Thread`: which thread's backtrace to read first.
- Thread backtraces: each frame is `module address symbol + offset`. Frames in your module with no symbol mean missing or mismatched dSYM.
- `Thread State`: registers at the crash instruction. Argument registers may already be reused; infer their meaning from the ABI and disassembly, not their entry-time role.
- `Binary Images`: load address, UUID, and path for every image. The UUID is the key to the right dSYM.

## Match the symbols

Do not equate a symbol table with DWARF debug information or assume every build emits a dSYM. Symbol names may support function breakpoints without source or local-variable information. Xcode's `DEBUG_INFORMATION_FORMAT=dwarf` uses DWARF without requesting a separate dSYM; `dwarf-with-dsym` also produces a bundle for supported linked products. Static-library and object-file products do not get their own dSYM through this setting. Check the actual target/configuration before diagnosing a missing bundle.

```
dwarfdump --uuid MyApp.app.dSYM                     # UUID per architecture
dwarfdump --uuid MyApp.app/MyApp
mdfind "com_apple_xcode_dsym_uuids == 1E2D3C4B-5A69-7887-96A5-B4C3D2E1F0A9"   # find a dSYM by UUID on this Mac
symbols -uuid MyApp.app/MyApp
```

The UUID in the report's Binary Images line and the dSYM's UUID must be identical. Retrieve the matching archive/CI dSYMs for that shipped build. Historical bitcode builds may need Apple-generated dSYMs where available; do not assume current App Store Connect offers a download for every build. Build settings that decide whether you have symbols at all: Debug Information Format must be "DWARF with dSYM File" for Release; Strip Linked Product, Strip Style, and Strip Swift Symbols decide what stays in the binary; Deployment Postprocessing applies stripping during archive. Keep dSYMs for every shipped build; bitcode-rebuilt binaries have different UUIDs than your local archive.

## Symbolicate one address

```
atos -o MyApp.app.dSYM/Contents/Resources/DWARF/MyApp -arch arm64 -l 0x100e00000 -i 0x100e1234c
```

`-l` is the load address of the binary from Binary Images, `-i` expands inlined frames (without it an optimized build hides functions that were inlined into their callers), `-arch` picks the slice. The ASLR slide is the difference between the load address and the `__TEXT` address in the binary (`otool -l MyApp | grep -A 8 "segname __TEXT"`); subtract it from a runtime address to get a file address you can inspect with `otool -tV` or `image lookup`.

In LLDB, without the crashlog helper:

```
target create --no-dependents --arch arm64 MyApp.app/MyApp --symfile MyApp.app.dSYM
target modules load --file MyApp __TEXT 0x100e00000
image lookup -a 0x100e1234c
image lookup -va 0x100e1234c            # adds variable locations, useful with the Thread State registers
```

Missing names in a captured trace call for symbol/UUID inspection. `get-task-allow` concerns permission to attach or collect data; it does not itself provide symbols.

## Source paths that do not match

When the binary was built elsewhere (CI, a vendor framework), LLDB shows disassembly instead of source because the debug info points at the build machine's paths. Remap:

```
settings set target.source-map /Users/ci/builds/MyApp /Users/me/MyApp
```

Put it in the scheme's LLDB Init File. Build systems can canonicalize paths at compile time with `-debug-prefix-map`, and a dSYM's `Info.plist` can carry a `DBGSourcePathRemapping` dictionary so the remap travels with the symbols.

## What the exception types mean

| Report says | Usual cause | First move |
|---|---|---|
| `EXC_BAD_ACCESS (SIGSEGV)` / `KERN_INVALID_ADDRESS` | dereferenced freed or garbage memory, unowned reference to a freed object, bad C pointer | Zombies for Objective-C, Address Sanitizer, check the address: near 0 is a null, `0x...bad...` patterns and tiny values are offsets from null |
| `EXC_BAD_ACCESS` with `KERN_PROTECTION_FAILURE` on a stack address | stack overflow from deep recursion | look for the repeating frames |
| `EXC_BREAKPOINT (SIGTRAP)` with `brk` in a Swift frame | Swift runtime trap: force unwrap of nil, out-of-range index, arithmetic overflow, `fatalError`, `precondition` | read the message in the console log (`Fatal error: ...`), frame 0 or 1 is the trapping line |
| `SIGABRT` with `abort` and `__cxa_throw` / `objc_exception_throw` below | uncaught `NSException` or C++ exception | the report's "Last Exception Backtrace" and the `Application Specific Information` reason; reproduce with an Exception breakpoint |
| `EXC_RESOURCE` | exceeded memory, CPU, or wakeup limits | memory graph, `vmmap`, check `Termination Reason` for the limit |
| `SIGKILL` with `0x8badf00d` | watchdog: launch, suspend, or resume took too long, main thread blocked | the main thread backtrace shows the blocking call |
| `SIGKILL` with `0xdead10cc` | held a file lock or database at suspension | release locks when entering the background |
| historical `0xbaaaaaad` diagnostic code | a stackshot rather than an ordinary crash | use its context and stacks if investigating a hang |
| `EXC_GUARD` | closed or used a guarded file descriptor the system owns | check `Exception Codes` for the operation |
| `SIGPIPE` | wrote to a closed socket | ignore the signal or handle the error |
| Swift runtime message about overlapping accesses | dynamic exclusivity violation; termination details vary | inspect both conflicting accesses in the runtime report |

## Catch it live

- Exception breakpoint stops at the throw. `po $arg1` is the `NSException`; `po [$arg1 reason]` and `po [$arg1 callStackSymbols]` complete the picture. Narrow to Objective-C exceptions when C++ libraries throw internally as part of normal operation.
- Swift Error breakpoint stops at the `throw`. Filter by error type in the breakpoint editor.
- Swift runtime traps stop in the debugger on their own; the Variables view and `v` still work in the trapping frame.
- For a hang, capture all thread stacks and repeated samples. Wait frames can be normal. Confirm lock ownership and a dependency cycle before calling it a deadlock.

## Demangling

Swift symbols in logs and `nm` output are mangled. `xcrun swift-demangle` reads them from stdin or arguments; `nm MyApp | xcrun swift-demangle` labels a whole symbol table. `image lookup -n` and `rb` accept the demangled spelling.
