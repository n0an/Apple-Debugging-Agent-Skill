# Watchpoints and memory

Breakpoints answer "when does this code run". Watchpoints answer "when does this memory change". Memory tools answer "what is alive, who owns it, and who allocated it".

## Watchpoints

A watchpoint pauses the process when a memory range is written (or read). Hardware resources, alignment, and supported sizes vary by architecture and debugserver. `watchpoint list` reports supported resources. Watch the smallest stable field and check creation errors; wider or unaligned ranges can consume multiple resources. Recreate address watchpoints after relaunch or reallocation.

Set one on a variable that is in scope:

```
watchpoint set variable attempts
watchpoint set variable self.cart.total
```

In Xcode: pause where the object is in scope, expand it in the Variables view, right-click the property, Watch. Delete the scaffolding breakpoint afterward; it was only there to get the object into scope.

Set one on an address when nothing is in scope:

```
language objc class-table dump UnixSignalHandler -v        # ivar offsets and sizes
p/x 0x600002ce8940 + 32                                      # instance address plus ivar offset
watchpoint set expression -s 1 -w write -- $0                # watch one byte for writes
```

Get the instance address from the memory graph, the view debugger, or a `po`. `-w` takes `write`, `read`, or `read_write`. Match `-s` to the actual field size and target ABI; a pointer is eight bytes only on a target with 64-bit pointers.

Why reach for a watchpoint: Swift `inout` writes, direct ivar writes in Objective-C, C structs, and compiler-generated accessors all bypass the setter symbol a breakpoint would need. If a value changes and the setter breakpoint never fires, this is the tool.

Manage them like breakpoints:

```
watchpoint list -b
watchpoint modify -c '*(BOOL *)0x600002ce8960 == 0' 2    # stop only when the new value is false
watchpoint modify -c "" 2                                 # clear this condition explicitly
watchpoint command add 2                                  # bt 5 / continue / DONE turns it into a tracer
watchpoint delete 2
```

## The memory footprint model

The system charges an app for its dirty memory (anything written to: objects, decoded image buffers, framework `__DATA` pages) plus compressed memory. Clean memory (read-only mapped files, framework `__TEXT`) is free to evict. Limits vary by device and process class. Memory pressure can cause jetsam termination, often without a conventional crash backtrace. `EXC_RESOURCE` is a separate possible diagnostic, not a guaranteed stop before a memory kill. Inspect the jetsam report and collect growth evidence before termination.

Decoded images cost width times height times bytes per pixel, regardless of file size. Rendering with `UIGraphicsImageRenderer` picks the cheapest pixel format; downsampling with ImageIO (`CGImageSourceCreateThumbnailAtIndex`) avoids decoding the full image. Unload large images when the view goes off screen or the app enters the background.

## Memory graph

Debug > Debug Memory Graph (or the debug bar button) pauses the app and shows every live object with its references. Use it to:

- Find leaks: the filter bar's leak button lists objects only referenced in a cycle, with the cycle drawn.
- Count instances: filter by class name to see how many of your controllers or models are alive. Two of something you expected one of is the classic retain cycle symptom.
- Get addresses for the console and for watchpoints.
- See creation backtraces when Malloc Stack Logging is on (scheme > Diagnostics > Logging). "Live Allocations Only" is enough for the graph; "All Allocations and Free History" also explains freed memory.

File > Export Memory Graph writes a `.memgraph` that the command-line tools below accept in place of a live process. Attach it to bug reports.

## Command-line memory tools

```
vmmap --summary App.memgraph                 # regions by type; look at Dirty and Swapped (compressed)
vmmap App.memgraph | grep CG                 # the regions of one kind, with addresses
vmmap -verbose App.memgraph                  # do not collapse adjacent regions
heap App.memgraph                            # object counts per class
heap --sortBySize App.memgraph               # largest classes first
heap --addresses NSConcreteData App.memgraph # addresses of every instance of a class
leaks App.memgraph                           # leaked objects and the cycles they belong to
leaks --traceTree 0x7f8a1c000000 App.memgraph  # who references this address, as a tree
malloc_history App.memgraph --fullStacks 0x7f8a1c000000   # allocation backtrace (needs Malloc Stack Logging)
```

The same tools take a process id or name for a live process. Start with `vmmap --summary`, follow the largest dirty region, find who references it with `leaks --traceTree`, and find who created it with `malloc_history`.

## Allocation backtraces from inside LLDB

```
memory history 0x600003a1c2e0                  # alloc and free stacks when ASan or Malloc Stack Logging is active
command script import lldb.macosx.heap         # Apple's bundled heap helpers
malloc_info --stack-history 0x600003a1c2e0
ptr_refs 0x600003a1c2e0                        # heap blocks that point to this address
cstr_refs "api.example.com"                    # heap blocks containing a C string
objc_refs UIImageView                          # live instances of a class (check help after import)
```

Prefer scheme-enabled Malloc Stack Logging. Some runtimes expose private `turn_on_stack_logging` helpers, but availability and signature vary. Discover and verify the symbol before calling it; such logging cannot reconstruct allocations made before it was enabled.

## Zombies, sanitizers, checkers

- Zombie Objects (scheme Diagnostics): a message to a freed Objective-C object stops with "message sent to deallocated instance" instead of a random crash. The memory graph then shows the zombie with its history when stack logging is on.
- Address Sanitizer: catches use after free, buffer overflows, and stack misuse in C, Objective-C, and Swift unsafe code. The report in the console includes allocation and free stacks; `memory history` works while it runs. ASan builds are slower and use more memory.
- Thread Sanitizer: data races in Swift and C family code, Simulator and macOS only. Pair with the Thread Sanitizer Runtime Issue breakpoint to stop at the race.
- Undefined Behavior Sanitizer: integer overflow, misaligned pointers, invalid casts.
- Main Thread Checker: UI calls off the main thread. Thread Performance Checker: priority inversions and blocking main-thread calls. Both report runtime issues; add a Runtime Issue breakpoint to pause on them.
- Guard Malloc and Malloc Scribble can expose corruption earlier, but do not guarantee a deterministic failure.

## Instruments, briefly

Allocations tracks heap growth over time with per-type counts and generations (mark a generation before and after an action to see what survived). Leaks runs the leak check periodically. VM Tracker shows dirty and swapped memory per region. Memory debugging in Instruments needs the same `get-task-allow` entitlement as the debugger; check code signing if symbols are missing.

## Reading raw memory

```
memory read -c 64 -f Y 0x600003a1c2e0
x/8xg 0x600003a1c2e0
memory region 0x600003a1c2e0        # readable, writable, executable? stack, heap, or image?
```

Objective-C objects can use non-pointer `isa`, tagged pointers, and authenticated pointers. Use runtime APIs for known Objective-C objects. Native Swift instances use Swift metadata and reference-count storage; do not infer property offsets or pass arbitrary Swift addresses to Objective-C APIs. Obtain storage from debug information and verify its lifetime.

For live-instance searches, singleton storage, and block captures, read [Runtime memory](runtime-memory.md). For private allocation-history API signatures and bounded Python result handling, read [Advanced Python](advanced-python.md).
