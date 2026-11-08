# Fundamentals

LLDB is the debugger behind Xcode's debug bar, variables view, and console. Everything Xcode shows you is an LLDB command whose output got a UI. Learning the commands gives you more than the UI shows and lets you automate the parts you repeat.

## How LLDB is wired

- The debugger is a separate program. On one side it talks to the kernel and the target process through `debugserver` (the `ptrace` family and Mach APIs). On the other side it talks to you through the command line, Xcode, or the Python API. All three clients call the same library.
- LLDB is also a compiler. For `expression`, `p`, and `po` it embeds the Swift and Clang compilers, compiles the text you typed in the context of the current frame, injects the machine code into the process, runs it, and reads the result back. That is why expressions can fail even when the variables view works: the variables view only needs debug info and reflection metadata, the expression evaluator also needs modules (see `swift-debugging.md`).
- While the process is stopped, the rest of the system keeps running. The render server, other processes, and the network do not wait for you. This is why UI changes made from the console only appear after you flush Core Animation (see `modifying-runtime-state.md`).

## Command grammar

```
<noun> <verb> [-options [option-value]] [--] [argument [argument ...]]
```

Examples:

```
process launch --stop-at-entry -- -program_arg value
breakpoint set -f LoginViewController.swift -l 42
expression -l swift -O -- self.view
```

Rules that bite:

- Options and arguments are whitespace separated. Quote arguments that contain spaces: `breakpoint set -n "-[UIView hitTest:withEvent:]"`.
- `--` ends the options. Required whenever an argument starts with `-`, and always after `expression` options because the expression itself may contain minus signs.
- Backticks evaluate an expression and splice the result in as text: `memory read -c `len` 0x12345`, `expression -l objc -O -- [`self.view` recursiveDescription]`. This is also how you move a value from the Swift frame into an Objective-C expression.
- Raw commands (`expression`, `script`) take the rest of the line as-is after their options.
- Any unique prefix works: `br s`, `im loo`, `fr v`, `th ret`, `re r`, `di -f`. LLDB also ships GDB-style aliases: `b`, `r`, `c`, `n`, `s`, `finish`, `bt`, `f`, `up`, `down`, `x`, `p`, `po`, `t`, `tbreak`.
- Press Enter on an empty line to repeat the previous command. Perfect for `n`, `finish`, and nudging a view by one point at a time.

## Getting help

```
help                          # every command and alias
help breakpoint set           # options of one subcommand
help <breakpt-id>             # argument types in angle brackets have their own help
apropos watch                 # search help text for a keyword
help expression               # shows the aliases p and po and what they expand to
```

`help` on an alias prints both your help text and the underlying command's help.

## The five command families

| Family | Commands | What they do |
|---|---|---|
| Stop | `breakpoint`, `watchpoint` | decide where and when the process pauses |
| Look | `frame variable` (`v`), `expression` (`p`, `po`), `thread backtrace` (`bt`), `frame info`, `thread list`, `image`, `memory read`, `register read`, `disassemble` | read state |
| Move | `thread step-over` (`n`), `thread step-in` (`s`), `thread step-out` (`finish`), `thread until`, `thread return`, `thread jump`, `process continue` (`c`), `process interrupt` | control execution |
| Do | `expression` (mutate, call), `script`, `command source`, `platform shell` | run code in the process or on the host |
| Setup | `command alias`, `command regex`, `command script import`, `settings`, `type summary`, `help` | configure the debugger |

## Print commands: which one when

| Command | Alias for | Compiles code? | Output | Use when |
|---|---|---|---|---|
| `v x` / `frame variable x` | - | no | formatted by LLDB's data formatters, dynamic type resolved at each step of the path | first choice for Swift inspection, works when expressions fail, fastest |
| `p x` | `dwim-print -- x` (Xcode 15+), `expression -- x` before | tries frame variable first, then compiles | formatted by data formatters, result named `$R0`/`$0` | expressions, method calls, arithmetic, anything `v` cannot evaluate |
| `po x` | `dwim-print -O -- x` | yes, then calls the description | `debugDescription` (Swift `CustomDebugStringConvertible`, Objective-C `debugDescription`, falling back to `description`) | when the object's own description is what you want |
| `vo x` | `frame variable -O x` | no | description without compiling | Swift objects when you only need to look |
| `expression ...` | - | yes | depends on options | explicit language (`-l`), ignore breakpoints (`-i0`), top-level declarations (`-p`) |

Details worth remembering:

- `v` has its own tiny syntax: `.`, `->`, `[]`, `*`, `&`. No method calls, no computed properties, no operator overloads. It resolves the dynamic type at every step, so `v activity.name` works even when `activity` is declared as a protocol type and `p activity.name` fails with "no member name" until you cast.
- `p` applies dynamic type resolution only to the final result, then hands it to the formatters. Add `--raw` to `p` or `-R` to `v` to see the unformatted structure.
- `po` runs two compilations: one for your expression, one to obtain the description. It is the slowest and the one that breaks first when the expression context is unhealthy.
- `p` and `po` print the same information for most types; `po` is just shaped by the type's own description. For `CALayer` and other Apple classes, `debugDescription` is far richer than `description`.

## Language context

LLDB picks the expression language from the frame you are stopped in: Swift code gives you Swift, Objective-C or C or C++ gives you Objective-C++. Two traps:

- Pausing with Xcode's pause button, or stopping in a system framework, lands you in an Objective-C context even if your app is pure Swift.
- A raw address is an integer in Swift. `po 0x7fd3a0c1e2f0` prints the number. The same address in Objective-C is an object: `expression -l objc -O -- 0x7fd3a0c1e2f0` prints its description.

Override the language per command:

```
expression -l objc -O -- [UIApplication sharedApplication]
expression -l swift -O -- UIApplication.shared
expression -l objc++ -- (void)[CATransaction flush]
```

`po` cannot take `-l` because its arguments come after `--`. Alias the long forms (see `custom-commands.md`):

```
command alias cpo expression -l objc -O --
command alias spo expression -l swift -O --
command alias sp  expression -l swift --
```

Imports differ by context: in an Objective-C expression you may need `@import UIKit;` so the compiler knows property types; in a Swift expression you may need `import UIKit` or `import MyModule` when a type from another module is not visible.

## Persistent variables and results

- Every `p`/`po`/`expression` result gets a name: `$0`, `$1` in C contexts, `$R0`, `$R1` in Swift. Use them later: `p $R0.title`, `po [$0 superview]`.
- Declare your own with a `$` prefix. Swift: `e let $vc = unsafeBitCast(0x600001234560, to: DetailViewController.self)`. Objective-C: `e id $view = (id)0x600001234560`. Without the `$` the variable dies at the end of the expression.
- Variables belong to the context they were created in. A `$view` from an Objective-C expression is unknown to a Swift expression. Recreate it in the other language if you need it there.
- `$` also names registers and pseudo-registers: `$pc`, `$sp`, `$fp`, `$lr`, `$x0`, `$rax`, and the arch-neutral `$arg1`, `$arg2`, ... (see `inspecting-state.md`).

## expression options you will actually use

| Option | Effect |
|---|---|
| `-l <lang>` | language: `swift`, `objc`, `objc++`, `c++` |
| `-O` | print the object description (what `po` does) |
| `-i 0` | do not ignore breakpoints while evaluating; lets you step into a method you call from the console |
| `-u 0` | do not unwind on error; leaves you at the crash site when the called code crashes |
| `-p` | top-level declaration (persistent functions, globals, classes) |
| `-d run-target` / `no-run-target` / `no-dynamic-values` | dynamic type resolution policy for the result |
| `-f <fmt>` | LLDB format for the result (`x`, `d`, `Y`, `s`, ...) |
| `-G <fmt>` | GDB format letter, same as the `p/<fmt>` shorthand |
| `-T` | show types in the output |
| `-t <seconds>` | timeout for long-running expressions |
| `-g` | debug the expression itself (steps into the JIT code) |

## Format shorthands

```
p/x 255          # 0xff
p/t 10           # 0b1010
p/d 'A'          # 65
p/c 65           # 'A'
p/a $pc          # address with symbol
x/4xw 0x16fdff0  # 4 words, hex
x/8xg $sp        # 8 giant words (64-bit), hex
x/s 0x1000a0     # C string
x/6i $pc         # 6 instructions
memory read -f Y -c 64 0x16fdff0   # bytes with ASCII
```

GDB letters: `x` hex, `d` decimal, `u` unsigned, `o` octal, `t` binary, `a` address, `c` char, `f` float, `s` string, `i` instruction. The size letters for `x/` are `b` byte, `h` halfword, `w` word, `g` giant word.

## Settings you will touch

```
settings list                                   # everything, grouped
settings show target.source-map
settings set target.source-map /build/server/path /Users/me/project
settings set target.process.thread.step-avoid-regexp '^std::'
settings set target.skip-prologue false         # break at the first instruction of a function
settings set stop-disassembly-display no-debuginfo
settings set target.max-string-summary-length 10000
settings set target.max-children-count 512
settings set target.inline-breakpoint-strategy always
settings set target.language swift              # default expression language when LLDB cannot tell
```

Put the ones you always want into `~/.lldbinit` (see `custom-commands.md`).

## Xcode UI to LLDB

| Xcode | LLDB |
|---|---|
| Pause button | `process interrupt` |
| Continue, step over, step into, step out | `c`, `n`, `s`, `finish` |
| Debug navigator thread list | `thread list` |
| Debug navigator backtrace | `bt` (`thread backtrace`), `bt all` |
| Click a frame | `frame select N` (`f N`), `up`, `down` |
| Variables view | `frame variable` (`v`); it hides some private ivars that `v` shows |
| Right-click a variable, Watch | `watchpoint set variable` |
| Edit Breakpoint popover | `breakpoint modify -c ... -i ... -G ...`, `breakpoint command add` |
| Breakpoint navigator | `breakpoint list` |
| Symbolic breakpoint | `breakpoint set -n <symbol> [-s <module>]` |
| View debugger, Edit > Copy on a view | the object's address, ready for `expression -l objc -O -- (id)0x...` |
| Memory graph, selected object | address shown in the inspector |
| Debug > Attach to Process | `process attach --name` / `--pid` / `--waitfor` |

Three Debug navigator buttons at the bottom filter the backtrace to frames with source; turn them off when the interesting frame is in a system framework.
