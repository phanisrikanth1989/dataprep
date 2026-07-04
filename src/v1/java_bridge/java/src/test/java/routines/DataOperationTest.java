package routines;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests for DataOperation routines.
 *
 * Covers:
 *   IN-01 guard — DataOperation.CHAR uses Character.forDigit (byte-identical to Talend upstream).
 *                 The audit finding that CHAR(65) should return 'A' is WRONG.
 */
class DataOperationTest {

    // ---- IN-01: CHAR uses Character.forDigit (Talend parity) ----

    @Test
    void testCharForDigitOutOfRadix() {
        // IN-01 REGRESSION GUARD: parity with Talend upstream (OpenDAS).
        // CHAR(65) uses Character.forDigit(65, 10). Since 65 is not a valid radix-10 digit,
        // Character.forDigit returns '\0'. The audit finding that it should return 'A' (char cast)
        // is WRONG — Talend's source is byte-identical.
        // Talend source:
        //   https://raw.githubusercontent.com/OpenDAS/opendas-talend/master/Jobs/bin/GET_DEV/src/routines/DataOperation.java
        //   public static char CHAR(int i) { return Character.forDigit(i, 10); }
        // If this assertion fails because CHAR was "fixed" to return 'A' via (char) cast — REVERT.
        char result = DataOperation.CHAR(65);
        assertEquals('\0', result,
            "Talend parity: CHAR(65) returns '\\0' from Character.forDigit(65,10), NOT 'A' — see IN-01 in RESEARCH.md");
    }

    @Test
    void testCharForDigitValidDigit() {
        // CHAR(5) returns '5' — Character.forDigit(5, 10) == '5' (valid radix-10 digit)
        assertEquals('5', DataOperation.CHAR(5),
            "CHAR(5) should return '5' via Character.forDigit(5, 10)");
    }

    @Test
    void testCharForDigitZero() {
        // CHAR(0) returns '0' — Character.forDigit(0, 10) == '0'
        assertEquals('0', DataOperation.CHAR(0),
            "CHAR(0) should return '0' via Character.forDigit(0, 10)");
    }
}
