import java.io.*;
import java.lang.management.*;
import java.time.*;
import java.time.format.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * Profiler.java
 * -------------
 * A standalone profiler that attaches to the JVM's management APIs
 * and periodically writes system metrics to: logs/profiler.log
 *
 * Captures every N seconds:
 *   - Heap / Non-heap memory usage
 *   - GC collection counts & times (page read/write analogy)
 *   - Thread counts & deadlocks
 *   - CPU load
 *   - Class loading stats
 *
 * Think of this as your "OS-level page reads/writes/misses" for the JVM.
 *
 * Run alongside TestApp:
 *   Terminal 1: java TestApp
 *   Terminal 2: java Profiler
 *
 * Or integrate into TestApp by calling Profiler.start() in main().
 */
public class Profiler {

    // -------------------------------------------------------
    // CONFIGURATION
    // -------------------------------------------------------
    static final int SAMPLE_INTERVAL_SECONDS = 2;
    static final String PROFILER_LOG = "logs/profiler.log";
    static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");

    // JVM Management beans
    static final MemoryMXBean memoryBean = ManagementFactory.getMemoryMXBean();
    static final ThreadMXBean threadBean = ManagementFactory.getThreadMXBean();
    static final OperatingSystemMXBean osBean = ManagementFactory.getOperatingSystemMXBean();
    static final ClassLoadingMXBean classBean = ManagementFactory.getClassLoadingMXBean();
    static final List<GarbageCollectorMXBean> gcBeans = ManagementFactory.getGarbageCollectorMXBeans();
    static final List<MemoryPoolMXBean> memPoolBeans = ManagementFactory.getMemoryPoolMXBeans();

    // Track deltas between samples
    static Map<String, Long> lastGcCount = new HashMap<>();
    static Map<String, Long> lastGcTime = new HashMap<>();

    static PrintWriter writer;

    // -------------------------------------------------------
    // PART 1: Write a header/separator
    // -------------------------------------------------------
    static void writeLine(String line) {
        String stamped = "[" + LocalDateTime.now().format(FMT) + "] " + line;
        System.out.println(stamped);
        writer.println(stamped);
        writer.flush();
    }

    static void writeSeparator() {
        writer.println("-----------------------------------------------------------");
        writer.flush();
    }

    // -------------------------------------------------------
    // PART 2: Capture heap & non-heap memory
    // (Analogous to: total memory available, used, free)
    // -------------------------------------------------------
    static void captureMemory() {
        MemoryUsage heap = memoryBean.getHeapMemoryUsage();
        MemoryUsage nonHeap = memoryBean.getNonHeapMemoryUsage();

        writeLine(String.format("MEMORY | Heap Used: %dMB / %dMB (%.1f%%) | Committed: %dMB | Max: %dMB",
            heap.getUsed() / 1024 / 1024,
            heap.getCommitted() / 1024 / 1024,
            (double) heap.getUsed() / Math.max(heap.getMax(), 1) * 100,
            heap.getCommitted() / 1024 / 1024,
            heap.getMax() / 1024 / 1024));

        writeLine(String.format("MEMORY | NonHeap Used: %dMB | Committed: %dMB",
            nonHeap.getUsed() / 1024 / 1024,
            nonHeap.getCommitted() / 1024 / 1024));

        // Per memory pool (Eden, Survivor, Old Gen, Metaspace)
        for (MemoryPoolMXBean pool : memPoolBeans) {
            MemoryUsage u = pool.getUsage();
            if (u == null) continue;
            writeLine(String.format("MEMPOOL | %-25s Used: %6dKB | Max: %dMB",
                pool.getName(),
                u.getUsed() / 1024,
                u.getMax() < 0 ? -1 : u.getMax() / 1024 / 1024));
        }
    }

    // -------------------------------------------------------
    // PART 3: Capture GC stats
    // Analogous to: page reads (minor GC) and page writes/flushes (major GC)
    // GC pauses = "page miss" equivalent — forced stop-the-world
    // -------------------------------------------------------
    static void captureGC() {
        for (GarbageCollectorMXBean gc : gcBeans) {
            long count = gc.getCollectionCount();
            long time = gc.getCollectionTime();

            long prevCount = lastGcCount.getOrDefault(gc.getName(), 0L);
            long prevTime = lastGcTime.getOrDefault(gc.getName(), 0L);

            long deltaCount = count - prevCount;
            long deltaTime = time - prevTime;

            // Classify: minor GC = "page read pressure", major GC = "page write/eviction"
            String gcType = gc.getName().toLowerCase().contains("young") ||
                            gc.getName().toLowerCase().contains("minor") ||
                            gc.getName().toLowerCase().contains("g1 young") ? "MINOR_GC" : "MAJOR_GC";

            writeLine(String.format("GC | %-10s | %-30s | Total Collections: %d | Total Time: %dms | "
                + "Delta Collections: %d | Delta Time: %dms",
                gcType, gc.getName(), count, time, deltaCount, deltaTime));

            if (deltaTime > 100) {
                writeLine("GC_ALERT | High GC pause detected: " + deltaTime + "ms in last interval for " + gc.getName());
            }

            lastGcCount.put(gc.getName(), count);
            lastGcTime.put(gc.getName(), time);
        }
    }

    // -------------------------------------------------------
    // PART 4: Capture thread stats
    // Deadlocks = hard errors; high thread count = resource pressure
    // -------------------------------------------------------
    static void captureThreads() {
        int threadCount = threadBean.getThreadCount();
        int peakCount = threadBean.getPeakThreadCount();
        long totalStarted = threadBean.getTotalStartedThreadCount();
        int daemon = threadBean.getDaemonThreadCount();

        writeLine(String.format("THREADS | Active: %d | Peak: %d | Daemon: %d | Total Started: %d",
            threadCount, peakCount, daemon, totalStarted));

        // Check for deadlocks
        long[] deadlocked = threadBean.findDeadlockedThreads();
        if (deadlocked != null && deadlocked.length > 0) {
            writeLine("DEADLOCK_ALERT | " + deadlocked.length + " deadlocked threads detected! IDs: "
                + Arrays.toString(deadlocked));
        }
    }

    // -------------------------------------------------------
    // PART 5: Capture CPU & OS stats
    // -------------------------------------------------------
    static void captureCPU() {
        double cpuLoad = osBean.getSystemLoadAverage();
        int processors = osBean.getAvailableProcessors();

        writeLine(String.format("CPU | Available Processors: %d | System Load Average: %.2f",
            processors, cpuLoad));

        // If it's HotSpot JVM, we can get process CPU usage
        if (osBean instanceof com.sun.management.OperatingSystemMXBean) {
            com.sun.management.OperatingSystemMXBean hotspot =
                (com.sun.management.OperatingSystemMXBean) osBean;
            writeLine(String.format("CPU | Process CPU Usage: %.1f%% | System CPU Usage: %.1f%%",
                hotspot.getProcessCpuLoad() * 100,
                hotspot.getCpuLoad() * 100));
        }
    }

    // -------------------------------------------------------
    // PART 6: Capture class loading
    // (Analogous to: page faults when new code is loaded)
    // -------------------------------------------------------
    static void captureClassLoading() {
        writeLine(String.format("CLASSES | Loaded: %d | Total Loaded: %d | Unloaded: %d",
            classBean.getLoadedClassCount(),
            classBean.getTotalLoadedClassCount(),
            classBean.getUnloadedClassCount()));
    }

    // -------------------------------------------------------
    // PART 7: Main sampling loop
    // -------------------------------------------------------
    public static void main(String[] args) throws Exception {

        new File("logs").mkdirs();
        writer = new PrintWriter(new FileWriter(PROFILER_LOG, true));

        writeLine("=== PROFILER START | Sampling every " + SAMPLE_INTERVAL_SECONDS + "s ===");
        writeSeparator();

        ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();

        scheduler.scheduleAtFixedRate(() -> {
            try {
                writeSeparator();
                writeLine("SAMPLE_START");
                captureMemory();
                captureGC();
                captureThreads();
                captureCPU();
                captureClassLoading();
                writeLine("SAMPLE_END");
            } catch (Exception e) {
                writeLine("PROFILER_ERROR | " + e.getMessage());
            }
        }, 0, SAMPLE_INTERVAL_SECONDS, TimeUnit.SECONDS);

        // Run for 60 seconds then stop (adjust as needed)
        Thread.sleep(60_000);
        scheduler.shutdown();
        writeLine("=== PROFILER SHUTDOWN ===");
        writer.close();
    }
}
