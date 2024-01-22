package edu.gmu.swe.flaky.sleepy.intercept;

import java.io.*;
import java.lang.instrument.UnmodifiableClassException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ForkJoinTask;
import java.util.concurrent.ForkJoinWorkerThread;
import java.util.concurrent.FutureTask;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;


public class Wrapper {

    static class WrapperPair<E, V> {
        E first;
        V second;

        WrapperPair(E first, V second) {
            WrapperPair.this.first = first;
            WrapperPair.this.second = second;
        }
    }

    public static long maxSleepTimeMS = -1;

    // Boolean to enable sleeping, we use this to not sleep right from the beginning but only when the
    // @Before or @Test method is run. FIXME, maybe this could be done better?
    public static volatile boolean SLEEP_THREADS = false;

    // The target lines to sleep at during execution/
    public static Set<String> linesToSleepDuringRun = null;

    // Maps line to number of nonzero sleeps
    final static Map<String, AtomicInteger> lineToSleeps = new ConcurrentHashMap<>();

    // Maps cause to interception to sleepcount (nonzero sleep) and time slept
    final static Map<String, Map<String, WrapperPair<Integer, Long>>>
            causeToInerceptionSleepCountNapTimeTotal = new ConcurrentHashMap<>();

    // thread reference to our custom thread identifier, see trackThread()
    final static Map<Object, String> threadToID = new WeakHashMap<>();

    // Map for getting the next count for how a thread has been created, useful for loops that make threads.
    final static Map<String, Integer> stackTraceToNextNonce = new ConcurrentHashMap<>();


    // Target thread ID to give a nap to.
    public static String threadIdToSlow = null;
    final static String NO_SLEEP = "0";

    // Record sleeps, we use this to keep track of threads have slept and where.
    static PrintWriter sleepRecorder;
    static Set<String> recordedSleeps = new HashSet<>();

    static PrintWriter shaToStackTraceWriter;

    static PrintWriter causeToInterceptionWriter;

    private static AtomicBoolean isInit = new AtomicBoolean(false);

    /**
     * Initialize various values must be called before other code is executed for class to work properly.
     **/
    public static void init(String threadIdToSlow, long maxSleepTimeMS) {
        Wrapper.maxSleepTimeMS = maxSleepTimeMS;
        // Set the thread to be napped.
        Wrapper.threadIdToSlow = threadIdToSlow;
        // Add the main thread as a special case.
        String mainThread = "<main>";
        threadToID.put(Thread.currentThread(), mainThread);

        try {
            // Retransform the thread class to start recording threads.
            if (!SleepyInterceptingAgent.inst.isRetransformClassesSupported()) {
                throw new RuntimeException();
            }
            SleepyInterceptingAgent.inst.retransformClasses(Thread.class);
            //SleepyInterceptingAgent.inst.retransformClasses(ForkJoinWorkerThread.class);
            SleepyInterceptingAgent.inst.retransformClasses(ForkJoinTask.class);
            SleepyInterceptingAgent.inst.retransformClasses(FutureTask.class);
        } catch (UnmodifiableClassException e) {
            e.printStackTrace();
        }

        try {
            // File for keeping track of who was slept and where so we can do bisection to find minimum sleep lines.
            File sleepRecordingFile = new File("sleepy-records/internal/sleepCalls." + threadIdToSlow);
            sleepRecorder = new PrintWriter(new FileOutputStream(sleepRecordingFile), true);

            File shaStackTraceMap = new File("sleepy-records/internal/shaToStackTrace.csv");
            shaToStackTraceWriter = new PrintWriter(new FileOutputStream(shaStackTraceMap, true), true);
            shaToStackTraceWriter.println(String.format("\"%s\",\"%s\"", mainThread, mainThread));
            File causeToLineCsv = new File("sleepy-records/internal/causeToInterception.csv");
            causeToInterceptionWriter = new PrintWriter(new FileOutputStream(causeToLineCsv), true);

            isInit.set(true);
        } catch (Exception e) {
            e.printStackTrace();
            throw new RuntimeException();
        }
    }

    /**
     * Used to keep track of threads. We use the following thread identification scheme.
     * 1) Get the stacktrace of the thread creating the new thread.
     * 2) Get the number of times a thread has been created in this way, as according to the trace.
     * 3) Hash the stacktrace and count as a pair, this is our identifier.
     *
     * @param thisThread this reference passed when this method is called by the ctor of a Thread.
     */
    public static int NONCE_RANGE = 5; // Change this to have higher precision of thread identification in job creating loops.

    public synchronized static void trackThread(Object thisThread) {
        StringBuilder idBuilder = new StringBuilder();
        for (StackTraceElement stackTraceElement : Thread.currentThread().getStackTrace()) {
            if (stackTraceElement.getClassName().startsWith("edu.gmu.swe.flaky")) {
                continue;
            }
            idBuilder.append(stackTraceElement);
            idBuilder.append(" ");
        }
        idBuilder.deleteCharAt(idBuilder.length() - 1); // Remove last newline.

        String trace = idBuilder.toString();
        stackTraceToNextNonce.putIfAbsent(trace, 0);
        int nonce = stackTraceToNextNonce.get(trace);
        int nextNonce = (nonce + 1) % NONCE_RANGE;
        stackTraceToNextNonce.put(trace, nextNonce);
        String threadKey;
        threadKey = String.format("<%d,%d>", trace.hashCode(), nextNonce);
//        if (thisThread instanceof ForkJoinTask<?>) {
//            // Because there can be a huge amount of ForkJoinTasks we don't use a counter to unique identify them.
//            // Specifically this can be seen in Orbit like in com.ea.orbit.actors.test.StatelessActorTest#statelessTest
//            threadKey = String.format("<%d,%s>", trace.hashCode(), "ForkJoinTask");
//            stackTraceToNextNonce.putIfAbsent(trace, 0);
//            int count = stackTraceToNextNonce.get(trace) + 1;
//            stackTraceToNextNonce.put(trace, count);
//            FlakyLogger.info(String.format("Counted ForkJoinTask:%d", count));
//        }
//        else {
//            stackTraceToNextNonce.putIfAbsent(trace, 0);
//            threadKey = String.format("<%d,%d>", trace.hashCode(), stackTraceToNextNonce.get(trace));
//            stackTraceToNextNonce.put(trace, 1 + stackTraceToNextNonce.get(trace));
//        }
        threadToID.put(thisThread, threadKey);
        FlakyLogger.debug(String.format("Associating %s with %s", trace + ' ' + nextNonce, threadKey));

        // Append to internal map of SHA => stacktrace
        shaToStackTraceWriter.println(String.format("\"%s\",\"%s\"", threadKey, trace));
    }

    public static Map<Thread, ForkJoinTask<?>> threadToForkJoinTask = new WeakHashMap<>();

    public synchronized static void mapThreadToForkJoinTask(ForkJoinTask<?> task) {
        Thread thread = Thread.currentThread();
        FlakyLogger.debug("Mapping " + threadToID.get(thread) + " to " + threadToID.get(task));
        threadToForkJoinTask.put(thread, task);
    }

    /***
     * Called when by instrumented test case so that we are only sleeping once a test method begins.
     * This way we avoid lots of unnecessary sleeps.
     */
    public static void setSleep() {
        SLEEP_THREADS = true;
    }

    public static boolean threadShouldBeSlept(String specialTid) {
        if (specialTid == null) {
            return false;
        }
        return SLEEP_THREADS && specialTid.equals(threadIdToSlow);
    }

    public static String getSpecialTID(Thread thread) {
        if (threadToForkJoinTask.containsKey(thread)) {
            ForkJoinTask<?> task = threadToForkJoinTask.get(thread);
            return threadToID.get(task);
        }
        return threadToID.get(thread);
    }

    /**
     * Workhorse method that potential points of thread contention call into for a little nap.
     *
     * @param className
     * @param methodName
     * @param line
     */
    public static void extraSleep(String cause, String className, String methodName, int line) {
        if (!isInit.get()) {
            return;
        }

        Thread currentThread = Thread.currentThread();
        String specialTID = getSpecialTID(currentThread);
        boolean sleeping = false;

        String interception = String.format("%s:%s:%d", className, methodName, line);
        FlakyLogger.debug(String.format("Intercepted %s because of %s", interception, cause));

        if (threadShouldBeSlept(specialTID)) {
            if (linesToSleepDuringRun == null ||
                    linesToSleepDuringRun.contains(String.format("%s:%s:%d", className, methodName, line))) {

                sleeping = true;
                // FIXME racecondition here with a failing test. Currently hackily fixed by always flushing.
                String record = String.format("%s:%s:%s:%s:%s", sleeping, specialTID, className, methodName, line);
                if (!recordedSleeps.contains(record) && NO_SLEEP.equals(threadIdToSlow)) {
                    recordedSleeps.add(record);
                    sleepRecorder.println(record);
                    FlakyLogger.debug(String.format("%s caused sleep at %s", cause, record));
                }
                napTime(cause, interception);
            } else {
                String msg = String.format("Skipping Thread: " + specialTID + " %s:%s:%s", className, methodName, line);
                FlakyLogger.debug(msg);
            }
        } else {
            String msg = String.format("Skipping Thread: " + specialTID + " %s:%s:%s", className, methodName, line);
            FlakyLogger.debug(msg);
        }
        String record = String.format("%s:%s:%s:%s:%s", sleeping, specialTID, className, methodName, line);
        if (!recordedSleeps.contains(record) && NO_SLEEP.equals(threadIdToSlow)) {
            // Only report the line we hit once to avoid taking too much space.
            recordedSleeps.add(record);
            sleepRecorder.println(record);
            FlakyLogger.debug(String.format("%s caused sleep at %s", cause, record));
        }
    }

    /**
     * Just an extra helper where the actual sleeping happens.
     */
    private static void napTime(String cause, String interception) {
        long amt = maxSleepTimeMS;
        try {
            synchronized (lineToSleeps) {
                lineToSleeps.putIfAbsent(interception, new AtomicInteger(0));
                amt = (long) Math.floor(amt * Math.pow(0.5, lineToSleeps.get(interception).get())); // Cut down on nap length by 1/2 each time.

                if (amt > 0) {
                    causeToInerceptionSleepCountNapTimeTotal.putIfAbsent(cause, new HashMap<>());
                    causeToInerceptionSleepCountNapTimeTotal.get(cause)
                            .putIfAbsent(interception, new WrapperPair<Integer, Long>(0,0L));
                    WrapperPair<Integer, Long> prevPair = causeToInerceptionSleepCountNapTimeTotal.get(cause).get(interception);
                    prevPair.first += 1;
                    prevPair.second += amt;

                    lineToSleeps.get(interception).getAndIncrement();
                }
            }

            FlakyLogger.debug("Sleeping at " + String.format("%s because of %s for %d ms", interception, cause, amt));
            FlakyLogger.debug("Sleeping thread: " + threadIdToSlow + " for " + amt + " milliseconds.");
            // Every time we sleep we may cause some kind of weird failure like OOM so write the report immediately.
            // Although the IO is a bit slow, it's nothing compared to our sleeps.
            writeCauseInterceptionSleepReport();
            Thread.sleep(amt);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    public synchronized static void writeCauseInterceptionSleepReport() {
        // Should only be called by the thread being slept, but synchronized just in case.
        for (String cause : causeToInerceptionSleepCountNapTimeTotal.keySet()) {
            for (String interception : causeToInerceptionSleepCountNapTimeTotal.get(cause).keySet()) {
                WrapperPair<Integer, Long> sleepCountTimePair = causeToInerceptionSleepCountNapTimeTotal.get(cause).get(interception);
                String row = String.format("%s,%s,%d,%d", cause, interception, sleepCountTimePair.first, sleepCountTimePair.second);
                causeToInterceptionWriter.println(row);
            }
        }
    }
}
