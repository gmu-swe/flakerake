package test.edu.gmu.edu;

import org.junit.Assert;
import org.junit.Test;

import java.util.HashSet;
import java.util.Set;

public class NonDexFailureTest {

    @Test
    public void testSetToString() {
        String hello = "hello";
        String world = "world";
        Set set = new HashSet<>();
        set.add(hello);
        set.add(world);
        System.out.println(set);
        Assert.assertEquals("[world, hello]", set.toString());
    }
}
