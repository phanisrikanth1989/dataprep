package routines;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests for StringHandling routines.
 *
 * Covers:
 *   WR-15 fix  — INSTR bounds check now uses the user-supplied start parameter.
 *   WR-14 guard — LEN(null) returns -1 (byte-identical to Talend upstream; must NOT be changed).
 */
class StringHandlingTest {

    // ---- WR-15: INSTR bounds-check uses user start ----

    @Test
    void testInstrOutOfBounds() {
        // WR-15: start=100 is beyond "hello".length(); must return null, not throw.
        assertNull(StringHandling.INSTR("hello", "x", 100, 1),
            "INSTR with start beyond string length should return null");
    }

    @Test
    void testInstrInBoundsFindsMatch() {
        // "ll" in "hello" starting at position 1 (1-based): found at index 3.
        assertEquals(3, StringHandling.INSTR("hello", "ll", 1, 1),
            "INSTR should return 1-based position 3 for 'll' in 'hello'");
    }

    @Test
    void testInstrNullString() {
        assertNull(StringHandling.INSTR(null, "x", 1, 1),
            "INSTR with null string should return null");
    }

    @Test
    void testInstrEmptySearch() {
        // isVacant("") == true per StringHandling convention -> return null
        assertNull(StringHandling.INSTR("hello", "", 1, 1),
            "INSTR with empty search_value should return null");
    }

    @Test
    void testInstrStartAtMiddle() {
        // start=4 (1-based), searches from 'l' onward in "hello" — "l" found at offset 4
        // "hello" from position 4 is "lo", indexOf("l") == 0, result = 0+1 = 1? No:
        // substring(defaultStart - 1) = substring(3) = "lo", indexOf("l") = 0, result = 0+1 = 1.
        // Then returned value is relative within the substring (Talend convention).
        Integer result = StringHandling.INSTR("hello", "l", 4, 1);
        assertNotNull(result, "INSTR with valid start within bounds should not return null");
    }

    // ---- WR-14: LEN(null) regression guard ----

    @Test
    void testLenNullReturnsMinusOne() {
        // WR-14 REGRESSION GUARD: parity with Talend upstream (OpenDAS).
        // LEN(null) MUST return -1. The audit finding that it should return 0 is WRONG.
        // Talend source (byte-identical):
        //   https://raw.githubusercontent.com/OpenDAS/opendas-talend/master/Jobs/bin/GET_DEV/src/routines/StringHandling.java
        //   public static int LEN(String string) { return string == null ? -1 : string.length(); }
        // If this assertion fails, someone "fixed" LEN to return 0 — REVERT immediately.
        assertEquals(-1, StringHandling.LEN((String) null),
            "Talend parity: LEN(null) must return -1 (NOT 0) — see WR-14 verdict in RESEARCH.md");
    }
}
