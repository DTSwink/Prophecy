// Project-owned extension to UE 5.7's build-tool adapter. No game/editor code.
using System;
using System.Runtime.InteropServices;
using System.Threading;

namespace EpicGames.UBA.Impl
{
    internal partial class SchedulerImpl
    {
        [StructLayout(LayoutKind.Sequential)]
        struct PhysicalMemoryStatus
        {
            public uint Length, Load;
            public ulong TotalPhysical, AvailablePhysical, TotalPageFile,
                AvailablePageFile, TotalVirtual, AvailableVirtual, Extended;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool GlobalMemoryStatusEx(ref PhysicalMemoryStatus status);

        [DllImport("UbaHost", CharSet = CharSet.Auto)]
        static extern void Scheduler_SetMaxLocalProcessors(nint scheduler, uint processors);

        Timer? _memoryLimitTimer;
        int _memoryCpuCeiling;
        int _lastMemoryLimit = -1;
        ulong _memoryPerCompiler = 1536UL * 1024 * 1024;

        void StartDynamicMemoryLimit(int startupLimit)
        {
            if (!OperatingSystem.IsWindows()) { return; }
            // Optional process-local budget, also used by the lightweight test.
            if (uint.TryParse(Environment.GetEnvironmentVariable("PROPHECY_BUILD_MEMORY_PER_ACTION_MB"), out uint megabytes)
                && megabytes >= 256 && megabytes <= 16384)
            {
                _memoryPerCompiler = (ulong)megabytes * 1024 * 1024;
            }
            // UBT's startupLimit may be its old one-time RAM result. Do not
            // retain that stale ceiling when memory becomes available later.
            _memoryCpuCeiling = Math.Max(1, Environment.ProcessorCount);
            if (int.TryParse(Environment.GetEnvironmentVariable("PROPHECY_BUILD_MAX_WORKERS"), out int explicitLimit)
                && explicitLimit > 0)
            {
                _memoryCpuCeiling = Math.Min(_memoryCpuCeiling, explicitLimit);
            }
            RefreshDynamicMemoryLimit(null);
            // Timers exist only during a build. The native scheduler keeps job
            // ordering/dependencies; lowering the cap doesn't kill active jobs.
            _memoryLimitTimer = new Timer(RefreshDynamicMemoryLimit, null, 500, 500);
        }

        void RefreshDynamicMemoryLimit(object? state)
        {
            PhysicalMemoryStatus memory = new() { Length = (uint)Marshal.SizeOf<PhysicalMemoryStatus>() };
            if (!GlobalMemoryStatusEx(ref memory)) { return; }
            // Preserve UBT's conservative 1.5 GiB/job budget, but resample it.
            // Existing compilers are included in system usage, never credited
            // back as spare memory. Commit headroom can impose a tighter cap.
            ulong available = Math.Min(memory.AvailablePhysical, memory.AvailablePageFile);
            int limit = Math.Max(1, Math.Min(_memoryCpuCeiling, (int)(available / _memoryPerCompiler)));
            if (limit == _lastMemoryLimit) { return; }
            Scheduler_SetMaxLocalProcessors(_schedulerHandle, (uint)limit);
            _lastMemoryLimit = limit;
            Console.WriteLine($"[Dynamic RAM] Worker ceiling {limit}/{_memoryCpuCeiling}; {available / (1024.0 * 1024 * 1024):F2} GiB free.");
        }

        void StopDynamicMemoryLimit()
        {
            Timer? timer = _memoryLimitTimer;
            if (timer == null) { return; }
            _memoryLimitTimer = null;
            using ManualResetEvent finished = new(false);
            if (timer.Dispose(finished)) { finished.WaitOne(); }
        }
    }
}
