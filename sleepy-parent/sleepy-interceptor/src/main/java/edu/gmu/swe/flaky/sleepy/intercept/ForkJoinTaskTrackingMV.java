package edu.gmu.swe.flaky.sleepy.intercept;

import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.commons.AdviceAdapter;

public class ForkJoinTaskTrackingMV extends AdviceAdapter {
    /***
     * This visitor is used to provide for easier tracking of threads and when/where they began.
     * It's "instrument"al in uniquely identifying threads better than just Thread.getId()
     */

    public ForkJoinTaskTrackingMV(int api, MethodVisitor defaultMV, int accessFlags, String className, String methodName, String desc) {
        super(api, defaultMV, accessFlags, methodName, desc);
        this.methodName = methodName;
        this.className = className;
        if (!(methodName.equals("doExec") || methodName.equals("<init>"))){
            throw new IllegalArgumentException();
        }
    }

    String methodName;
    String className;
    int lineNum = 0;

    @Override
    public void visitLineNumber(int i, Label label) {
        lineNum = i;
        super.visitLineNumber(i, label);
    }

    @Override
    protected void onMethodEnter() {
        // FIXME restructure visitors so we dont duplicate code in InterceptingMV
        super.onMethodEnter();
        if (methodName.equals("doExec")) {
            mapThreadToTask();
        }
        instCallToExtraSleep("RUNNABLE_CALLABLE_START",className, methodName, lineNum);
    }

    @Override
    protected void onMethodExit(int opcode) {
        if (methodName.equals("<init>")) {
            recordThread();
        }
        super.onMethodExit(opcode);
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

    private void mapThreadToTask() {
        super.visitIntInsn(ALOAD, 0); // Get this
        super.visitMethodInsn(INVOKESTATIC,
                "edu/gmu/swe/flaky/sleepy/intercept/Wrapper",
                "mapThreadToForkJoinTask",
                "(Ljava/util/concurrent/ForkJoinTask;)V",
                false
        );
    }

    private void recordThread() {
        super.visitIntInsn(ALOAD, 0); // Get this
        super.visitMethodInsn(INVOKESTATIC,
                "edu/gmu/swe/flaky/sleepy/intercept/Wrapper",
                "trackThread",
                "(Ljava/lang/Object;)V",
                false
        );
    }
}
