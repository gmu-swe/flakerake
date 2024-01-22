package agent;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassWriter;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.IllegalClassFormatException;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.util.*;
import java.io.*;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.objectweb.asm.ClassVisitor;

public class Agent {

    private static List<String> blackList;

    static {
        blackList = new ArrayList<>();
        try {
            // get the file url, not working in JAR file.
            //ClassLoader classloader = Agent.class.getClassLoader();
            //InputStream is = classloader.getResourceAsStream("blacklist.txt");
            InputStream is = Agent.class.getResourceAsStream("blacklist.txt");
            if (is == null) {
                System.out.println("blacklist.txt not found");
            }
            else {
                // failed if files have whitespaces or special characters
                InputStreamReader streamReader = new InputStreamReader(is, StandardCharsets.UTF_8);
                BufferedReader reader = new BufferedReader(streamReader);
                String line = reader.readLine();
                while (line != null) {
                    blackList.add(line);
                    // read next line
                    line = reader.readLine();
                }
                reader.close();
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public static boolean blackListContains(String s) {
        for (String prefix : blackList) {
            if (s.startsWith(prefix)) {
                return true;
            }
        }
        return false;
    }
    
    private static List<String> whiteList = new ArrayList<>();
	// White list consists of specific class names (not package prefixing as black list relies on)
    public static boolean whiteListContains(String s) {
        if (whiteList.isEmpty()) {
            whiteList = new ArrayList<>();
            try {
                BufferedReader reader = new BufferedReader(new FileReader(new File(System.getProperty("whitelist"))));
                String line = reader.readLine();
                System.out.println("Givent LINE="+line);
                while (line != null) {
                    //System.out.println("***********LINE="+line);
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
 
    public static void premain(String agentArgs, Instrumentation inst) {
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader classLoader, String s, Class<?> aClass,
                    ProtectionDomain protectionDomain, byte[] bytes) throws IllegalClassFormatException {
                s = s.replaceAll("[/]","."); 
               	if ((System.getProperty("whitelist") != null) && (whiteListContains(s)) ) {
                   boolean x=whiteListContains(s);

                   final ClassReader reader = new ClassReader(bytes);
                   final ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_FRAMES|ClassWriter.COMPUTE_MAXS );
                   // If the concurrentmethods option is not set (meaning we do not know what the concurrent methods are, use the EnterExitClassTracer to find them
                   ClassVisitor visitor;
                    if (System.getProperty("findAPI") != null) {
                       visitor = new EnterExitClassTracer(writer);
                   } else //if (System.getProperty("allAPI")
                   {
                       visitor = new RandomClassTracer(writer);
                   }
                   reader.accept(visitor, 0);
                   return writer.toByteArray();

                }
                return null;
            }
        });

        System.out.println("CALLING to print");
        printStartStopTimes();
    }

    private static void printStartStopTimes() {
        final long start = System.currentTimeMillis();
        Thread hook = new Thread() {
            @Override
            public void run() {
                BufferedWriter bfMethods = null;
                BufferedWriter bfLocations = null;

                try {
                    FileWriter outputMethodsFile = new FileWriter("MethodList.txt");
				    bfMethods = new BufferedWriter(outputMethodsFile);
                    synchronized(Utility.methodsRun) {
                        for (String meth : Utility.methodsRun) {
                            bfMethods.write(meth);
                            bfMethods.newLine();
                        }
                    }

					FileWriter outputLocationsFile = new FileWriter("ResultLocations.txt");
                    bfLocations = new BufferedWriter(outputLocationsFile);

                    synchronized(RandomClassTracer.locations) {
                        for (String location : RandomClassTracer.locations) {
                            bfLocations.write(location);
                            bfLocations.newLine();
                        }
                    }
                    bfLocations.flush();

                    bfMethods.flush();
				} catch (IOException e) {
                    System.out.println("An error occurred.");
                    e.printStackTrace();
                }
			 	finally {
                    try {
                        bfMethods.close();
                    }
                    catch (Exception e) {
                    }
                    //System.out.println(Utility.resultInterception);
                }	
            }
        };
        Runtime.getRuntime().addShutdownHook(hook);
    }
}

