"""Run an owned Windows diagnostic with a real process-commit limit.

The child starts suspended, joins a private job, then resumes. Closing the job
kills only this child and its descendants. No machine-wide settings are changed.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import time


class BasicLimit(C.Structure):
    _fields_ = [("ProcessTime", C.c_int64), ("JobTime", C.c_int64),
                ("Flags", W.DWORD), ("MinimumWorkingSet", C.c_size_t),
                ("MaximumWorkingSet", C.c_size_t), ("ActiveProcesses", W.DWORD),
                ("Affinity", C.c_size_t), ("Priority", W.DWORD), ("Scheduling", W.DWORD)]


class IO(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in
                ("ReadOperations", "WriteOperations", "OtherOperations",
                 "ReadBytes", "WriteBytes", "OtherBytes")]


class ExtendedLimit(C.Structure):
    _fields_ = [("Basic", BasicLimit), ("IO", IO),
                ("ProcessMemory", C.c_size_t), ("JobMemory", C.c_size_t),
                ("PeakProcessMemory", C.c_size_t), ("PeakJobMemory", C.c_size_t)]


class Memory(C.Structure):
    _fields_ = [("Size", W.DWORD), ("PageFaults", W.DWORD)] + [
        (name, C.c_size_t) for name in
        ("PeakWorkingSet", "WorkingSet", "PeakPagedPool", "PagedPool",
         "PeakNonpagedPool", "NonpagedPool", "Pagefile", "PeakPagefile", "Private")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-mib", type=int, default=384)
    parser.add_argument("--timeout", type=float, default=190)
    parser.add_argument("--log", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if os.name != "nt" or not command or args.memory_mib <= 0 or args.timeout <= 0:
        parser.error("Requires Windows, a command and positive limits")
    kernel = C.WinDLL("kernel32", use_last_error=True)
    ntdll = C.WinDLL("ntdll")
    signatures = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "K32GetProcessMemoryInfo": ([W.HANDLE, C.c_void_p, W.DWORD], W.BOOL),
    }
    for name, (inputs, output) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = inputs, output
    ntdll.NtResumeProcess.argtypes, ntdll.NtResumeProcess.restype = [W.HANDLE], C.c_long
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise C.WinError(C.get_last_error())
    process = None
    receipt = {"command": command, "processCommittedMemoryLimitBytes": args.memory_mib * 1024**2,
               "timeoutSeconds": args.timeout, "assignedBeforeResume": False}
    started = time.monotonic()
    try:
        limit = ExtendedLimit()
        limit.Basic.Flags = 0x100 | 0x2000  # PROCESS_MEMORY | KILL_ON_JOB_CLOSE
        limit.ProcessMemory = receipt["processCommittedMemoryLimitBytes"]
        if not kernel.SetInformationJobObject(job, 9, C.byref(limit), C.sizeof(limit)):
            raise C.WinError(C.get_last_error())
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        with open(args.log, "wb") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=0x4 | 0x08000000 | 0x4000)
            receipt["pid"] = process.pid
            if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                process.kill()
                raise C.WinError(C.get_last_error())
            receipt["assignedBeforeResume"] = True
            status = ntdll.NtResumeProcess(int(process._handle))
            if status < 0:
                raise RuntimeError("NtResumeProcess failed: " + hex(status & 0xffffffff))
            try:
                receipt["exitCode"] = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                receipt["timedOut"] = True
                kernel.TerminateJobObject(job, 124)
                receipt["exitCode"] = process.wait(timeout=10)
        actual = ExtendedLimit()
        if not kernel.QueryInformationJobObject(job, 9, C.byref(actual), C.sizeof(actual), None):
            raise C.WinError(C.get_last_error())
        receipt["jobLimitFlags"] = actual.Basic.Flags
        receipt["peakCommittedBytes"] = actual.PeakProcessMemory
        memory = Memory()
        memory.Size = C.sizeof(memory)
        if kernel.K32GetProcessMemoryInfo(int(process._handle), C.byref(memory), C.sizeof(memory)):
            receipt["peakWorkingSetBytes"] = memory.PeakWorkingSet
        receipt["passed"] = receipt["exitCode"] == 0 and not receipt.get("timedOut", False)
    finally:
        if process is not None and process.poll() is None:
            kernel.TerminateJobObject(job, 125)
            process.wait(timeout=10)
        kernel.CloseHandle(job)
        receipt["wallSeconds"] = time.monotonic() - started
        Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.receipt).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt))
    return 0 if receipt.get("passed", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
