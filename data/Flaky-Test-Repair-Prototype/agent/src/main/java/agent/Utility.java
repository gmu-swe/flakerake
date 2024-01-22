package agent;

import java.util.*;

public class Utility{
	private static int delay; 
    static {
       try {
            delay = Integer.parseInt(System.getProperty("delay", "100"));
        } catch (NumberFormatException e) {
            delay = 100;
        }
    }
     

    public static void delay(){
	 	try {
            Thread.sleep(delay);
        }
        catch (InterruptedException e) {
            System.out.println("Exception " );
            e.printStackTrace();
        }
    }
    public static Set<String> methodsRun = new HashSet<>();
    public static void recordMethodEntry(String methodName) {
        //System.out.println("**** methodName="+ methodName);
        synchronized(methodsRun) {
            methodsRun.add(methodName);        
        }
    }   
}
