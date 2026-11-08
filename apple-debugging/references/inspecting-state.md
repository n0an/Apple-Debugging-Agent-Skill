# Inspecting state

Stopping is useless unless you can read the state and trust what you read. This file covers variables, objects you only know by address, assembly frames, threads, images, and raw memory.

## Variables in the current frame

```
v                      # every argument and local, formatted
v -a                   # locals only (no args)
v self                 # one variable
v self.view.frame      # a path, dynamic type resolved at each step
v -T self              # with types
v -R self              # raw, no formatters
vo self                # description without compiling
v -f x count           # one-off format
p self.items.count     # evaluate (dwim-print)
po self.items          # description
p -- -x                # expression that starts with a minus
```

Use `v` for anything you can reach with `.`, `[]`, and `*`. Use `p` when you need a method call, arithmetic, a computed property, or an overloaded operator. Use `po` when the type's own description tells the story (view hierarchies, layers, errors, URL requests).

In the Xcode Variables view: right-click a value for Print Description, Watch, View Value As, and Add Expression (a watched expression re-evaluated on every stop). Quick Look (the eye icon) renders `UIImage`, `NSImage`, `CGImage`, `UIView`, `NSView`, `CGPath`, `UIBezierPath`, `UIColor`, `NSData`, `NSURL`, strings, and attributed strings visually. Hover over an identifier in the editor while paused to see its value.

## Objects you only know by address

Addresses come from the view debugger (Edit > Copy on a selected object gives the pointer), the memory graph, `recursiveDescription`, logs, crash reports, or a breakpoint in a frame without source.

Objective-C context:

```
expression -l objc -O -- (id)0x600003a1c2e0
expression -l objc -O -- [(UIView *)0x600003a1c2e0 superview]
expression -l objc -- id $v = (id)0x600003a1c2e0
expression -l objc -O -- [$v valueForKey:@"titleLabel"]     # KVC reaches private ivars and properties
```

Swift context:

```
expression -l swift -- import UIKit                       # once, if UIView is unresolved
expression -l swift -O -- unsafeBitCast(0x600003a1c2e0, to: UIView.self)
expression -l swift -- let $v = unsafeBitCast(0x600003a1c2e0, to: CheckoutViewController.self)
p $v.cart.items.count
```

`unsafeBitCast` returns a typed object, so property access and method calls work. The Objective-C route works without knowing the type at all, including for Swift classes that inherit from `NSObject`.

## Frames without source: registers and $arg

When you stop in a system framework or a stripped binary, there are no variables, only registers. The calling convention tells you where arguments are.

| | arm64 (devices, Apple silicon Macs and Simulators) | x86_64 (Intel Macs and Simulators) |
|---|---|---|
| Integer and pointer args | `x0` ... `x7`, rest on the stack | `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, rest on the stack |
| Return value | `x0` | `rax` |
| Frame pointer / return address | `fp` (`x29`) / `lr` (`x30`) | `rbp` / stack |
| Program counter / stack pointer | `pc`, `sp` | `rip`, `rsp` |

LLDB abstracts this with `$arg1`, `$arg2`, ... which map to the right register for the architecture (integer and pointer arguments only). For an Objective-C method:

```
po $arg1               # self (the receiver)
po (SEL)$arg2          # _cmd, needs the cast or you see a number
po $arg3               # first parameter
po [$arg1 class]       # which subclass this is
po (char *)$arg2       # the selector as a C string
```

Count the colons in the selector to know how many parameters follow `$arg2`. Registers are reliable at the first instruction of a function; `settings set target.skip-prologue false` makes breakpoints stop there instead of after the prologue. Swift's convention differs (self is often in a different register or on the stack), so for Swift frames without source prefer `disassemble` plus `register read` over `$arg`.

```
register read                 # general purpose registers
register read -a              # everything
register read x0 x1 x2
register read -f d x0         # as signed decimal
register write x0 0x0         # change an argument before the function uses it
p/x $pc
```

## Backtraces, threads, frames

```
bt                        # current thread
bt 8                      # first eight frames
bt all                    # every thread; the way to spot a deadlock or a main thread stuck in a wait
thread list               # threads with queue names and stop reasons
thread select 3           # or: t 3
thread info               # current thread, includes os_activity info when present
frame select 2            # or: f 2
up / down
frame info                # function, file, line, pc
```

Read a backtrace as a census: your Swift frames, then `@objc` thunks, then UIKit or AppKit in Objective-C, Core Animation in C++ (`::` in names), Core Foundation run loop in C (`CFRunLoop*`), then `main`. Frames tagged `[opt]` were compiled with optimization; their variables may be unavailable.

Swift concurrency: an async function is split into partial functions around each `await`, so one source function shows up as several frames, and after an `await` the continuation may run on another thread. LLDB and Xcode reconstruct the logical async call chain in the backtrace.

To step only the current thread while every other thread stays frozen, hold Control-Shift while clicking Xcode's step buttons, or pass `--run-mode this-thread` to the thread step commands.

## Images and symbols

```
image list                          # every loaded module with UUID, load address, path, dSYM
image list -b                       # names only
image lookup -a $pc                 # which module and symbol contains an address
image lookup -va 0x1045c2e10        # verbose: compile unit, function, line entry, variable locations
image lookup -n "-[UIView layoutSubviews]"
image lookup -rn 'viewDid' MyApp    # regex, scoped to one module
image lookup -t CheckoutState       # type information
image lookup -s main                # a symbol by name
image dump sections MyApp
image dump symtab MyApp
```

`image lookup -rn` is `grep` for loaded code. It is the fastest way to discover Apple's private method names, find the exact spelling for a symbolic breakpoint, or confirm that a module you expect is actually loaded.

## Objective-C runtime introspection

These private helpers exist on every `NSObject` in the iOS and macOS runtimes and work in an Objective-C expression even for Swift subclasses of `NSObject`:

```
expression -l objc -O -- [$v _ivarDescription]          # every ivar with values
expression -l objc -O -- [$v _methodDescription]        # methods including inherited
expression -l objc -O -- [$v _shortMethodDescription]   # methods declared on the class only
expression -l objc -O -- [NSClassFromString(@"UIKeyboardLayoutStar") _shortMethodDescription]
expression -l objc -O -- [[$v class] superclass]
expression -l objc -O -- object_getClass($v)            # the real class, including KVO subclasses
language objc class-table dump UIButton -v              # ivar offsets and sizes (for watchpoints)
```

Swift:

```
p type(of: value)
po dump(value)                        # structure with child values
p Mirror(reflecting: value).children.map { $0.label }
language swift refcount object        # retain counts of a Swift object
```

## Memory

```
memory read 0x16fdff0                            # 32 bytes, hex
memory read -c 64 -f Y 0x16fdff0                 # bytes with ASCII
memory read -s 8 -f x -c 4 $sp                   # four 8-byte words
x/8xg $sp                                        # same, GDB style
x/s 0x1000a0                                     # C string
memory read -r -b -o /tmp/payload.bin -c 4096 `(uintptr_t)[$data bytes]`   # dump an NSData to a host file
memory region 0x600003a1c2e0                     # permissions of the page (r-x means code)
memory find -s "secret" -- 0x100000000 0x101000000
memory history 0x600003a1c2e0                    # allocation and free backtraces when ASan or Malloc Stack Logging is on
```

The `-o` dump with `-b` is the simplest way to copy a file or buffer out of a device process to your Mac without any app code.

## Disassembly

```
disassemble -f            # current function
disassemble -p -c 12      # around the pc
disassemble -m            # mixed source and assembly
disassemble -b            # with opcode bytes
disassemble -n "-[UIViewController viewDidLoad]"
disassemble -a 0x1045c2e10
```

Xcode: Debug > Debug Workflow > Always Show Disassembly. The green marker is the next instruction; the `bl` (arm64) or `call` (x86_64) just above it is the call that reached the current function.

## Run loop and UI state from anywhere

Paused with the pause button, you have no `self`, but globals are always reachable:

```
expression -l objc -O -- [[[UIApplication sharedApplication] keyWindow] recursiveDescription]
expression -l objc -O -- [[[[UIApplication sharedApplication] keyWindow] rootViewController] _printHierarchy]
expression -l objc -O -- [[UIApplication sharedApplication] delegate]
expression -l objc -O -- [NSThread callStackSymbols]
expression -l objc -O -- [[NSBundle mainBundle] bundlePath]
expression -l objc -O -- [[NSFileManager defaultManager] contentsOfDirectoryAtPath:NSHomeDirectory() error:nil]
expression -l objc -O -- [[NSProcessInfo processInfo] environment]
expression -l objc -O -- [[NSUserDefaults standardUserDefaults] dictionaryRepresentation]
```

macOS equivalents use `NSApp`, `[NSApp keyWindow]`, `[[NSApp keyWindow] contentView]`, and `_subtreeDescription` instead of `recursiveDescription`.
