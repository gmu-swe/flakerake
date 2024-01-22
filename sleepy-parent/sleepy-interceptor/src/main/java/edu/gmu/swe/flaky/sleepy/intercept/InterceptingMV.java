package edu.gmu.swe.flaky.sleepy.intercept;


import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.commons.AdviceAdapter;

import java.io.File;
import java.io.FileNotFoundException;
import java.util.*;

import static org.objectweb.asm.Opcodes.INVOKESTATIC;

public class InterceptingMV extends AdviceAdapter {


    static Set<String> methodCallsWeIntercept = new HashSet<>();
    static Set<String> forbiddenPkgPrefixesForInstr = new HashSet<>();

    static {
        // Note loading as a resource file here does not work. Sadness.
        String pathToFlakyHome = System.getenv("FLAKY_HOME");
        if (pathToFlakyHome == null) {
            throw new RuntimeException("No FLAKY_HOME env variable, must set before running.");
        }
        File file = new File(pathToFlakyHome + "/sleepy-parent/sleepy-interceptor/config-files/initial-large-set");
        try {
            Scanner scanner = new Scanner(file);
            while (scanner.hasNext()) {
                String token = scanner.nextLine();
                if (token.contains("#")) {
                    continue;
                }
                methodCallsWeIntercept.add(token);
            }

        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }

        forbiddenPkgPrefixesForInstr.add("org/apache/maven");
        forbiddenPkgPrefixesForInstr.add("sun");
        forbiddenPkgPrefixesForInstr.add("com/sun");
        forbiddenPkgPrefixesForInstr.add("edu/gmu");
        forbiddenPkgPrefixesForInstr.add("org/junit");
    }


    String classname;
    String methodName;
    String desc;

    String annot;
    int accessFlags = 0;

    int currentLine;

    public InterceptingMV(int api, MethodVisitor defaultMV, int accessFlags, String className, String methodName, String desc) {
        super(api, defaultMV, accessFlags, methodName, desc);

        this.classname = className;
        this.methodName = methodName;
        this.desc = desc;
        this.accessFlags = accessFlags;
    }

    boolean safeToInst(String classname) {
        for (String clazz : forbiddenPkgPrefixesForInstr) {
            if (classname.startsWith(clazz)) {
                return false;
            }
        }
        return true;
    }

    @Override
    public AnnotationVisitor visitAnnotation(String desc, boolean visible) {
        this.annot = desc;
        if (this.annot.equals("Lorg/junit/Test;")) {
            TestTimeoutRemoverAV av = new TestTimeoutRemoverAV(this.api, super.visitAnnotation(desc, visible));
            return av;
        }
        return super.visitAnnotation(desc, visible);
    }
    private static class TestTimeoutRemoverAV extends AnnotationVisitor {
        public TestTimeoutRemoverAV(int api, AnnotationVisitor av) {
            super(api, av);
        }
        @Override
        public AnnotationVisitor visitAnnotation(String name, String desc) {
            return super.visitAnnotation(name, desc);
        }
        @Override
        public void visit(String name, Object value) {
            if (name.equals("timeout")) {
                // Remove test timeouts. We're not really interested in those.
                return;
            }
            super.visit(name, value);
        }
    }

    @Override
    public void visitInsn(int opcode) {
        if (safeToInst(this.classname)) {
            // Sleep before & after monitor enter and monitor exit.
            switch (opcode) {
                case Opcodes.MONITORENTER:
                    instCallToExtraSleep("MONITORENTER", this.classname, this.methodName, currentLine);
                    super.visitInsn(opcode);
                    instCallToExtraSleep("MONITORENTER", this.classname, this.methodName, currentLine);
                    break;
                case Opcodes.MONITOREXIT:
                    instCallToExtraSleep("MONITOREXIT", this.classname, this.methodName, currentLine);
                    super.visitInsn(opcode);
                    instCallToExtraSleep("MONITOREXIT", this.classname, this.methodName, currentLine);
                    break;
                default:
                    super.visitInsn(opcode);
            }
        }
    }

    @Override
    protected void onMethodEnter() {
        super.onMethodEnter();
        if (inSynchronizeKeywordMethod()) {
            // FIXME currently, the first line of a synchronized method is not initialized after onMethodEnter, so this looks like lineNumber 0
            instCallToExtraSleep("SYNCHRONIZED_METHOD_ENTER", classname, methodName, currentLine);
        }
        // As soon as we begin testing start sleeping threads.
        if ((this.methodName.startsWith("test") && desc.contains("V")) || (this.annot != null &&
                (this.annot.endsWith("Test;") || this.annot.endsWith("Before;")))) {
            super.visitMethodInsn(INVOKESTATIC,
                    "edu/gmu/swe/flaky/sleepy/intercept/Wrapper",
                    "setSleep",
                    "()V",
                    false
            );
        }
        // Sleep the beginning of any Runnable or Callable.
        // TODO change below so it actually only instruments only implementers of Runnable
        else if (("." + methodName + desc).equals(".run()V") || ("." + methodName).endsWith(".call")) {
            instCallToExtraSleep("RUNNABLE_CALLABLE_START", classname, methodName, currentLine);
        }
    }

    @Override
    protected void onMethodExit(int opcode) {
        if (inSynchronizeKeywordMethod()) {
            instCallToExtraSleep("SYNCHRONIZED_METHOD_EXIT", classname, methodName, currentLine);
        }
        super.onMethodExit(opcode);
    }

    private boolean inSynchronizeKeywordMethod() {
        return (this.accessFlags & Opcodes.ACC_SYNCHRONIZED) != 0;
    }

    private void instCallToExtraSleep(String cause, String classname, String methodName, int currentLine) {
        super.visitLdcInsn(cause);
        super.visitLdcInsn(classname);
        super.visitLdcInsn(methodName);
        super.visitLdcInsn(currentLine);
        super.visitMethodInsn(INVOKESTATIC,
                "edu/gmu/swe/flaky/sleepy/intercept/Wrapper",
                "extraSleep",
                "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;I)V",
                false
        );
    }

    @Override
    public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {
        // Check if it's a target contention method to intercept and if so add naps before and after call.
        String candidateTarget = owner + "." + name + desc;
        boolean interceptCall = safeToInst(classname) && methodCallsWeIntercept.contains(candidateTarget);
        if (interceptCall) {
            instCallToExtraSleep(candidateTarget, this.classname, this.methodName, currentLine);
            super.visitMethodInsn(opcode, owner, name, desc, itf);
            instCallToExtraSleep(candidateTarget, this.classname, this.methodName, currentLine + 1); // Adding 1 so not to reduce sleep.
        }
        else {
            super.visitMethodInsn(opcode, owner, name, desc, itf);
        }
    }

    @Override
    public void visitLineNumber(int line, Label start) {
        this.currentLine = line;
        super.visitLineNumber(line, start);
    }
}
