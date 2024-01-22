package edu.gmu.swe.flaky.sleepy.intercept;


import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.FieldVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

public class InterceptingCV extends ClassVisitor {

    public InterceptingCV(int api, ClassVisitor cv) {
        super(api, cv);
    }

    String className;

    @Override
    public FieldVisitor visitField(int i, String s, String s1, String s2, Object o) {

        // FIXME add code for tracking accesses to volatile variables?
//        if (i == Opcodes.ACC_VOLATILE) {
//            System.out.println(s);
//            String so = (o == null) ? "null" : o.toString();
//            System.out.println(so);
//        }
        return super.visitField(i, s, s1, s2, o);
    }

    @Override
    public void visit(int version, int access, String name, String signature, String superName, String[] interfaces) {
        this.className = name;
        super.visit(version, access, name, signature, superName, interfaces);
    }

    @Override
    public MethodVisitor visitMethod(int access, String methodName, String desc, String signature, String[] exceptions) {
        MethodVisitor defaultMV = super.visitMethod(access, methodName, desc, signature, exceptions);
        MethodVisitor sleepyMV = new InterceptingMV(this.api, defaultMV, access, this.className, methodName, desc);
        // Handle Thread class specially to do tracking.
        if (className.equals("java/lang/Thread")) {
            if (methodName.equals("<init>")) {
                MethodVisitor mv = new ThreadTrackingMV(this.api, defaultMV, access, this.className, methodName, desc);
                return mv;
            }
            return defaultMV;
        } else if (className.equals("java/util/concurrent/ForkJoinTask") && (methodName.equals("doExec") || methodName.equals("<init>"))) {
            MethodVisitor mv = new ForkJoinTaskTrackingMV(this.api, defaultMV, access, this.className, methodName, desc);
            return mv;
        }
        return sleepyMV;
    }
}
