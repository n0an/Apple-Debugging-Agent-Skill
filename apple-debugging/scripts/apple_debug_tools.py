"""Small, session-local LLDB inspection commands. No third-party dependencies."""

import argparse
import re
import shlex
import struct

import lldb


class ParseError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ParseError(message)


def arguments(command, result, configure):
    parser = Parser(add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    configure(parser)
    tokens = shlex.split(command)
    if "-h" in tokens or "--help" in tokens:
        result.AppendMessage(parser.format_help())
        return None
    return parser.parse_args(tokens)


def target_for(exe_ctx):
    target = exe_ctx.GetTarget()
    if not target.IsValid():
        raise ValueError("Select a target first.")
    return target


def stopped_process(exe_ctx):
    process = exe_ctx.GetProcess()
    if not process.IsValid() or process.GetState() != lldb.eStateStopped:
        raise ValueError("This command requires a stopped live process.")
    return process


def path_of(file_spec):
    directory = file_spec.GetDirectory() or ""
    name = file_spec.GetFilename() or ""
    return directory.rstrip("/") + "/" + name if directory else name


def location(target, address):
    resolved = target.ResolveLoadAddress(address)
    module = resolved.GetModule()
    function = resolved.GetFunction()
    symbol = resolved.GetSymbol()
    name = function.GetName() if function.IsValid() else symbol.GetName()
    return "{}: {}".format(path_of(module.GetFileSpec()), name or "<unresolved>")


def lookup(debugger, command, exe_ctx, result, internal_dict):
    """adb-lookup [--module PATH_SUBSTRING] [--limit N] REGEX; no target execution."""
    try:
        def configure(parser):
            parser.add_argument("--module", default="")
            parser.add_argument("--limit", type=int, default=50)
            parser.add_argument("pattern")
        args = arguments(command, result, configure)
        if args is None:
            return
        if not 1 <= args.limit <= 1000:
            raise ValueError("--limit must be between 1 and 1000.")
        pattern = re.compile(args.pattern)
        target = target_for(exe_ctx)
        count = 0
        for index in range(target.GetNumModules()):
            module = target.GetModuleAtIndex(index)
            path = path_of(module.GetFileSpec())
            if args.module not in path:
                continue
            heading = False
            for symbol_index in range(module.GetNumSymbols()):
                symbol = module.GetSymbolAtIndex(symbol_index)
                name = symbol.GetDisplayName() or symbol.GetName() or ""
                if not pattern.search(name):
                    continue
                if count == args.limit:
                    result.AppendMessage("Result limit reached; narrow the regex or module.")
                    return
                if not heading:
                    result.AppendMessage("{} [UUID {}]".format(path, module.GetUUIDString()))
                    heading = True
                address = symbol.GetStartAddress()
                load = address.GetLoadAddress(target)
                label = "load"
                if load == lldb.LLDB_INVALID_ADDRESS:
                    load = address.GetFileAddress()
                    label = "file"
                rendered = "<no address>" if load == lldb.LLDB_INVALID_ADDRESS else hex(load)
                result.AppendMessage("  {} {} {}".format(label, rendered, name))
                count += 1
        result.AppendMessage("{} symbol(s).".format(count))
    except (ValueError, re.error) as error:
        result.SetError(str(error))


def block(debugger, command, exe_ctx, result, internal_dict):
    """adb-block ADDRESS; read a known 64-bit block prefix without running target code."""
    try:
        def configure(parser):
            parser.add_argument("address", type=lambda value: int(value, 0))
        args = arguments(command, result, configure)
        if args is None:
            return
        target = target_for(exe_ctx)
        process = stopped_process(exe_ctx)
        if target.GetAddressByteSize() != 8:
            raise ValueError("This layout supports 64-bit pointers only.")
        if not 0 < args.address <= (1 << 64) - 32:
            raise ValueError("Address is outside the supported range.")
        order = target.GetByteOrder()
        if order not in (lldb.eByteOrderLittle, lldb.eByteOrderBig):
            raise ValueError("Unknown target byte order.")
        error = lldb.SBError()
        data = process.ReadMemory(args.address, 32, error)
        if error.Fail() or len(data) != 32:
            raise ValueError("Cannot read block prefix: {}".format(error))
        prefix = "<" if order == lldb.eByteOrderLittle else ">"
        isa, flags, reserved, invoke, descriptor = struct.unpack(prefix + "QIIQQ", data)
        result.AppendMessage("isa={} flags={:#x} reserved={} invoke={} descriptor={}".format(
            hex(isa), flags, reserved, hex(invoke), hex(descriptor)))
        result.AppendMessage("invoke: " + location(target, invoke))
        result.AppendMessage("Layout only; this does not validate object lifetime or pointer authentication.")
    except ValueError as error:
        result.SetError(str(error))


def array_string(value):
    error = lldb.SBError()
    data = value.GetData().ReadRawData(error, 0, value.GetByteSize())
    if error.Fail():
        raise ValueError("Cannot read method metadata: {}".format(error))
    return data.split(b"\0", 1)[0].decode("utf-8", errors="replace")


def methods(debugger, command, exe_ctx, result, internal_dict):
    """adb-methods [--class-methods] CLASS; executes a bounded Objective-C runtime query."""
    try:
        def configure(parser):
            parser.add_argument("--class-methods", action="store_true")
            parser.add_argument("class_name")
        args = arguments(command, result, configure)
        if args is None:
            return
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_.$]*", args.class_name):
            raise ValueError("Expected a simple runtime class name, not an expression.")
        target = target_for(exe_ctx)
        stopped_process(exe_ctx)
        frame = exe_ctx.GetFrame()
        if not frame.IsValid():
            raise ValueError("Select a frame first.")
        options = lldb.SBExpressionOptions()
        options.SetLanguage(lldb.eLanguageTypeObjC_plus_plus)
        options.SetTimeoutInMicroSeconds(2000000)
        options.SetUnwindOnError(True)
        options.SetIgnoreBreakpoints(True)
        expression = r'''@import Foundation; @import ObjectiveC;
        ({
            struct Row { unsigned long long imp; char name[128]; char types[96]; };
            struct Rows { unsigned int found, count, stored; Row items[128]; };
            Rows output = {};
            Class cls = objc_getClass("CLASS_NAME");
            output.found = cls != Nil;
            if (cls) {
                if (CLASS_METHODS) cls = object_getClass((id)cls);
                Method *list = class_copyMethodList(cls, &output.count);
                output.stored = output.count < 128 ? output.count : 128;
                for (unsigned int i = 0; i < output.stored; ++i) {
                    output.items[i].imp = (unsigned long long)method_getImplementation(list[i]);
                    snprintf(output.items[i].name, sizeof(output.items[i].name), "%s", sel_getName(method_getName(list[i])));
                    snprintf(output.items[i].types, sizeof(output.items[i].types), "%s", method_getTypeEncoding(list[i]));
                }
                free(list);
            }
            output;
        })'''.replace("CLASS_METHODS", "1" if args.class_methods else "0").replace("CLASS_NAME", args.class_name)
        value = frame.EvaluateExpression(expression, options)
        if not value.IsValid() or value.GetError().Fail():
            raise ValueError("Runtime query failed: {}".format(value.GetError()))
        if not value.GetChildMemberWithName("found").GetValueAsUnsigned():
            raise ValueError("Runtime class not found: " + args.class_name)
        count = value.GetChildMemberWithName("count").GetValueAsUnsigned()
        stored = value.GetChildMemberWithName("stored").GetValueAsUnsigned()
        if stored > 128:
            raise ValueError("Invalid runtime query result.")
        items = value.GetChildMemberWithName("items")
        prefix = "+" if args.class_methods else "-"
        for index in range(stored):
            row = items.GetChildAtIndex(index)
            address = row.GetChildMemberWithName("imp").GetValueAsUnsigned()
            name = array_string(row.GetChildMemberWithName("name"))
            encoding = array_string(row.GetChildMemberWithName("types"))
            result.AppendMessage("{}[{} {}] {} {}".format(prefix, args.class_name, name, hex(address), encoding))
            result.AppendMessage("  " + location(target, address))
        result.AppendMessage("{}/{} methods declared on this class; inherited methods excluded.".format(stored, count))
        result.AppendMessage("Names/type encodings are bounded to 127/95 bytes; long fields may be truncated.")
    except ValueError as error:
        result.SetError(str(error))


def __lldb_init_module(debugger, internal_dict):
    for name, function in (("adb-lookup", "lookup"), ("adb-block", "block"), ("adb-methods", "methods")):
        debugger.HandleCommand("command script add -o -f {}.{} {}".format(__name__, function, name))
