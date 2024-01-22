package edu.gmu.swe;


import org.objectweb.asm.*;
import org.objectweb.asm.util.Printer;
import org.objectweb.asm.util.Textifier;

import java.io.IOException;

import static org.objectweb.asm.Opcodes.ASM5;


/**
 * Hello world!
 *
 */
public class App 
{
    public static void main( String[] args ) throws IOException {
        ClassReader classReader = new ClassReader(args[0]);
        classReader.accept(new MethodListerCV(), 0);
    }

    private static class MethodListerCV extends ClassVisitor {
        public MethodListerCV() {
            super(ASM5);
        }

        private MethodListerCV(int api) {
            super(api);
        }

        String className;

        @Override
        public void visit(int version, int access, String name, String signature, String superName, String[] interfaces) {
            this.className = name;
            super.visit(version, access, name, signature, superName, interfaces);
        }

        @Override
        public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
            System.out.println(this.className + "." + name + desc);
            return null;
        }
    }
}
