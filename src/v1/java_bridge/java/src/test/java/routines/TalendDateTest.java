package routines;

import org.junit.jupiter.api.Test;
import java.text.ParseException;
import java.util.Date;
import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests for TalendDate routines.
 *
 * Covers:
 *   CR-08 partial fix — parseDate error message includes input + pattern + cause preserved.
 *                       Exception type remains RuntimeException (Talend parity).
 */
class TalendDateTest {

    // ---- CR-08: parseDate error message + cause ----

    @Test
    void testParseDateExceptionHasInputInMessage() {
        // CR-08 partial: error message should contain the bad input string
        RuntimeException ex = assertThrows(RuntimeException.class,
            () -> TalendDate.parseDate("yyyy-MM-dd", "not-a-date"),
            "parseDate with invalid input should throw RuntimeException");
        assertTrue(ex.getMessage().contains("not-a-date"),
            "Exception message should include the input string 'not-a-date'");
    }

    @Test
    void testParseDateExceptionHasPatternInMessage() {
        // CR-08 partial: error message should contain the pattern
        RuntimeException ex = assertThrows(RuntimeException.class,
            () -> TalendDate.parseDate("yyyy-MM-dd", "not-a-date"));
        assertTrue(ex.getMessage().contains("yyyy-MM-dd"),
            "Exception message should include the pattern 'yyyy-MM-dd'");
    }

    @Test
    void testParseDateExceptionPreservesCause() {
        // CR-08 partial: cause must be preserved for debuggability
        RuntimeException ex = assertThrows(RuntimeException.class,
            () -> TalendDate.parseDate("yyyy-MM-dd", "bad"));
        assertNotNull(ex.getCause(), "Cause should be preserved (not swallowed)");
        assertInstanceOf(ParseException.class, ex.getCause(),
            "Cause should be ParseException from the underlying parser");
    }

    @Test
    void testParseDateRuntimeExceptionType() {
        // Parity guard: exception must remain plain RuntimeException, NOT a checked exception
        // and NOT a custom subclass. Talend upstream wraps with new RuntimeException(e).
        try {
            TalendDate.parseDate("yyyy-MM-dd", "bad-date-value");
            fail("Expected RuntimeException");
        } catch (RuntimeException ok) {
            // Exact-class check — if this fails, someone promoted it to a checked exception.
            assertEquals(RuntimeException.class, ok.getClass(),
                "Talend parity: must be plain RuntimeException, not a subclass");
        }
    }

    @Test
    void testParseDateSuccess() {
        // Regression guard: valid input still parses correctly
        Date d = TalendDate.parseDate("yyyy-MM-dd", "2026-04-25");
        assertNotNull(d, "Valid date string should parse without error");
    }
}
