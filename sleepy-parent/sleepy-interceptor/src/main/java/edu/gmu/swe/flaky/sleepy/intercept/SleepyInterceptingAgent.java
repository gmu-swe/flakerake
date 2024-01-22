package edu.gmu.swe.flaky.sleepy.intercept;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.IllegalClassFormatException;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;

import static org.objectweb.asm.Opcodes.*;

public class SleepyInterceptingAgent {

    public static Instrumentation inst;

    public static void premain(String agentArgs, Instrumentation inst) {
        SleepyInterceptingAgent.inst = inst;
        try {
            inst.addTransformer(new ClassFileTransformer() {
                @Override
                public byte[] transform(ClassLoader classLoader, String className, Class<?> aClass, ProtectionDomain protectionDomain, byte[] classfileBuffer) throws IllegalClassFormatException {
                    try {
                        if (className == null) {
                            // Dont worry anon clazzes are still handled.
                            return null;
                        }
                        if (!className.equals("java/lang/Thread") &&
                                !className.equals("java/util/concurrent/ForkJoinTask") &&
                                !className.equals("java/util/concurrent/FutureTask")) {
                            // We handle Thread and ForkJoinTask specially to track threads and sleep during the beginning of a task.
                            // Try to skip most classes we're only interested in user code.
                            if (className.startsWith("java") || className.startsWith("jdk") || className.startsWith("sun") || className.startsWith("edu/gmu") || className.startsWith("com/sun") ||
                                    className.startsWith("org/junit") || className.startsWith("org/apache/maven")) {
                                return null;
                            }
                        }

                        ClassReader cr = new ClassReader(classfileBuffer);
                        ClassWriter cw = new ClassWriter(ClassWriter.COMPUTE_MAXS);
                        ClassVisitor cv = new InterceptingCV(ASM5, cw);
                        cr.accept(cv, ClassReader.EXPAND_FRAMES);
                        return cw.toByteArray();
                    } catch (Throwable t) {
                        //If you don't catch exceptions yourself, JVM will silently squash them
                        t.printStackTrace();
                        return null;
                    }
                }
            }, true);
        } catch (Throwable e) {
            e.printStackTrace();
        }
    }
}
