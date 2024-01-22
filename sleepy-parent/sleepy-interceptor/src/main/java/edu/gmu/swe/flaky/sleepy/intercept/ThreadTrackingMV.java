package edu.gmu.swe.flaky.sleepy.intercept;

import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.commons.AdviceAdapter;

import static org.objectweb.asm.Opcodes.ALOAD;
import static org.objectweb.asm.Opcodes.INVOKESTATIC;

public class ThreadTrackingMV extends AdviceAdapter {
    /***
     * This visitor is used to provide for easier tracking of threads and when/where they began.
     * It's "instrument"al in uniquely identifying threads better than just Thread.getId()
     */

    public ThreadTrackingMV(int api, MethodVisitor defaultMV, int accessFlags, String className, String methodName, String desc) {
        super(api, defaultMV, accessFlags, methodName, desc);
    }

    @Override
    protected void onMethodExit(int opcode) {
        recordThread();
        super.onMethodExit(opcode);
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
