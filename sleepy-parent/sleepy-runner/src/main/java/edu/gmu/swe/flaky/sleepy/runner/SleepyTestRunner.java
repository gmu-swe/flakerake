package edu.gmu.swe.flaky.sleepy.runner;

import edu.gmu.swe.flaky.sleepy.intercept.FlakyLogger;
import edu.gmu.swe.flaky.sleepy.intercept.Wrapper;
import org.junit.runner.JUnitCore;
import org.junit.runner.Request;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.PrintWriter;
import java.util.HashSet;
import java.util.Scanner;


public class SleepyTestRunner {

    /**
     *
     * @param args
     * 0) TestMethod
     * 1) ThreadID
     * 2) LoggingLevel = info | debug | critical
     * 3) Optional but needed for extra analysis - file containing allowed list of lines to sleep at.
     * @throws ClassNotFoundException
     * @throws FileNotFoundException
     */
    public static void main(String... args) throws ClassNotFoundException, FileNotFoundException {
        String threadIdTarget = args[1];
        long initTimeToSleep = Long.parseLong(args[3]);

        Wrapper.init(threadIdTarget, initTimeToSleep);
        FlakyLogger.init(FlakyLogger.Level.valueOf(args[2].toUpperCase()));

        // Check if we should only insert sleeps for specific lines:
        String[] classAndMethod = args[0].split("#");
        Request request = Request.method(Class.forName(classAndMethod[0]),
                classAndMethod[1]);

        String targetLinesToSleep = null;
        if (args.length > 4) {
            targetLinesToSleep = args[4];
        }

        if (targetLinesToSleep != null) {
            Wrapper.linesToSleepDuringRun = new HashSet<>();
            File file = new File(targetLinesToSleep);
            Scanner scanner = new Scanner(file);
            while (scanner.hasNextLine()) {
                String target = scanner.nextLine().trim();
                Wrapper.linesToSleepDuringRun.add(target);
            }
        }

        Result result = new JUnitCore().run(request);

        // Need the if so that we dont overwrite non failure run on failing run.
        if (result.getFailureCount() > 0) {
            PrintWriter failureReporter = new PrintWriter(new File("./sleepy-records/internal/failure.log"));
            StringBuilder failureBuilder = new StringBuilder();
            for (Failure fail : result.getFailures()) {
                // This loop should only ever be executed once and only once.
                FlakyLogger.info("Failure:");
                FlakyLogger.info(fail.getDescription() + fail.getTrace());
                failureBuilder.append(fail.getTrace());
            }
            failureReporter.write(failureBuilder.toString());
            failureReporter.close();
        }

        FlakyLogger.info(result.wasSuccessful() ? "OK" : "FAILURE");
        System.exit(result.wasSuccessful() ? 0 : 1337);
    }
}
