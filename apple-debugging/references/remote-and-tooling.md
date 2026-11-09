# Remote debugging and debugger integrations

Use when the debugger frontend, process, or recorded state lives outside the ordinary Xcode launch session. First identify the selected Xcode/LLVM build and inspect available commands. Upstream LLDB documentation can describe features absent from an older Apple build.

## Remote sessions

Apple platforms commonly use `debugserver` as the process-side GDB-remote stub. A platform connection supplies services such as process/file management; a process connection controls a particular debuggee. Do not treat those as interchangeable ports or install a Linux `lldb-server` workflow onto an iPhone.

For an accessible own macOS lab target, start the matching debugserver on a loopback endpoint following its local `--help`, then connect from LLDB with `gdb-remote HOST:PORT`. For another host, use an authenticated transport such as an SSH tunnel and keep the debugger endpoint off public interfaces. Set the target binary before connecting when possible and verify architecture, UUIDs, loaded modules, and stop state afterward.

For a platform server that actually supports the selected protocol:

```text
platform list
platform select remote-macosx
platform connect connect://HOST:PORT
platform status
```

These commands do not start the server or grant target rights. For physical Apple devices, prefer Xcode's supported pairing, Developer Mode, device services, and matching toolchain. A generic TCP recipe does not replace those requirements. Diagnose transport errors separately from signing/attach denials.

Map remote source paths with `settings set target.source-map /build/root /local/root`; load matching dSYMs with `target symbols add`. Keep remote executable paths, local symbol paths, and process load addresses distinct. On completion, verify whether detach resumes the remote process and close the owned server/tunnel without disturbing another session.

## LLDB DAP

`lldb-dap` translates Debug Adapter Protocol requests from an editor into LLDB operations. Discover the executable with `xcrun --find lldb-dap` or the selected toolchain; old installations may use `lldb-vscode`. The frontend extension's adapter type name must match its configuration.

An editor configured for `lldb-dap` can start with:

```json
{
  "name": "Debug local probe",
  "type": "lldb-dap",
  "request": "launch",
  "program": "/absolute/path/probe",
  "cwd": "/absolute/path/lab",
  "args": []
}
```

Treat the adapter, LLDB library, Swift support, architecture, and target SDK as one compatible toolchain. A generic upstream adapter may not match Xcode's Swift debugger. Verify breakpoints and variables before moving an existing project workflow. Launch/attach commands and initialization settings can execute code; review the concrete configuration and keep it local to the task.

## LLDB MCP

Check `help protocol-server` and whether `lldb-mcp` is installed. Current upstream LLDB documents a standalone stdio `lldb-mcp` service with `session_create`, `sessions_list`, `command`, and `session_close` tools. Session IDs are debugger URIs; use the returned URI rather than assuming a singleton session.

An interactive session can expose its MCP protocol server with:

```text
protocol-server start MCP
protocol-server get MCP
protocol-server stop MCP
```

Start it only when the integration is needed, retain the returned endpoint, and stop the owned server afterward. Upstream discovery uses a local registry; sessions started after `lldb-mcp` discovery may require reconnecting the client. A visible session is not permission to mutate an unrelated debuggee. `session_close` applies to sessions created by the standalone service, not every discovered interactive debugger.

Standalone sessions can run asynchronously, so a returned `continue` response does not prove the target stopped again. Inspect process state and use bounded waits. Debuggee stdout may need explicit redirection. Do not globally force synchronous mode in a user's existing session to simplify an integration. Terminal commands remain a fallback when the installed debugger lacks MCP.

This integration is version-sensitive; command help availability alone is not an end-to-end MCP test.

## Custom breakpoint resolvers

A resolver discovers locations as modules are loaded; a breakpoint callback decides what to do after a location is hit. Use the former when symbols need a custom matching rule, and the latter for a stop condition/action.

A resolver class receives `SBBreakpoint` and `SBStructuredData`, defines `__get_depth__`, and handles `__callback__(sym_ctx)`. Search only the supplied context and add addresses with `SBBreakpoint.AddLocation`, checking its error. Keep target-side evaluation out of module-discovery callbacks. LLDB manages duplicate locations and module reloads.

```text
command script import /absolute/path/resolvers.py
breakpoint set -P resolvers.ProbeResolver -s MyProbe -k prefix -v diagnostic_
breakpoint list
```

The Python class must exist before this command runs. Use `-s`/`-f` to constrain the built-in search filter. Inspect `SBStructuredData` types instead of assuming every argument is a string. Test initial resolution, a later dylib load, and a reload before relying on the resolver for automation.

## Scripted processes, threads, and stepping

These solve different problems:

| Extension | Use |
|---|---|
| Scripted process | Present memory regions, modules, stop state, and control from a custom backend or recorded data |
| Scripted thread | Supply register context, frames, and stop reasons for a thread in that process |
| Scripted thread plan | Compose stepping operations in an existing process |

Inspect the installed base classes with `script import lldb.plugins.scripted_process as p; print(p.__file__)`. Implement the abstract contracts from that toolchain. A recorded-memory backend must report unavailable memory/registers and reject unsupported execution; it cannot honestly evaluate arbitrary live expressions. Specify byte order, address size, architecture, and address mappings from the capture, not the host.

For multi-stage stepping, derive a plan that uses the supplied `SBThreadPlan`, explains its own stops, notices stale frames, and calls `SetPlanComplete` when done. Invoke it with `thread step-scripted -C module.PlanClass`. Preserve unexpected signals and user breakpoints. A callback that calls `StepOut` recursively or changes debugger-wide async mode is not a substitute for a thread plan.

