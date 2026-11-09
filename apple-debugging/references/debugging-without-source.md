# Debugging without source

Use for an accessible SDK/framework, command-line tool, macOS app, or Simulator process when source is unavailable. Start with the loaded image and exact architecture, then narrow to a symbol, receiver, and call site. Kernel debugging and bypassing process protections require a separate workflow.

## Identify the binary before interpreting addresses

On the host, inspect a binary you have:

```sh
file /path/to/MyApp
xcrun lipo -archs /path/to/MyApp
xcrun dwarfdump --uuid /path/to/MyApp
xcrun otool -L /path/to/MyApp
xcrun otool -l /path/to/MyApp
xcrun nm -nm /path/to/MyApp
```

In the stopped process:

```text
target list
image list -o -f
image dump sections MyApp
image lookup -rn 'keyword' MyApp
image lookup -a 0x100012340
```

`image list -o` shows slides, not image load bases. A universal file has multiple slices; a translated x86_64 process on Apple silicon still follows the x86_64 ABI. A stripped symbol table does not imply the Objective-C runtime lost its class and selector metadata. Modern system frameworks may be in the dyld shared cache rather than standalone binaries at old SDK paths. Inspect the loaded image instead of copying a path from an old example.

## Keep three address spaces distinct

- **Runtime/load address**: address in this particular process.
- **Unslid virtual address**: address specified by the Mach-O layout, often called a file address in LLDB.
- **File offset**: byte offset into the selected Mach-O slice on disk.

For an address inside a file-backed segment:

```text
slide = runtime segment address - segment vmaddr
unslid address = runtime address - slide
file offset = segment fileoff + (unslid address - segment vmaddr)
```

Use the containing segment from `otool -l`. The mapping applies only within its file-backed bytes; zero-filled storage has no corresponding file bytes. Do not treat an unslid virtual address as a byte offset. For universal files, account for the slice offset when addressing the outer file. See [Crash symbolication](crashes-and-symbolication.md) for `atos` and UUID matching.

## Find the implementation, including inherited methods

```text
image lookup -rn 'setTitle' MyFramework
breakpoint set -n '-[ExampleController setTitle:]' -s MyFramework
breakpoint list
```

If a class inherits the method, break on the superclass implementation and filter by receiver. When symbols are missing but the Objective-C runtime knows the method, inspect the runtime implementation pointer:

```text
expression -l objc++ -- @import Foundation; @import ObjectiveC;
expression -l objc++ -- Class $cls = (Class)NSClassFromString(@"ExampleController")
expression -l objc++ -- SEL $sel = sel_registerName("setTitle:")
expression -l objc++ -- Method $method = class_getInstanceMethod($cls, $sel)
expression -l objc++ -- (const char *)method_getTypeEncoding($method)
expression -l objc++ -- IMP $implementation = method_getImplementation($method)
image lookup -a `$implementation`
breakpoint set -a `$implementation`
```

Check that `$cls` and `$method` are non-null before calling the next API. Use `class_getClassMethod` for a class method. Method lookup can return an inherited implementation. Recheck if swizzling changes it; do not strip pointer-authentication bits by hand.

At entry, inspect the receiver and arguments using the verified ABI, then `bt` to identify your caller. Do not assume `$arg1` means `self` outside Objective-C method entry, or that every return value is in `x0`. Follow [Inspecting state](inspecting-state.md) for register limits.

## Read just enough assembly

```text
disassemble -f -b
register read pc sp fp lr x0 x1 x2
memory region 0x100012340
```

On arm64, follow `bl`/`blr` calls and `cbz`/`cbnz` or conditional branches around the decision of interest. Pair instructions with observed values instead of guessing from a symbol name. On x86_64 use its registers and call/return convention. LLVM optimization, thunks, and inlining can hide a one-to-one source mapping.

Prefer a scoped setter/selector breakpoint, watchpoint, or caller-side experiment before rewriting machine instructions. Inspect only enough implementation detail to find a supported application-level fix. For an apparent framework defect, preserve a small reproduction, OS/build versions, and the trace that distinguishes it from application misuse.

## Inspect Mach-O structure and binding

Separate the header, load commands, segments, and sections. Load commands describe what the loader needs; sections group particular contents within segments. Useful commands include:

| Load command/content | Debugging question |
|---|---|
| `LC_UUID` | Does this binary match the dSYM/crash image? |
| `LC_BUILD_VERSION` | Is this the correct Apple platform and deployment target? |
| `LC_LOAD_DYLIB`, `LC_RPATH` | Which dependency/path resolution could fail? |
| `LC_SEGMENT_64` | What virtual/file ranges and protections contain the address? |
| `LC_FUNCTION_STARTS`, unwind information | Where might an unnamed function begin? |
| Export trie, bind information, `LC_DYLD_CHAINED_FIXUPS` | How are exported/imported addresses resolved? |
| `LC_CODE_SIGNATURE` | Where is the signing data, independently of symbol/debug data? |

Legacy `__la_symbol_ptr` and GOT examples illustrate indirect bindings, but modern binaries can use chained fixups and authenticated pointers. Bindings belong to each importing image; modifying one consumer's slot does not patch every caller. `__DATA_CONST` can become read-only after fixups. Raw writes that worked on an older Intel binary are not a general rebinding recipe.

Use `image dump sections` and `memory region` to validate a live address before reading it. For strings, read a bounded region and honor NUL boundaries; `__cstring` contains clues, not proof of executed behavior. Zero-fill sections have virtual bytes without backing file bytes. For singleton/global storage and cross-references, see [Runtime memory](runtime-memory.md).

If writing a Mach-O parser, validate magic and byte order, selected architecture/platform, header size, `ncmds`, `sizeofcmds`, every `cmdsize`, section counts, file bounds, and arithmetic overflow. A fat container's byte order/layout is separate from the selected thin slice. A 64-bit fat offset is needed for large offsets beyond 32-bit range, roughly 4 GiB, not 4 MB. Prefer existing parsing tools for an investigation instead of building an unchecked offset walker in an LLDB expression.

## Shared-cache and disassembler workflows

Begin with the loaded system image in LLDB. An SDK stub is not the implementation, and a UIKit wrapper can delegate into another loaded framework such as UIKitCore. Query the actual module list before guessing the binary name.

Offline analysis can use matching dyld shared-cache files and an extractor compatible with that OS/cache format. Historical `dsc_extractor.bundle` APIs and filesystem paths are private and version-dependent; modern caches may have subcaches. Verify that all pieces, architecture, and OS build match before trusting the extracted image. Do not assume every machine contains both Intel and arm64 caches or that a standalone extracted file has the same layout as the running cache.

Feed the matching slice into Hopper/IDA when cross-reference browsing helps, then validate a suspected call path in the process. Keep decompiler guesses separate from runtime evidence. [Assembly and ABI](assembly-and-abi.md) explains arguments, stack frames, and instruction-level checks.

## Injection as a focused experiment

Objective-C swizzling changes runtime method dispatch; dyld interposing redirects eligible dynamically linked C function bindings. Neither replaces arbitrary Swift direct calls or inlined code.

For a concrete interposing lab, saved-IMP replacement, `dlopen`/`dlsym`, and Simulator environment forwarding, read [Dynamic loading and interposition](dynamic-loading-and-interposition.md). Use a disposable app, verify signatures/architecture, preserve original behavior, and relaunch without the injection. Library validation and hardened runtime can affect loading; diagnose those from the actual error.
