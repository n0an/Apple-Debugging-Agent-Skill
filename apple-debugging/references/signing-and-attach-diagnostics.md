# Code signing, attach failures, and anti-debug checks

Use when an attach, launch, library load, or installation fails. Keep the exact error and separate platform policy from the app's own code. A successful attach to a Simulator app does not predict attach rights on a physical device or a hardened macOS distribution build.

## Diagnose the failing layer

| Evidence | Investigate |
|---|---|
| Process already being debugged | Existing Xcode/LLDB owner; preserve that session |
| Device unavailable or debugger connection fails | Pairing, Developer Mode, device support, selected Xcode, transport |
| `task_for_pid` / attach denied | Debugger authorization, target signing/entitlements, protected-process policy |
| Process exits when debugger is present | Application anti-debug checks, crash/termination logs, launch configuration |
| Injected library ignored or rejected | Platform slice, dependent libraries, hardened runtime, library validation, environment propagation |
| Install/signature validation fails | Bundle identifiers, nested code, profile, entitlements, certificate, expiration, device eligibility |

macOS debugging uses Mach task/exception mechanisms as well as process-control interfaces. Root alone does not override every protection, and `ptrace` is not the whole LLDB architecture. Diagnose the reported layer before proposing security changes.

## Inspect signatures without changing them

```sh
codesign -dvvv /path/to/App.app
codesign -d --entitlements - /path/to/App.app
codesign --verify --strict --verbose=4 /path/to/App.app
security cms -D -i /path/to/App.app/embedded.mobileprovision -o /tmp/debug-profile.plist
plutil -p /tmp/debug-profile.plist
```

For a macOS bundle, the embedded profile, when present, is normally `Contents/embedded.provisionprofile`. Inspect each relevant nested framework, extension, or helper separately. A certificate identity and a valid signature do not alone prove that an entitlement is authorized for that app/device.

Compare the signed entitlements to the profile's permitted values, application identifier, team, expiration, and device/distribution eligibility. A profile permits a set of entitlements; do not blindly copy its entire dictionary into an entitlements file. Modern profiles/signatures also contain DER representations, so historical XML-only assumptions are incomplete.

`CFBundleIdentifier` is the bundle ID, without an App ID prefix. `application-identifier` combines a prefix with that ID; the prefix is not always the Team ID. On macOS the standard entitlement is `com.apple.application-identifier`; Catalyst can include both forms. Device development profiles and macOS hardened runtime debugging have different entitlement names and rules: for example, `get-task-allow` versus `com.apple.security.get-task-allow` in their respective contexts.

For your app, prefer a development build signed through the project. If a specific experiment requires re-signing, work on a copy, preserve bundle structure, entitlements, and profiles, and sign nested code from the inside out. Extensions retain their own identifiers/profiles. `codesign --deep` is not a general repair strategy. An ad hoc signature does not grant device provisioning, trust, protected-process access, or decryption of an encrypted executable.

## Understand an own-app anti-debug check

`ptrace(PT_DENY_ATTACH, ...)` and inspecting `P_TRACED` through `sysctl` are different mechanisms. The former requests attach-denial behavior; the latter observes a process flag and lets application code decide what to do. Neither should be mistaken for the application's ordinary business failure.

With source, make the check configurable for your development build. Without a convenient rebuild, an own-app experiment can stop **before** the call:

```text
breakpoint set -n ptrace -K false
run
bt
disassemble -f
```

Inspect the request using the actual ABI and the platform's header definition of `PT_DENY_ATTACH`. Verify that the caller is the intended app/check, since not every `ptrace` call denies attach. For that specific call, `thread return 0` can simulate a successful no-op, then continuing tests whether this check caused the observed behavior. It does not undo a denial already executed, grant task rights, or fix signing. Record the changed control flow and relaunch without the experiment.

For a `sysctl`-based check, stop at the application's decision or inspect its returned data and branch. Prefer changing the test condition in the development build to installing a process-wide hook that falsifies unrelated queries.

## Recovery and scope

Do not turn an attach error into automatic SIP changes, arbitrary entitlement removal, or re-signing a user's installed app. Those are separate persistent experiments with a concrete target and restoration plan. Research involving protected system processes belongs on an explicitly selected disposable environment. Keep useful debugging knowledge in the skill while distinguishing it from authorization to alter the current machine.
