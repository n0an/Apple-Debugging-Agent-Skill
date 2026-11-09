# Advanced LLDB Python and allocation histories

Use for repeated investigations that need structured results, runtime metadata, or bounded memory inspection. Start with [Custom commands](custom-commands.md) for registration and callbacks. A Python command runs in the debugger; its expression evaluations run in the target. Those are different address spaces and failure modes.

## Session-local helper commands

Import the bundled [apple_debug_tools.py](../scripts/apple_debug_tools.py) using its actual installed absolute path:

```text
command script import /absolute/path/apple-debugging/scripts/apple_debug_tools.py
help adb-lookup
adb-lookup --module MyApp --limit 20 'Checkout|Payment'
adb-methods ExampleController
adb-methods --class-methods ExampleController
adb-block 0xKNOWN_LIVE_BLOCK
```

`adb-lookup` searches symbol names with Python regex and groups results by full image path and UUID. It labels file addresses when the image is not loaded. It complements `image lookup`, which can also use debug information and source/line contexts. Python `(?i)` regex syntax here does not imply LLDB's native regex engine accepts it.

`adb-methods` takes the runtime class name: a Swift class needs its module prefix (`adb-methods MyApp.CheckoutViewController`). It executes a runtime query on the selected frame, listing up to 128 methods declared on the selected class or metaclass. It excludes inherited methods and bounds printed names/encodings. `adb-block` only reads the 64-bit prefix of a known live block. See [Runtime memory](runtime-memory.md) for interpretation and stripped-backtrace matching. None of the commands resumes, detaches, installs hooks, or changes global init files.

## Work with SBValue, not formatted strings

Use the five-argument command signature and its `SBExecutionContext`. Check validity and `SBError` at every boundary:

```python
frame = exe_ctx.GetFrame()
if not frame.IsValid():
    result.SetError("Select a frame first.")
    return
value = frame.FindVariable("request")
if not value.IsValid() or value.GetError().Fail():
    result.SetError("request is unavailable in this frame")
    return
raw = value.GetNonSyntheticValue()
field = raw.GetChildMemberWithName("count")
```

Distinguish a pointer's value (`GetValueAsUnsigned`) from its storage (`AddressOf`) and a variable's load address (`GetLoadAddress`). Use `Dereference` only for a valid pointer, and `GetData` for bounded bytes. `GetObjectDescription` can run target code; a summary or synthetic child may also depend on runtime support. `SBProcess.ReadMemory` reads target memory; host `ctypes` cannot dereference a target address.

Query `target.GetAddressByteSize()` and byte order. A 64-bit instruction set does not universally imply eight-byte pointers, as arm64_32 demonstrates. Swift resilient fields, enum payloads, strings, and non-pointer isa/tagged objects invalidate fixed-offset guesses. Small-string capacity is measured in UTF-8 bytes, not user-perceived characters; do not classify every non-ASCII string as a heap allocation.

For symbol resolution, prefer `SBFunction` when available and fall back to `SBSymbol`. A function can appear in many recursive frames, and inline frames do not necessarily have separate machine-code bodies. Preserve original PCs, module UUIDs, architecture, and source-lookup adjustments separately.

## Expression ownership and failures

Set the expression language, timeout in **microseconds**, unwind-on-error behavior, and breakpoint policy explicitly. A timeout can unwind expression execution but cannot roll back side effects. If code takes a lock already held by another stopped thread, more timeout is not the fix.

Generate code only from validated arguments. Prefer `argparse` plus `shlex.split`; override parser errors so a bad command returns `result.SetError` rather than terminating through `SystemExit`. A regex command that interpolates `%1` into Python or C code is not a general-purpose escaping layer.

Keep runtime allocations scoped. Free arrays returned by `class_copyMethodList` and `objc_copyClassNamesForImage`. Prefer a bounded struct/array result to allocating a target buffer merely to pass a few addresses to Python. If allocation is unavoidable, copy the result into host values before cleanup and free it in a `finally` path while the target remains stopped. Do not retain debug objects indefinitely while investigating ARC lifetime.

## Allocation stack logging

Enable logging **before** the allocation being investigated, through the scheme or a launch setting:

```text
settings set target.env-vars MallocStackLogging=1 MallocStackLoggingNoCompact=1
run
```

These settings affect a subsequent launch; record/restore the target's previous environment. `NoCompact` preserves more allocation/deallocation history at a cost. On an accessible macOS process, `malloc_history PID ADDRESS` is the first tool to try. `memory history ADDRESS` can use an available memory-history provider; it is not guaranteed to expose every malloc record on every target.

Addresses can be freed and reused. A last record can describe a free or a later allocation, not the creation of the object you remember. Preserve the PID, address, allocation interval, and reproduction. Enabling logging now cannot reconstruct earlier allocations. Sampling/stack-logging modes and platform support affect completeness.

A custom command can call the private `__mach_stack_logging_get_frames` API. Verify its presence and exact declaration against the matching OS before calling it. A conventional declaration is:

```c
kern_return_t __mach_stack_logging_get_frames(
    task_t task, mach_vm_address_t address,
    mach_vm_address_t *frames, uint32_t capacity, uint32_t *count);
```

The current task port is a Mach port value, not a `void *`. A bounded result can contain `kern_return_t status`, `uint32_t count`, and `mach_vm_address_t frames[128]`. Zero-initialize it, pass capacity 128, then reject a non-success status or count above capacity before resolving each PC with `ResolveLoadAddress`. This avoids allocating a target buffer that must be freed later. Return addresses and exact current PCs need different source-line handling; do not subtract one indiscriminately from every address.

`turn_on_stack_logging` is also private and has changed across versions. Historical declarations return `boolean_t`, not `void`; inspect the matching header and mode enum instead of guessing an integer mode. Prefer launch-time configuration. A third-party command that wraps these APIs needs the same review of its casts, error handling, and cleanup on the current OS.

## Debug the debugger script

```text
script import sys; print(sys.version); print(sys.executable); print(sys.path)
script import lldb; print(lldb.__file__)
```

The Python embedded in Xcode LLDB can differ from shell Python. `xcrun lldb -P` locates the bindings, but importing them from a standalone interpreter also requires compatible Python minor version, architecture, `_lldb`, and framework dependencies. Set paths only for that invocation; do not globally overwrite `PYTHONPATH` based on old installation paths.

Separate Python syntax/import failures, Python exceptions, expression-compiler diagnostics, and target execution errors. Print generated expression code with line numbers when compilation fails. Reload only your module and re-register its owned commands idempotently. A terminal LLDB session can use `pdb` or post-mortem Python debugging; Xcode's debugger console is not a full interactive terminal. Python post-mortem inspection does not rewind target execution.

Do not call `StepOut`, `Continue`, or change global async mode from a breakpoint callback to implement a multi-stage operation. Return the stop decision, then step explicitly or use a [scripted thread plan](remote-and-tooling.md). Preserve unexpected stops and user breakpoints.
