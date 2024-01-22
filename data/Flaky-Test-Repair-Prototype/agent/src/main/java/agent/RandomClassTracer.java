package agent;


import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

public class RandomClassTracer extends ClassVisitor{

    private String className;
    private static List<String> whiteList = new ArrayList<>();
    public static Set<String> locations = new HashSet<>();
    public static Set<String> providedLocations = new HashSet<>();

    public RandomClassTracer(ClassVisitor cv) {
        super(Opcodes.ASM9, cv);
    }
		static {
        if (System.getProperty("locations") != null) {
            try {
                BufferedReader reader = new BufferedReader(new FileReader(new File(System.getProperty("locations"))));
                String line = reader.readLine();
                while (line != null) {
                    providedLocations.add(line);
                    // read next line
                    line = reader.readLine();
                }
                reader.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }
	   public static boolean whiteListContains(String s) {
        if (whiteList.isEmpty()) {
            whiteList = new ArrayList<>();
            try {
                BufferedReader reader = new BufferedReader(new FileReader(new File(System.getProperty("allAPI"))));
                String line = reader.readLine();
                while (line != null) {
                    whiteList.add(line);
                    // read next line
                    line = reader.readLine();
                }
                reader.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        return whiteList.contains(s);
    }

    @Override
    public void visit(int version, int access, String name, String signature, String superName, String[] interfaces) {
        this.className = name;
        super.visit(version, access, name, signature, superName, interfaces);
    }

   @Override
    public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
        final String cn = this.className;
        final String containingMethod = cn + "." + name + desc;

        //System.out.println("containingMethod="+containingMethod);
        return new MethodVisitor(Opcodes.ASM9, super.visitMethod(access, name, desc, signature, exceptions)) {
            int lineNumber;

            @Override
            public void visitLineNumber(int line, Label start) {
                System.out.println("LINENUMBER="+line);
                 lineNumber = line;
                 super.visitLineNumber(line, start);
            }

            @Override
            public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {
                String methodName = owner + "." + name + desc;
                String location = cn + "#" + lineNumber;
                // If locations are provided, delay only at those locations [Will needed when we will add delay]
                if (System.getProperty("locations") != null) {
                    //System.out.println("D= " + location);
                    if (providedLocations.contains(location)) {
                        super.visitMethodInsn(Opcodes.INVOKESTATIC, "agent/Utility", "delay", "()V", false);
                    }
                }

                // Insert some random delay call right before invoking the method, with some probability
                else if (whiteListContains(containingMethod)) {
                    locations.add(location);
                }

                super.visitMethodInsn(opcode, owner, name, desc, itf);
            }
        };
    } 

}
