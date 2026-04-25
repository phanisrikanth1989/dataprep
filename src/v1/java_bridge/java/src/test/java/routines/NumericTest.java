package routines;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests for Numeric routines.
 *
 * Covers:
 *   WR-16 fix  — convertImpliedDecimalFormat uses Float.valueOf instead of deprecated new Float(double).
 *   CR-07 guard — Mathematical.INT("100.5") throws (byte-identical to Talend upstream; must NOT truncate).
 */
class NumericTest {

    // ---- WR-16: Float.valueOf replaces deprecated new Float(double) ----

    @Test
    void testConvertImpliedDecimalUsesValueOf() {
        // WR-16: ensures no NoSuchMethodError on Java 17+ (deprecated constructor removed there).
        // "9V99" format means 2 decimal places; "123" -> 1.23
        Float result = Numeric.convertImpliedDecimalFormat("9V99", "123");
        assertNotNull(result, "convertImpliedDecimalFormat should return a Float");
        assertEquals(1.23f, result, 0.001f, "123 with 2 implied decimals should be 1.23");
    }

    @Test
    void testConvertImpliedDecimalNoV() {
        // No 'V' in format -> no decimal shift; "100" -> 100.0
        Float result = Numeric.convertImpliedDecimalFormat("999", "100");
        assertNotNull(result);
        assertEquals(100.0f, result, 0.001f);
    }

    // ---- CR-07: Mathematical.INT regression guard ----

    @Test
    void testIntRejectsDecimal() {
        // CR-07 REGRESSION GUARD: parity with Talend upstream (OpenDAS).
        // Mathematical.INT("100.5") MUST throw NumberFormatException.
        // The audit finding that it should truncate to 100 is WRONG — Talend's
        // Mathematical.INT is byte-identical: Integer.valueOf(e).
        // Talend source:
        //   https://raw.githubusercontent.com/OpenDAS/opendas-talend/master/Jobs/bin/GET_DEV/src/routines/Mathematical.java
        //   public static int INT(String e) { return Integer.valueOf(e); }
        // If this test fails, someone "fixed" INT to truncate — REVERT immediately.
        assertThrows(NumberFormatException.class, () -> Mathematical.INT("100.5"),
            "Talend parity: INT(\"100.5\") must throw NumberFormatException — see CR-07 verdict in RESEARCH.md");
    }

    @Test
    void testIntAcceptsInteger() {
        assertEquals(100, Mathematical.INT("100"),
            "INT(\"100\") should return 100");
    }
}
