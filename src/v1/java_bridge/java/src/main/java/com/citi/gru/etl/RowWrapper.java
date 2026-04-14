package com.citi.gru.etl;

import java.util.Map;
import java.util.HashMap;
import java.util.logging.Logger;

/**
 * Row accessor for Groovy script binding.
 *
 * Provides Groovy scripts access to input row data (read) and collects output
 * values (write). Supports Groovy's propertyMissing convention so scripts can
 * use {@code input_row.columnName} and {@code output_row.columnName = value}
 * syntax directly.
 *
 * <p>Lifecycle per row iteration:
 * <ol>
 *   <li>Set input row via {@link #setInputRow(Map)}</li>
 *   <li>Groovy script reads via {@link #get(String)} and writes via {@link #set(String, Object)}</li>
 *   <li>Caller retrieves output via {@link #getOutputRow()}</li>
 *   <li>Caller calls {@link #reset()} before next row</li>
 * </ol>
 */
public class RowWrapper {

    private static final Logger logger = Logger.getLogger(RowWrapper.class.getName());

    private Map<String, Object> inputRow;
    private Map<String, Object> outputRow;

    /**
     * Construct a new RowWrapper with empty input and output maps.
     */
    public RowWrapper() {
        this.inputRow = new HashMap<>();
        this.outputRow = new HashMap<>();
    }

    /**
     * Get a value from the input row.
     *
     * @param columnName the column name to look up
     * @return the value, or null if the column is not present
     */
    public Object get(String columnName) {
        return inputRow.get(columnName);
    }

    /**
     * Set a value in the output row.
     *
     * @param columnName the column name to set
     * @param value the value to store
     */
    public void set(String columnName, Object value) {
        outputRow.put(columnName, value);
    }

    /**
     * Get the full input row map.
     *
     * @return the current input row data
     */
    public Map<String, Object> getInputRow() {
        return inputRow;
    }

    /**
     * Replace the input row data for the next iteration.
     *
     * @param row the new input row data
     */
    public void setInputRow(Map<String, Object> row) {
        this.inputRow = (row != null) ? row : new HashMap<>();
    }

    /**
     * Get all output values set by the Groovy script.
     *
     * @return the output row data
     */
    public Map<String, Object> getOutputRow() {
        return outputRow;
    }

    /**
     * Clear the output row for the next row iteration.
     * Input row is not cleared -- caller must call {@link #setInputRow(Map)} explicitly.
     */
    public void reset() {
        outputRow.clear();
        logger.fine("[JavaBridge] RowWrapper reset for next row");
    }

    // ------------------------------------------------------------------
    // Groovy propertyMissing support
    // ------------------------------------------------------------------

    /**
     * Groovy property read: allows {@code row.columnName} syntax.
     *
     * @param name the property (column) name
     * @return the value from the input row
     */
    public Object propertyMissing(String name) {
        return get(name);
    }

    /**
     * Groovy property write: allows {@code row.columnName = value} syntax.
     *
     * @param name the property (column) name
     * @param value the value to set in the output row
     */
    public void propertyMissing(String name, Object value) {
        set(name, value);
    }

    @Override
    public String toString() {
        return "RowWrapper{inputRow=" + inputRow + ", outputRow=" + outputRow + "}";
    }
}
