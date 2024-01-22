package test.edu.gmu.edu;

import static org.junit.Assert.*;

import edu.gmu.swe.phosphor.maven.bar.Bar;
import org.junit.Assert;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.LinkedList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class EasySourceTest {

    volatile int sharedInt = 0;

    @Before
    public void tearDown() {
        sharedInt = 0;
    }

    private static void allocateMemory() {
        allocateMemory();
    }
    public void generateOOM() throws Exception {
        int iteratorValue = 20;
        System.out.println("\n=================> OOM test started..\n");
        for (int outerIterator = 1; outerIterator < 20; outerIterator++) {
            System.out.println("Iteration " + outerIterator + " Free Mem: " + Runtime.getRuntime().freeMemory());
            int loop1 = 2;
            int[] memoryFillIntVar = new int[iteratorValue];
            // feel memoryFillIntVar array in loop..
            do {
                memoryFillIntVar[loop1] = 0;
                loop1--;
            } while (loop1 > 0);
            iteratorValue = iteratorValue * 5;
            System.out.println("\nRequired Memory for next loop: " + iteratorValue);
            Thread.sleep(1000);
        }
    }

    @Test
    public void testSingleThreadedNoInterception() {
        System.out.println("Passed!");
    }

    @Test
    public void testOOMError() throws Exception {
        // This is an example of a failure we cannot log but does not fail every time.
        AtomicInteger atomicInteger = new AtomicInteger(0);
        Callable callable = new Callable() {
            @Override
            public Object call() throws Exception {
                atomicInteger.getAndIncrement();
                return null;
            }
        };
        FutureTask futureTask = new FutureTask(callable);
        Executor executor = Executors.newSingleThreadExecutor();
        executor.execute(futureTask);
        Thread.sleep(3000);
        if (atomicInteger.get() == 0) {
            generateOOM();
        }
    }

    @Test
    public void testMultipleFailuresForOneThread() {
        long maxTimeMS = 5 * 1000;
        long startTime = System.currentTimeMillis();
        System.out.println("Between startTime and endTime");
        long endTime = System.currentTimeMillis();
        long timeSpan = endTime - startTime;
        Assert.assertTrue(timeSpan < maxTimeMS);

        startTime = System.currentTimeMillis();
        System.out.println("Between startTime and endTime");
        endTime = System.currentTimeMillis();
        timeSpan = endTime - startTime;
        Assert.assertTrue(timeSpan < maxTimeMS);
    }

    @Test
    public void testMultipleThreadsWithSynchronized() throws InterruptedException {
        // Should result in showing that sleeping t1 and or t2 cause the same failures.
        // This test shows that depending on which thread reaches a sync primitive first, has an extra affect for sleeping in the function.
        // This is also a clear example of when our method does not find every possible failure.
        Thread t1 = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    Thread.sleep(0);
                    incrementSharedInt();
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        });
        Thread t2 = new Thread(this::otherIncrementSharedInt);
        t1.start();
        t2.start();
        Thread.sleep(5000);
        Assert.assertEquals(2, sharedInt);
        t1.join();
        t2.join();
    }
    private synchronized void incrementSharedInt() {
        sharedInt++;
    }
    private void otherIncrementSharedInt() {
        synchronized (this) {
            sharedInt++;
        }
    }

    @Test
    public void sleepsBeginOfRunThreadMethods() throws InterruptedException {
        // NOTE to test this check that we're sleeping in the run methods of Thread and ForkJoinWorkerThread
        // Our tool should make this fail with both types of threads.
        Thread thread = new Thread(() -> sharedInt++);
        thread.start();
        ForkJoinPool pool = new ForkJoinPool(5);
        pool.execute(() -> {System.out.println(Thread.currentThread());
            try {
                // Need to do this to force the ForkJoinPool to make new worker thread.
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        });
        pool.execute(() -> sharedInt++);
        pool.execute(() -> sharedInt++);

        System.out.println("Started all threads");
        Thread.sleep(5000);
        Assert.assertEquals(3, sharedInt);
    }

    @Test
    public void failsStablyWithNonAsciiException() {
        String message = "❤";
        throw new RuntimeException(message);
    }

    @Test
    public void randomSlines() {
        Random rand = new Random();
        int randomInt = rand.nextInt();
        if ((randomInt % 2) == 0) {
            System.currentTimeMillis();
        }
        else {
            System.currentTimeMillis();
        }
    }
}
