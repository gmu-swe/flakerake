package test.edu.gmu.edu;

import org.junit.Assert;
import org.junit.Test;

public class ODFailureTest {

    public static int globalInt = 0;

    @Test
    public void testIncrement() {
        Assert.assertEquals(0, globalInt++);
    }

    @Test
    public void testDecrement() {
        Assert.assertEquals(1, globalInt--);
    }
}
