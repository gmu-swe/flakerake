package test.edu.gmu.edu;

public class FooClass {

    public FooClass() {
        this(0);
        System.out.println("Flaky ctor");
    }

    public FooClass(int x) {
        System.out.println("Flaky inner ctor");
    }

    public void foo() { // Not to be flaky!
        System.out.println("foo!");
    }

    public void fooCalledFromFlakyIHope() {
        System.out.println("Flaky foo!");
    }
}
