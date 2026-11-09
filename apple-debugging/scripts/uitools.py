"""UIKit layout helpers for a paused process: vmove nudges a view, fview filters a view tree.

Import for the current session:
    command script import /absolute/path/apple-debugging/scripts/uitools.py
Both commands run Objective-C expressions in the target. Select the main thread first.
"""

import argparse
import re
import shlex

import lldb


class ParseError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ParseError(self.format_usage().strip())


def objc(frame, text):
    options = lldb.SBExpressionOptions()
    options.SetLanguage(lldb.eLanguageTypeObjC_plus_plus)
    options.SetTimeoutInMicroSeconds(3000000)
    options.SetUnwindOnError(True)
    options.SetIgnoreBreakpoints(True)
    value = frame.EvaluateExpression(text, options)
    if not value.IsValid() or value.GetError().Fail():
        raise ValueError("expression failed: {}\n  {}".format(value.GetError(), text))
    return value


def selected_frame(exe_ctx):
    frame = exe_ctx.GetFrame()
    process = exe_ctx.GetProcess()
    if not process.IsValid() or process.GetState() != lldb.eStateStopped or not frame.IsValid():
        raise ValueError("Pause the process and select a frame first.")
    return frame


def vmove(debugger, command, exe_ctx, result, internal_dict):
    """vmove <dx> <dy> <view-expression>: move a view's center and redraw while paused."""
    try:
        parser = Parser(prog="vmove", add_help=False)
        parser.add_argument("dx", type=float)
        parser.add_argument("dy", type=float)
        parser.add_argument("view", nargs="+")
        args = parser.parse_args(shlex.split(command))
        frame = selected_frame(exe_ctx)
        view = " ".join(args.view)
        # One expression that returns a value: a void result reports as an error.
        moved = objc(frame, "@import UIKit; UIView *v = (UIView *)({}); CGPoint c = [v center]; "
                            "[v setCenter:CGPointMake(c.x + {}, c.y + {})]; [CATransaction flush]; "
                            "NSStringFromCGRect([v frame])".format(view, args.dx, args.dy))
        result.AppendMessage("moved by ({:g}, {:g}); frame is now {}".format(
            args.dx, args.dy, moved.GetObjectDescription()))
    except (ValueError, ParseError) as error:
        result.SetError(str(error))


def fview(debugger, command, exe_ctx, result, internal_dict):
    """fview [--root VIEW-EXPRESSION] <regex>: print views under root whose description matches.

    The root defaults to $window, the window you selected for the scene that shows the bug.
    Quote a root expression that contains spaces: fview --root '[$window rootViewController].view' Label"""
    try:
        parser = Parser(prog="fview", add_help=False)
        parser.add_argument("--root", default="$window")
        parser.add_argument("pattern")
        args = parser.parse_args(shlex.split(command))
        pattern = re.compile(args.pattern)
        frame = selected_frame(exe_ctx)
        try:
            tree = objc(frame, "@import UIKit; (NSString *)[(UIView *)({}) recursiveDescription]".format(args.root))
        except ValueError as error:
            if args.root == "$window":
                raise ValueError("Select the window first, for example: "
                                 "expression -l objc -- UIWindow *$window = (UIWindow *)0x...")
            raise error
        matches = [line.strip(" |") for line in (tree.GetObjectDescription() or "").splitlines()
                   if pattern.search(line)]
        for line in matches:
            result.AppendMessage(line)
        result.AppendMessage("{} matching view(s).".format(len(matches)))
    except (ValueError, ParseError, re.error) as error:
        result.SetError(str(error))


def __lldb_init_module(debugger, internal_dict):
    for name in ("vmove", "fview"):
        debugger.HandleCommand("command script add -o -f {}.{} {}".format(__name__, name, name))
