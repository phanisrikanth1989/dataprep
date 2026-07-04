package routines;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests for Mathematical routines.
 *
 * Covers:
 *   IN-02 guard — Mathematical.main(String[]) no longer exists (leftover test code deleted).
 *   CR-07 guard — Mathematical.INT("100.5") throws (byte-identical to Talend upstream; must NOT truncate).
 */
class MathematicalTest {

    // ---- IN-02: main() leftover is gone ----

    @Test
    void testNoMainLeftover() {
        // IN-02: main() was a developer test stub; it has been deleted.
        // This test guards against future re-addition via reflection.
        for (var m : Mathematical.class.getDeclaredMethods()) {
            if ("main".equals(m.getName())
                    && m.getParameterCount() == 1
                    && m.getParameterTypes()[0].equals(String[].class)) {
                fail("Mathematical.main(String[]) should not exist (IN-02 cleanup) — "
                    + "do not re-add this method");
            }
        }
    }

    // ---- CR-07: Mathematical.INT("100.5") throws (Talend parity) ----

    @Test
    void testIntRejectsDecimalString() {
        // CR-07 REGRESSION GUARD: parity with Talend upstream (OpenDAS).
        // Mathematical.INT("100.5") MUST throw NumberFormatException — Talend's INT is
        // byte-identical: public static int INT(String e) { return Integer.valueOf(e); }
        // Talend source:
        //   https://raw.githubusercontent.com/OpenDAS/opendas-talend/master/Jobs/bin/GET_DEV/src/routines/Mathematical.java
        // If this test fails, someone "fixed" INT to truncate — REVERT immediately.
        assertThrows(NumberFormatException.class, () -> Mathematical.INT("100.5"),
            "Talend parity: INT(\"100.5\") must throw NumberFormatException — see CR-07 in RESEARCH.md");
    }

    @Test
    void testIntAcceptsWholeNumber() {
        assertEquals(100, Mathematical.INT("100"),
            "INT(\"100\") should return 100");
    }

    @Test
    void testModBasic() {
        // Sanity check: MOD still works after IN-02 cleanup
        assertEquals(1.0, Mathematical.MOD(3, 2), 0.0001,
            "MOD(3, 2) should return 1.0");
    }
}
