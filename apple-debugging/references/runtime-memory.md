# Runtime metadata, blocks, heap instances, and stripped code

Use after identifying a loaded image and the behavior being investigated. Start with runtime metadata and known live objects; widen to heap or section searches only when necessary. Runtime queries and heap walkers can execute code and acquire locks in the paused process.

## Enumerate classes and methods by image

Obtain the exact loaded path with `image list -f`. Objective-C class metadata often survives symbol stripping. This scoped expression prints classes belonging to one image and frees the runtime's copied array:

```text
expression -l objc++ -- @import Foundation; @import ObjectiveC;
expression -l objc++ -- unsigned int $classCount = 0
expression -l objc++ -- const char **$classNames = objc_copyClassNamesForImage("/actual/loaded/image/path", &$classCount)
expression -l objc++ -- (void)({ for (unsigned int i = 0; i < $classCount; ++i) printf("%s\n", $classNames[i]); free($classNames); $classNames = nullptr; })
```

For a selected class, enumerate instance methods on the class and class methods on its metaclass. The bundled [Python helper](../scripts/apple_debug_tools.py) offers `adb-methods ClassName` and `adb-methods --class-methods ClassName`, printing selector, type encoding, IMP, and image lookup context. It executes a bounded runtime query and frees the copied method list. A class can have methods from categories in other images, so the class's image is not necessarily every method's image.

Third-party class-dump commands, when installed, offer richer browsing and header-like dumps. A generated declaration is a hypothesis from metadata, not the original header, ownership annotations, generics, or source implementation. Native Swift types need Swift metadata/debug info; not every Swift type is an Objective-C class.

## Improve a stripped backtrace

1. Preserve the original `bt`, loaded-image UUIDs/slides, and PCs. Look for matching dSYMs first.
2. Enumerate candidate class and metaclass methods. Build a multimap from IMP to every matching method name, retaining module identity.
3. For each frame, ask LLDB for the containing function/symbol start. Match that start against the IMP map. Function-start metadata or unwind ranges may help even without names.
4. Annotate only supported matches, with `PC - IMP` as the offset. A return PC may refer just beyond a call; preserve it separately from any adjusted source-lookup address.
5. Leave unmatched frames unresolved. Choosing the nearest lower IMP in the entire image can assign unrelated code, thunks, or another function to the wrong method.

One IMP can implement several selectors, and swizzling can change the map. Rebuild after relaunch, image changes, or runtime replacement. This recovers possible Objective-C method labels, not local variables, source lines, or all stripped C/Swift names. If a third-party stripped-backtrace command is installed, compare its result with the raw stack instead of treating every recovered label as exact.

## Inspect a block without calling it

A block is an object plus an invocation function and captured storage. On a conventional 64-bit Apple block ABI, the prefix is:

```c
struct BlockPrefix {
    void *isa;
    int flags;
    int reserved;
    void *invoke;
    void *descriptor;
};
```

For a **known live block**, the bundled `adb-block 0xADDRESS` reads this prefix without target execution. It reports flags, invoke, and descriptor addresses, then resolves the invocation address. It deliberately rejects non-64-bit targets and does not certify arbitrary memory as a block.

The descriptor begins with reserved and size fields. Optional copy/dispose helpers shift the signature's position; consult the flags before reading further. Captures may include objects, scalars, weak references, and `__block` forwarding cells. They are not all object pointers. A stack block can escape only through the appropriate copy/ownership mechanism.

Set an address breakpoint on the resolved invocation function to observe normal execution. The block pointer is its first ABI argument, preceding explicit arguments. Do not cast `invoke` to `void (*)(void)` and call it. Structure returns, captured lifetime, and arm64e pointer authentication add constraints. If raw pointer resolution fails on arm64e, obtain a canonical callable address through supported debugger/runtime facilities rather than masking bits.

This is the 64-bit layout; do not copy its offsets to 32-bit or arm64_32 targets.

## Find instances and singleton storage

Prefer the memory graph, a known owner, a breakpoint on initialization, or a getter whose side effects are acceptable. A heap scan is useful when the object is alive but there is no obvious source-level path to it. If a third-party heap-search command is installed, inspect its class/subclass, predicate, and result-limit options with `help` before scanning. Heap scanning may stop or walk allocator zones and invoke runtime code. It can miss tagged pointers, non-Objective-C Swift values, custom allocation regions, or objects created after the snapshot.

Validate a candidate's region, allocation lifetime, class, and an independent field/caller before sending messages. An address-looking word is not proof of a live object. Avoid retaining candidates in persistent debugger variables when investigating their deallocation.

For a singleton with symbols, use `image lookup` and the global/static variable's debug info. To observe its first initialization, watch the **pointer storage**, not an object that does not exist yet:

```text
watchpoint set expression -w write -s 8 -- 0xPOINTER_STORAGE
continue
bt
```

Eight is the pointer size only on a verified 64-bit target. When symbols are absent, locate a candidate storage reference in the getter's disassembly, map it to the containing writable/zero-fill section, and watch that specific slot. Calling the getter to discover the object can initialize it and erase the evidence you wanted.

`__bss` means zero-filled storage, not "private variables". `__common` does not contain all globals. `__data`, `__DATA_CONST`, authenticated data, and other sections can also matter. Scanning every word and calling `po` on it is neither a type check nor a reliable singleton finder.

## Cross-references and static analysis

Use `image lookup`, `disassemble`, loaded section ranges, and referenced strings to narrow a hypothesis. `adrp`/`add` can form a global address; a following `ldr` can load a pointer from it. A string's presence does not prove a call executes. Swift small strings may be inline, and dynamic construction can leave no whole string in `__cstring`.

For larger cross-reference graphs, Hopper or IDA can help relate a matching Mach-O slice to functions, strings, selectors, and callers. Import the correct UUID/architecture and account for ASLR when moving between static and live addresses. Decompilation is an approximation. Dynamic Objective-C dispatch and indirect calls may have no complete static caller list; verify the candidate with a live breakpoint or trace.

Interception libraries built on message forwarding are another runtime hook. They change dispatch and can conflict with other hooks or method signatures. Inspect the implementation and supported signatures before using one in an own-app lab; a narrow saved-IMP replacement is easier to attribute to one experiment. See [Dynamic loading and interposition](dynamic-loading-and-interposition.md).

## Investigate a Simulator system process

For an explicitly scoped SpringBoard investigation, use a disposable Simulator and record its UDID/runtime. List its processes through `xcrun simctl spawn <UDID> launchctl list`, identify and verify the exact PID, then attach with LLDB if the platform permits. `pgrep SpringBoard` can select another booted simulator. Do not attach a second debugger to a process already owned by Xcode.

Work from loaded image to classes, method implementations, caller stacks, and narrowly scoped traces. Keep private class/selector names as discoveries for that OS build, not permanent APIs. An attach denial is evidence about the platform's policy; follow [Signing and attach diagnostics](signing-and-attach-diagnostics.md).

Historical drag-and-drop `NSUserDefaults` keys may no longer exist or control the same feature. Discover the current key and domain at the read site, record whether a persistent value was absent, and test one override. Restore absence by removing the key, not by setting it to false; restore any prior stored value exactly. The effective `objectForKey:` value can come from registration or another domain, so it is insufficient as a backup of persistent storage. Relaunch and verify normal Simulator behavior after any hook, environment, or defaults experiment.
