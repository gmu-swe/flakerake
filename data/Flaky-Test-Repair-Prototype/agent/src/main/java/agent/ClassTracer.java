package agent;

import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import org.objectweb.asm.Type;
import org.objectweb.asm.TypePath;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.Label;
import java.util.*;
import java.io.*;
import java.net.URL;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;

public class ClassTracer extends ClassVisitor {
    private String cn;
    int lineNumber;

    static BufferedReader reader;
    static List<String> listAPI;
    public ClassTracer(ClassVisitor cv) {
        super(Opcodes.ASM9, cv);
    }

    @Override
    public void visit(int version, int access, String name, String signature, String superName, String[] interfaces) {
        this.cn = name;
        super.visit(version, access, name, signature, superName, interfaces);
    }
    String aapi="";	


   @Override
   public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
        final String methodId = this.cn + "." + name;
        final String methodName = name;
        return new MethodVisitor(Opcodes.ASM9, super.visitMethod(access, name, desc, signature, exceptions)) {
            @Override
            public void visitLineNumber(int line, Label start) {
                 lineNumber = line;
                 super.visitLineNumber(line, start);
            }
        
            @Override
            public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {  
                String combined_name = owner +"/" +name+desc;
                if (System.getProperty("api") != null) {
                    aapi= System.getProperty("api");
                    if (aapi.equals(combined_name)) {
                        System.out.println("API matched found, Combined Name...............****************************" + combined_name +", api="+aapi); 
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "agent/Utility", "delay", "()V", false);
                    } 
                    super.visitMethodInsn(opcode, owner, name, desc, itf);
                }
                else
                    super.visitMethodInsn(opcode, owner, name, desc, itf);
             } 
      };
    }
}
