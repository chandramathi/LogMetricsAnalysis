import java.io.*;
import java.time.*;
import java.time.format.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * TestApp.java
 * ------------
 * A simulated Java application that intentionally produces:
 *   - INFO logs (execution states)
 *   - WARN logs (slow queries, retries)
 *   - ERROR logs (NullPointerException, DB failures, OOM)
 *
 * Logs are written to: logs/app.log
 *
 * Run: javac TestApp.java && java TestApp
 */
public class TestApp {

    static final String LOG_FILE = "logs/app.log";
    static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS");
    static PrintWriter logWriter;
    static Random rand = new Random();

    // -------------------------------------------------------
    // PART 1: Logger utility
    // -------------------------------------------------------
    static void log(String level, String module, String message) {
        String line = String.format("[%s] [%s] [%s] %s",
            LocalDateTime.now().format(FMT), level, module, message);
        System.out.println(line);
        logWriter.println(line);
        logWriter.flush();
    }

    static void logError(String module, String message, Exception e) {
        log("ERROR", module, message + " | Exception: " + e.getClass().getSimpleName()
            + ": " + e.getMessage());
        // Write stack trace to log
        StringWriter sw = new StringWriter();
        e.printStackTrace(new PrintWriter(sw));
        logWriter.println("    STACKTRACE: " + sw.toString().replace("\n", "\n    "));
        logWriter.flush();
    }

    // -------------------------------------------------------
    // PART 2: Simulated Database module
    // -------------------------------------------------------
    static class DatabaseModule {

        static int queryCount = 0;

        static String query(String sql) throws Exception {
            queryCount++;
            int delay = rand.nextInt(500);
            Thread.sleep(delay);

            // Simulate slow query warning
            if (delay > 300) {
                log("WARN", "DatabaseModule", "Slow query detected (" + delay + "ms): " + sql);
            }

            // Simulate random DB failures
            if (rand.nextInt(10) == 0) {
                throw new RuntimeException("Connection timeout to DB after 3 retries");
            }

            // Simulate null result
            if (rand.nextInt(8) == 0) {
                return null;
            }

            log("INFO", "DatabaseModule", "Query OK (" + delay + "ms) [query #" + queryCount + "]: " + sql);
            return "ResultSet[rows=" + rand.nextInt(100) + "]";
        }
    }

    // -------------------------------------------------------
    // PART 3: Simulated Payment processing module
    // -------------------------------------------------------
    static class PaymentModule {

        static void processPayment(String userId, double amount) {
            log("INFO", "PaymentModule", "START processPayment user=" + userId + " amount=" + amount);

            try {
                String result = DatabaseModule.query("SELECT balance FROM accounts WHERE user='" + userId + "'");

                // NullPointerException simulation
                if (result == null) {
                    throw new NullPointerException("Account balance result was null for user: " + userId);
                }

                // Simulate business logic
                if (amount > 10000) {
                    log("WARN", "PaymentModule", "High-value transaction flagged for review: $" + amount);
                }

                log("INFO", "PaymentModule", "Payment authorized for user=" + userId + " amount=$" + amount);

            } catch (NullPointerException e) {
                logError("PaymentModule", "Null account data during payment processing", e);
            } catch (Exception e) {
                logError("PaymentModule", "Payment failed for user=" + userId, e);
            }

            log("INFO", "PaymentModule", "END processPayment user=" + userId);
        }
    }

    // -------------------------------------------------------
    // PART 4: Simulated Cache module with memory pressure
    // -------------------------------------------------------
    static class CacheModule {

        static List<byte[]> cache = new ArrayList<>();
        static int hitCount = 0;
        static int missCount = 0;

        static String get(String key) {
            if (rand.nextInt(3) == 0) {
                hitCount++;
                log("INFO", "CacheModule", "Cache HIT for key=" + key
                    + " [hits=" + hitCount + " misses=" + missCount + "]");
                return "cached-value-" + key;
            } else {
                missCount++;
                log("WARN", "CacheModule", "Cache MISS for key=" + key
                    + " [hits=" + hitCount + " misses=" + missCount + "]");

                // Simulate memory allocation (causes GC pressure)
                if (cache.size() < 50) {
                    cache.add(new byte[1024 * 512]); // 512 KB allocation
                }
                return null;
            }
        }
    }

    // -------------------------------------------------------
    // PART 5: Main execution loop
    // -------------------------------------------------------
    public static void main(String[] args) throws Exception {

        // Setup log directory
        new File("logs").mkdirs();
        logWriter = new PrintWriter(new FileWriter(LOG_FILE, true));

        log("INFO", "Main", "=== Application START ===");
        log("INFO", "Main", "JVM: " + System.getProperty("java.version")
            + " | Heap: " + (Runtime.getRuntime().maxMemory() / 1024 / 1024) + "MB");

        String[] users = {"user_001", "user_002", "user_003", "user_404", "user_999"};

        // Run simulation for ~30 seconds
        long endTime = System.currentTimeMillis() + 30_000;

        while (System.currentTimeMillis() < endTime) {

            String user = users[rand.nextInt(users.length)];
            double amount = rand.nextDouble() * 15000;

            // Simulate a request pipeline
            log("INFO", "Main", "--- New request: user=" + user + " ---");

            // 1. Check cache first
            CacheModule.get("session:" + user);

            // 2. Process payment
            PaymentModule.processPayment(user, amount);

            // 3. Simulate occasional unhandled state
            if (rand.nextInt(15) == 0) {
                log("ERROR", "Main", "Unhandled state reached! System may be in inconsistent state.");
            }

            Thread.sleep(500 + rand.nextInt(1000));
        }

        log("INFO", "Main", "=== Application SHUTDOWN ===");
        logWriter.close();
    }
}
