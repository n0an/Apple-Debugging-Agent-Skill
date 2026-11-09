# Assembly, registers, and the ABI

Use when source variables are unavailable, an argument is wrong before your code runs, or a stripped stack needs interpretation. Identify the **running slice**, calling convention, and exact instruction first. Simulator arm64, device arm64/arm64e, and translated x86_64 are not interchangeable environments.

## Recover arguments and returns

For ordinary C-family calls on Apple platforms:

| Value | arm64 | x86_64 |
|---|---|---|
| Integer/pointer arguments | x0-x7 | rdi, rsi, rdx, rcx, r8, r9 |
| Floating-point arguments | v0-v7, viewed as sN/dN | xmm0-xmm7 |
| Integer/pointer result | x0, sometimes x0/x1 | rax, sometimes rax/rdx |
| float/double result | s0 or d0 | xmm0 |
| Objective-C receiver and selector | x0, x1 | rdi, rsi |
| First explicit integer/pointer ObjC argument | x2 | rdx |

Aggregates, vectors, variadic functions, indirect results, and language-specific conventions need the exact signature. arm64 can use x8 for indirect result storage. Integer and floating-point arguments use separate register classes; do not count a `double` as occupying an integer slot. Apple variadic stack rules differ from generic AArch64 examples.

`$arg1` is an argument alias, **not a portable return-value alias**. On x86_64 it does not name rax. Swift native calls can pass metadata, witness tables, contexts, error results, and async contexts through additional conventions. Read the demangled signature and call site instead of casting a native Swift entry point to an arbitrary C function pointer.

Stop before the prologue changes argument registers:

```text
breakpoint set -n probe_value -K false
run
disassemble -f -b
register read x0 x1 x2 x8 pc sp fp lr
thread step-inst
```

This register list is arm64-specific. For a known `int probe_value(int)` call with input 3, x0 should contain 3 at entry. `thread step-out` runs the function; inspect w0 immediately afterward for its `int` result. `thread return 6` instead skips the remaining implementation, including cleanup and side effects. Variables read before their prologue spills execute can look uninitialized even in a debug build.

For an Objective-C method, inspect the method type encoding before interpreting registers. An `id` cast and `po` execute code and do not validate a pointer. Use raw registers and memory for a corruption investigation.

## Follow the decision in arm64 instructions

| Instruction pattern | Debugging question |
|---|---|
| `ldr`, `ldp` | Which address supplies the value? |
| `str`, `stp` | Which storage changes, and by how many bytes? |
| `adr`, `adrp` followed by `add` or `ldr` | Is this computing an address or loading through one? |
| `cmp`, `tst`, `b.eq`, `b.ne`, `cbz`, `cbnz`, `tbz`, `tbnz` | Which observed value chooses the path? |
| `bl`, `blr` | Direct or indirect call; what is the destination now? |
| `ret`, authenticated return variants | What unwind/calling convention restores the caller? |

`ldr x0, [x1, #8]` reads eight bytes from x1+8; `add x0, x1, #8` only computes that address. Writing w0 also clears the upper half of x0. Apple arm64 instructions are four bytes wide and data is little-endian. Intel/AT&T disassembly syntax settings apply to x86, not arm64.

```text
register read x1
memory region 0xADDRESS
memory read -f x -s 8 -c 4 0xADDRESS
image lookup -a 0xDESTINATION
disassemble -s 0xDESTINATION -c 16
```

Use values from this stop, never addresses copied from another run. PC is a virtual address. A debugger may write PC, but that does not make it an ordinary ARM arithmetic operand. Jumping across a prologue, epilogue, function, or async suspension point can invalidate stack, ownership, and authentication state.

## Stack frames and DWARF

arm64 uses sp, commonly x29 as frame pointer and x30 as link register. A common prologue saves x29/x30 with `stp` and maintains 16-byte stack alignment, but leaf functions, tail calls, optimizations, and omitted frame pointers change the pattern. LR alone is not a complete backtrace.

```text
bt
frame select 1
frame info
register read
image lookup -v -a 0xPC
```

Registers displayed for an older frame may be reconstructed by the unwinder; selecting that frame does not rewind the real process. Volatile registers may be unavailable or no longer contain arguments. Compare unwind information, caller instructions, and saved stack values before accusing the callee.

`DW_OP_fbreg` is relative to the DWARF frame base, which is not necessarily x29. A variable can move between registers and stack locations over different PC ranges, have pieces in multiple places, or be optimized away. Recompiling with debug info cannot reconstruct a value eliminated from an already running optimized binary. The stack and heap need not be adjacent.

On arm64e, use LLDB's supported address resolution and the runtime's typed function pointers. Do not invent a bit mask to remove pointer authentication, copy signed pointers between unrelated contexts, or assume a raw memory patch is a valid call target.

For address translation and section analysis, read [Debugging without source](debugging-without-source.md).
