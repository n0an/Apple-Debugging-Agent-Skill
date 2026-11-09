# Advanced DTrace experiments

Read [Tracing](tracing-and-dtrace.md) first. List the exact provider/probes on the current OS, choose one verified PID, and keep stderr. Permission failures, unavailable probes, dropped events, and copy faults are evidence, not noise to redirect away.

## Scope and correlate events

The `pid` provider's module field names an image; the `objc` provider's module field names a class. Entry probes and instruction-offset probes have different costs. `pid` is not restricted to non-Objective-C code. DTrace actions cannot call arbitrary Objective-C methods inside the target.

Use thread-local state for a synchronous call chain and a depth key for recursion:

```d
pid$target:MyProbe:work:entry
{
    self->depth++;
    self->started[self->depth] = timestamp;
}

pid$target:MyProbe:work:return
/self->depth > 0/
{
    @duration_ns = quantize(timestamp - self->started[self->depth]);
    self->started[self->depth] = 0;
    self->depth--;
}
```

Match this to a verified image and symbol. Mid-call attachment, unmatched returns, exceptions/longjmp, or lost events can leave incomplete state. Thread-local correlation does not follow asynchronous work to another thread; use an explicit operation identifier or signposts for that case. Use aggregations rather than per-event printing for high-frequency paths.

## Read user memory using the correct syscall signature

```d
syscall::open:entry,
syscall::open_nocancel:entry
/pid == $target && arg0 != 0/
{
    printf("%s\n", copyinstr(arg0));
}

syscall::openat:entry,
syscall::openat_nocancel:entry
/pid == $target && arg1 != 0/
{
    printf("%s\n", copyinstr(arg1));
}
```

Keep only probe names returned by `dtrace -l` on this OS. In `openat`, arg0 is a directory file descriptor and the pathname is arg1. A broad `open*` pattern with `copyinstr(arg0)` is incorrect. `copyin` reads a bounded byte region; `copyinstr` reads a user-space C string into DTrace's context. A non-null pointer can still fault, change concurrently, or exceed the configured string bound.

## Destructive actions are useful, scoped experiments

The `-w` option enables actions that can alter a process or execute host commands. It is not needed for ordinary observation. In an authorized disposable lab:

| Action | Use | Recovery/limit |
|---|---|---|
| `stop()` | Freeze the process that triggered a precise event, then inspect it | DTrace exiting does not resume it; verify PID and send `SIGCONT` after inspection |
| `raise(signal)` | Exercise the target's signal handling | Signal semantics apply; SIGSTOP/SIGKILL cannot be caught |
| `copyout` / `copyoutstr` | Change a known writable buffer to test a hypothesis | Require verified capacity, lifetime, and byte count; relaunch restores initial state |
| `system()` | Invoke a fixed host command on an event | Runs with the consumer's privileges and is deferred; never interpolate untrusted event strings into a shell command |

A one-event stop recipe, after verifying the probe, is:

```sh
sudo dtrace -w -p 12345 -n 'pid$target:MyProbe:work:entry /pid == $target && !stopped/ { stopped = 1; stop(); exit(0); }'
```

Replace 12345 with the verified lab PID. Before resuming with `kill -CONT 12345`, recheck that the PID still names the same process. If LLDB was attached for inspection, finish its detach/resume lifecycle as well. Do not interpret a process left stopped by this experiment as a newly discovered hang.

### A bounded memory-change example

Make an own-process fixture whose `open` argument points to a writable buffer with known capacity:

```c
char path[64] = "/tmp/adb-original";
int fd = open(path, O_RDONLY);
```

Create the intended original and replacement fixture files, confirm the exact syscall probe, and inspect `path` before enabling this D program:

```d
syscall::open:entry
/pid == $target && !changed && copyinstr(arg0) == "/tmp/adb-original"/
{
    changed = 1;
    copyoutstr("/tmp/adb-new", arg0, 13);
    exit(0);
}
```

`/tmp/adb-new` is 13 UTF-8 bytes including its NUL terminator, so the bound 13 is sufficient and below the known 64-byte capacity. For other strings, calculate bytes including NUL, not characters or newline-bearing `echo | wc` output. In this example, scope to `open` only; an observed `openat` needs arg1 and a separate clause.

The original pathname's length and a pointer above 4 GiB do not prove writability or capacity. Do not apply a broad pathname rewrite to arbitrary string literals or unknown allocations. Verify the changed argument and resulting behavior, then relaunch without DTrace. Kernel/provider restrictions can prevent this experiment even when read-only tracing works.

These destructive examples are documented lab procedures, not a claim that they run on every modern Apple system. No SIP, signing, or global environment change is implied.
