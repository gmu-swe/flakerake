package agent;

import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

public class EnterExitClassTracer extends ClassVisitor {

    private String className;

    public EnterExitClassTracer(ClassVisitor cv) {
        super(Opcodes.ASM9, cv);
    }

    @Override
    public void visit(int version, int access, String name, String signature, String superName, String[] interfaces) {
        System.out.println("From visit*******");
        this.className = name;
        super.visit(version, access, name, signature, superName, interfaces);
    }

    @Override
    public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
        System.out.println("From visitMethod*******");
        // Ignore if constructor or class initializer
        if (name.equals("<init>") || name.equals("<clinit>")) {
            return super.visitMethod(access, name, desc, signature, exceptions);
        }

        final String methodName = className + "." + name + desc;

        System.out.println("MethodName="+methodName);
        return new MethodVisitor(Opcodes.ASM9, super.visitMethod(access, name, desc, signature, exceptions)) {

            final Label start = new Label();
            final Label end = new Label();
		    int lineNumber;	
			
            @Override
            public void visitLineNumber(int line, Label start) {
                 lineNumber = line;
                 super.visitLineNumber(line, start);
            }
        
            @Override
            public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {  // Is used when the method is invoked
                String combined_name = owner +"/" +name+desc;
                super.visitLdcInsn(methodName);
                super.visitMethodInsn(Opcodes.INVOKESTATIC, "agent/Utility",  "recordMethodEntry", "(Ljava/lang/String;)V",  false);
                super.visitMethodInsn(opcode, owner, name, desc, itf);
             } 

        };
    }
}
