package edu.gmu.swe.flaky.sleepy.intercept;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.PrintWriter;

public class FlakyLogger {
    /* Custom Logger that was made due to difficulty in bundling log4j jar feel free to refactor with
     * actual logging framework if you can figure out how to get log4j shaded and working.
     */

    private static PrintWriter logWriter;
    private static Level loggingLevel = Level.INFO;
    public static void init(Level loggingLevel) {
        FlakyLogger.loggingLevel = loggingLevel;
        File loggingFile = new File("sleepy-records/logs/flakyJava.log");
        try {
            logWriter = new PrintWriter(new FileOutputStream(loggingFile, true), true);
        } catch (FileNotFoundException e) {
            e.printStackTrace();
            throw new RuntimeException();
        }
    }

    public static void debug(String msg) {
        if (loggingLevel == Level.DEBUG) {
            writeLog(msg);
        }
    }

    public static void info(String msg) {
        switch (loggingLevel) {
            case INFO:
            case DEBUG:
                writeLog(msg);
        }
    }

    public static void critical(String msg) {
        writeLog(msg);
    }

    private static void writeLog(String msg) {
        // Log to Java Log and to main log.
        logWriter.println(formatMessage(msg));
        System.out.println(formatMessage(msg));
    }

    private static String formatMessage(String msg) {
        return String.format("%s:FromJava:%s", loggingLevel.toString().toUpperCase(), msg);
    }

    public enum Level {
        DEBUG, INFO, CRITICAL
    }
}
