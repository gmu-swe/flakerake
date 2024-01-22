package edu.gmu.swe.phosphor.maven.bar;


import test.edu.gmu.edu.FooClass;

public class Bar extends FooClass {

    public Bar() {
        super(0);
    }

    @Override
    public void fooCalledFromFlakyIHope() {
        super.fooCalledFromFlakyIHope();
    }
}
