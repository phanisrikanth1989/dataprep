package com.citi.gru.etl;

import org.apache.arrow.vector.*;
import java.util.*;
import java.math.BigDecimal;

/**
 * Dynamic wrapper for row data to enable field access like row.field_name
 * Supports both reading from Arrow vectors (input_row) and writing to Map (output_row)
 */
public class RowWrapper {

    private VectorSchemaRoot vectorRoot;
    private int rowIndex;
    private String tableName;
    private Map<String, Object> dataMap;
    private boolean isInputRow;

    /**
     * Constructor for input_row (reads from Arrow)
     * @param vectorRoot Arrow vector schema root containing row data
     * @param rowIndex Index of the row to read
     * @param tableName Name of the table (for prefixed column lookup, e.g., "customers", "products")
     */
    public RowWrapper(VectorSchemaRoot vectorRoot, int rowIndex, String tableName) {
        this.vectorRoot = vectorRoot;
        this.rowIndex = rowIndex;
        this.tableName = tableName;
        this.isInputRow = true;
        this.dataMap = null;
    }

    /**
     * Constructor for output_row (writes to Map)
     */
    public RowWrapper(Map<String, String> schema) {
        this.dataMap = new HashMap<>();
        this.isInputRow = false;
        this.vectorRoot = null;
        this.rowIndex = -1;

        // Initialize all fields to null
        for (String fieldName : schema.keySet()) {
            dataMap.put(fieldName, null);
        }
    }

    /**
     * Get field value - used for input_row
     */
    public Object get(String fieldName) {
        if (isInputRow) {
            return getFromArrow(fieldName);
        } else {
            return dataMap.get(fieldName);
        }
    }

    /**
     * Set field value - used for output_row
     */
    public void set(String fieldName, Object value) {
        if (!isInputRow) {
            dataMap.put(fieldName, value);
        } else {
            throw new UnsupportedOperationException("Cannot set values on input_row");
        }
    }

    /**
     * Read value from Arrow vector
     * Implements smart column lookup with table name prefixing
     */
    private Object getFromArrow(String fieldName) {
        FieldVector vector = null;

        // Strategy 1: Try "tableName.fieldName" (e.g., "customers.name")
        if (tableName != null) {
            String prefixedName = tableName + "." + fieldName;
            vector = vectorRoot.getVector(prefixedName);
        }

        // Strategy 2: Fallback to original fieldName (for main table or unprefixed columns)
        if (vector == null) {
            vector = vectorRoot.getVector(fieldName);
        }

        if (vector == null) {
            String attempted = (tableName != null) ?
                    tableName + "." + fieldName + " or " + fieldName :
                    fieldName;
            throw new IllegalArgumentException("Field not found: " + attempted);
        }
    
        if (vector.isNull(rowIndex)) {
            return null;
        }

        // Type-specific extraction
         if (vector instanceof VarCharVector) {
            return ((VarCharVector) vector).getObject(rowIndex).toString();
        } else if (vector instanceof IntVector) {
            return ((IntVector) vector).get(rowIndex);
        } else if (vector instanceof BigIntVector) {
            return ((BigIntVector) vector).get(rowIndex);
        } else if (vector instanceof Float8Vector) {
            return ((Float8Vector) vector).get(rowIndex);
        } else if (vector instanceof BitVector) {
            return ((BitVector) vector).get(rowIndex) == 1;
        } else if (vector instanceof DateMilliVector) {
            return new Date(((DateMilliVector) vector).get(rowIndex));
        } else if (vector instanceof DecimalVector) {
            return ((DecimalVector) vector).getObject(rowIndex);  // Returns BigDecimal
        } else if (vector instanceof Decimal256Vector) {
            return ((Decimal256Vector) vector).getObject(rowIndex);  // For large decimals
        } else {
            return vector.getObject(rowIndex);
        }
    }

    /**
        * Get all data as Map (for output_row)
        */
    public Map<String, Object> toMap() {
        return dataMap;
    }

    // Dynamic property access support using Groovy's propertyMissing
    public Object propertyMissing(String name) {
        return get(name);
    }

    public void propertyMissing(String name, Object value) {
        set(name, value);
    }

    @Override
    public String toString() {
        if (isInputRow && vectorRoot != null) {
            StringBuilder sb = new StringBuilder();
            sb.append("com.citi.gru.etl.RowWrapper[input_row] {");
            List<String> fieldStrings = new ArrayList<>();
            for (FieldVector vector : vectorRoot.getFieldVectors()) {
                String fieldName = vector.getName();
                Object value = get(fieldName);
                fieldStrings.add(fieldName + "=" + String.valueOf(value));
            }
            sb.append(String.join(", ", fieldStrings));
            sb.append("}");
            return sb.toString();
        } else if (!isInputRow && dataMap != null) {
            return "com.citi.gru.etl.RowWrapper[output_row] " + dataMap.toString();
        } else {
            return "com.citi.gru.etl.RowWrapper[unknown]";
            }
        }
    }