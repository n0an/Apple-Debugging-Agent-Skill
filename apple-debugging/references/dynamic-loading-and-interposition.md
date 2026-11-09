# Dynamic loading, interposition, and swizzling

Use to make an own-app reproduction deterministic, observe a call unavailable to source instrumentation, or test a runtime hypothesis. These techniques belong in Apple debugging; they do not require a separate skill. Record the mechanism, affected process, original behavior, and clean-run result.

## Choose the mechanism

| Mechanism | What changes | Important limit |
|---|---|---|
| `dlopen` / `dlsym` | Loads an image / locates a symbol | Loading can run constructors; resolving alone does not hook calls |
| `DYLD_INTERPOSE`-style section | Eligible dynamic symbol bindings | Does not replace all direct, inlined, or Swift calls |
| Symbol-pointer rebinding | Selected import slots in consumer images | Different from interpose tuples; modern fixups, page protections, and PAC matter |
| Objective-C method replacement | Dispatch through a class's selector table | Inherited methods, cached IMPs, concurrent callers, and Swift direct dispatch matter |
| Breakpoint action | A selected stopped call | High hit rates add debugger overhead |

A static library contributes object code at link time. A dynamic framework packages a loadable image and resources. `.tbd` files describe linker-facing symbols; headers/module maps describe compiler-facing declarations. Neither is the runtime implementation. Even when both are arm64, macOS, iOS, and iOS Simulator libraries target different platforms.

Inspect dependencies with `otool -L`, load commands with `otool -l`, and loaded images with `image list -o -f`. Resolve `@rpath`, `@loader_path`, and `@executable_path` relative to the requesting image and its runpaths. `nm -u` shows undefined symbols; `nm -U` excludes them. Those flags do not classify private versus public APIs. Modern exports can also live in export tries.

## Load a diagnostic library explicitly

Use a library built for this process's platform, architecture, and signature requirements. In a stopped development process:

```text
expression -l objc++ -- @import Darwin;
expression -l objc++ -- (void)dlerror()
expression -l objc++ -- void *$probeHandle = dlopen("/absolute/path/libProbe.dylib", RTLD_NOW | RTLD_LOCAL)
expression -l objc++ -- (const char *)dlerror()
expression -l objc++ -- void *$probeSymbol = dlsym($probeHandle, "probe_value")
expression -l objc++ -- (const char *)dlerror()
image list -f
```

Proceed to `dlsym` only if the handle is non-null. Clear/check `dlerror` around each lookup; a null symbol value alone is not the complete error protocol. For a verified exported C signature `int probe_value(int)`, call it with `expression -l objc++ -- ((int (*)(int))$probeSymbol)(3)`. Keep the handle alive while code or data from it is in use. `dlclose` is not an undo button for constructors, swizzles, spawned threads, or retained callbacks. Relaunch is often the correct reset.

Use a C or Objective-C bridge for native Swift code. `@convention(c)` cannot make an arbitrary Swift function with metadata/context parameters C-callable. Treat underscored export attributes as toolchain-specific.

## Reproducible interposing lab

Create these three files in a disposable directory. They use a dedicated function so the replacement does not recursively intercept logging or allocation.

`probe.c`:

```c
int probe_value(int value) { return value * 2; }
```

`main.c`:

```c
#include <stdio.h>
extern int probe_value(int);
int main(void) { printf("%d\n", probe_value(3)); }
```

`hook.c`:

```c
extern int probe_value(int);
static int replacement(int value) { return value + 100; }
__attribute__((used, section("__DATA,__interpose")))
static const struct {
    const void *replacement;
    const void *original;
} bindings[] = {{(const void *)replacement, (const void *)probe_value}};
```

```sh
xcrun clang -g -O0 -dynamiclib probe.c -o libProbe.dylib -Wl,-install_name,@rpath/libProbe.dylib
xcrun clang -g -O0 main.c -L. -lProbe -Wl,-rpath,@executable_path -o probe
xcrun clang -g -O0 -dynamiclib hook.c -L. -lProbe -Wl,-rpath,@loader_path -o libHook.dylib
./probe
env DYLD_INSERT_LIBRARIES="$PWD/libHook.dylib" ./probe
./probe
```

Expected output is 6, 103, 6. The environment change applies only to the middle launch. If injection fails, inspect platform, load errors, hardened runtime, and library validation before changing any protection.

For a wrapper that calls through, resolve the original deliberately: `RTLD_NEXT` searches after the current image; `RTLD_DEFAULT` can find the replacement again. A specific library handle narrows lookup but does not make every binding scheme equivalent. Avoid recursive initialization, preserve `errno` when the contract requires it, and do not log an allocator hook through Foundation or another allocator.

## Scoped Objective-C method replacement

Prefer a test-owned class and an explicit install/restore phase over automatic `+load`. For a method **declared on** `Probe`, `- (int)value:(int)value`, this is a minimal replacement:

```objc
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
static IMP savedIMP;
static int replacementValue(id self, SEL cmd, int value) {
    int original = ((int (*)(id, SEL, int))savedIMP)(self, cmd, value);
    return original + 100;
}
// Install once, before concurrent callers enter the method:
Method method = class_getInstanceMethod([Probe class], @selector(value:));
savedIMP = method_setImplementation(method, (IMP)replacementValue);
// Restore after the experiment, with callers quiescent:
method_setImplementation(method, savedIMP);
```

Validate the class, method, type encoding, and saved IMP before installing. `class_getInstanceMethod` can return a superclass's Method. To limit a change to a subclass, first add a local override with `class_addMethod` and the inherited implementation/type encoding, then look up that local method. Adding an override itself persists until process exit; restoring its IMP does not remove it. Class methods live on the metaclass.

The replacement and any block-backed IMP must remain alive. A cached IMP can continue to call the old implementation, and an in-flight caller can still use the replacement after restoration. Restore while quiescent and relaunch to verify the source fix. Broad `method_exchangeImplementations` examples must also account for inherited methods and double installation.

### Observe NSURLSession creation

For a test build, choose the exact method, such as `dataTaskWithRequest:completionHandler:`. Its replacement must return `NSURLSessionDataTask *` and accept `id`, `SEL`, `NSURLRequest *`, and the correctly typed completion block. Record request method, host, and path, then call the saved IMP exactly once with the unchanged block. Do not execute or wrap the block just to print it.

Observe both request- and URL-based overloads only when needed; delegation between overloads can produce duplicate events. Subclasses, download/upload tasks, background sessions, and other networking stacks need their own evidence. Task creation does not prove `resume` or network transmission. A supported `URLProtocol` test fixture or URLSession metrics may answer the question more directly. In an own-app diagnostic build, swizzling remains useful when the call boundary itself is the question.

## Simulator and launch environments

An environment variable exported in the debugger's shell does not alter an already running app. Use the scheme or a single launch:

```sh
env SIMCTL_CHILD_DYLD_INSERT_LIBRARIES=/absolute/path/libProbe.dylib \
  xcrun simctl launch booted com.example.DebugProbe
```

The library must be built for the Simulator, and the app must actually relaunch. Check `simctl help launch` for the installed Xcode's launch/termination options. Do not interrupt a running user session just to apply an environment variable.

`xcrun simctl spawn booted launchctl setenv NAME VALUE` changes the simulated launchd environment for future children, so its scope is much broader. If a research task requires it, record any previous value with `launchctl getenv`, change only the selected simulator, and restore the old value or use `launchctl unsetenv NAME` afterward. Already injected processes need a clean relaunch. Avoid host-wide `launchctl setenv DYLD_INSERT_LIBRARIES` as a debugging default.

For loading denials, read [Signing and attach diagnostics](signing-and-attach-diagnostics.md).
