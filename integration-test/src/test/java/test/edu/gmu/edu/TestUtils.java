package test.edu.gmu.edu;

public class TestUtils {
	public static int source()
	{
		return 10;
	}
	public static void sink(int in)
	{
		System.out.println("I got " + in);
	}
	public static Holder sourceObj(){
		Holder h = new Holder();
		h.v = 10;
		return h; //h wil be tainted, h.v will not be
	}
	static class Holder{
		int v;
		public int getV() {
			return v; //should get tainted via pass-through
		}
	}
}
