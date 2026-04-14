package com.citi.gru.etl;

import org.apache.arrow.memory.BufferAllocator;
import org.apache.arrow.vector.*;
import org.apache.arrow.vector.types.pojo.Field;

import java.math.BigDecimal;
import java.util.*;
import java.util.logging.Logger;

/**
 * Arrow serialization utilities for the Java bridge.
 *
 * Provides static helper methods for creating Arrow vectors, setting typed values,
 * and mapping the 7 Python type strings to Java classes. All Arrow vector creation
 * and value-setting in the bridge routes through this class.
 *
 * <p>Supported Python type strings (from type_mapping.py):
 * {@code str}, {@code int}, {@code float}, {@code bool},
 * {@code datetime}, {@code Decimal}, {@code object}
 */
public final class ArrowSerializer {

    private static final Logger logger = Logger.getLogger(ArrowSerializer.class.getName());

    private ArrowSerializer() {
        // Utility class -- no instances
    }

    // ------------------------------------------------------------------
    // Type mapping
    // ------------------------------------------------------------------

    /**
     * Map a Python type string to the corresponding Java class.
     *
     * <p>The 7 recognised type strings are:
     * <ul>
     *   <li>{@code "str"}      -- {@code String.class}</li>
     *   <li>{@code "int"}      -- {@code Long.class}</li>
     *   <li>{@code "float"}    -- {@code Double.class}</li>
     *   <li>{@code "bool"}     -- {@code Boolean.class}</li>
     *   <li>{@code "datetime"} -- {@code java.util.Date.class}</li>
     *   <li>{@code "Decimal"}  -- {@code BigDecimal.class}</li>
     *   <li>{@code "object"}   -- {@code String.class}</li>
     * </ul>
     *
     * Unknown types log a warning and default to {@code String.class}.
     *
     * @param schemaType Python type string from the converter schema
     * @return the Java class for the given type
     */
    public static Class<?> mapSchemaTypeToJava(String schemaType) {
        if (schemaType == null) {
            logger.warning("[JavaBridge] Null schema type -- defaulting to String");
            return String.class;
        }
        switch (schemaType) {
            case "str":
                return String.class;
            case "int":
                return Long.class;
            case "float":
                return Double.class;
            case "bool":
                return Boolean.class;
            case "datetime":
                return Date.class;
            case "Decimal":
                return BigDecimal.class;
            case "object":
                return String.class;
            default:
                logger.warning("[JavaBridge] Unknown schema type: " + schemaType + " -- defaulting to String");
                return String.class;
        }
    }

    // ------------------------------------------------------------------
    // Arrow vector creation
    // ------------------------------------------------------------------

    /**
     * Create a VectorSchemaRoot from column-oriented data using explicit schema types.
     *
     * @param allocator  Arrow buffer allocator
     * @param data       column-oriented data: {columnName: Object[values]}
     * @param schema     column type map: {columnName: pythonTypeString}
     * @return a populated VectorSchemaRoot (caller must close)
     */
    public static VectorSchemaRoot createOutputRootFromData(
            BufferAllocator allocator,
            Map<String, Object[]> data,
            Map<String, String> schema) throws Exception {

        List<Field> fields = new ArrayList<>();
        List<FieldVector> vectors = new ArrayList<>();

        int rowCount = 0;
        // Determine row count from first non-null data array
        for (Object[] values : data.values()) {
            if (values != null) {
                rowCount = values.length;
                break;
            }
        }

        for (Map.Entry<String, String> entry : schema.entrySet()) {
            String colName = entry.getKey();
            String colType = entry.getValue();
            Object[] colData = data.get(colName);

            FieldVector vector = createVectorForType(allocator, colName, colType, rowCount);

            // Populate vector
            for (int i = 0; i < rowCount; i++) {
                Object value = (colData != null && i < colData.length) ? colData[i] : null;
                setVectorValue(vector, i, value, colType);
            }
            vector.setValueCount(rowCount);

            fields.add(vector.getField());
            vectors.add(vector);
        }

        VectorSchemaRoot root = new VectorSchemaRoot(fields, vectors);
        root.setRowCount(rowCount);
        return root;
    }

    /**
     * Create an Arrow FieldVector for the given Python type string.
     *
     * @param allocator  Arrow buffer allocator
     * @param name       column name
     * @param schemaType Python type string (e.g. "str", "int", "Decimal")
     * @param rowCount   expected number of rows (used for Decimal precision inference hint)
     * @return allocated but empty FieldVector (caller must populate and close)
     */
    public static FieldVector createVectorForType(
            BufferAllocator allocator, String name, String schemaType, int rowCount) {

        Class<?> javaType = mapSchemaTypeToJava(schemaType);
        FieldVector vector;

        if (javaType == String.class) {
            vector = new VarCharVector(name, allocator);
        } else if (javaType == Long.class) {
            vector = new BigIntVector(name, allocator);
        } else if (javaType == Double.class) {
            vector = new Float8Vector(name, allocator);
        } else if (javaType == Boolean.class) {
            vector = new BitVector(name, allocator);
        } else if (javaType == Date.class) {
            vector = new DateMilliVector(name, allocator);
        } else if (javaType == BigDecimal.class) {
            // Default precision/scale -- overridden by inferDecimalPrecisionScale if data available
            vector = new DecimalVector(name, allocator, 38, 10);
        } else {
            // Fallback (should not happen given mapSchemaTypeToJava defaults to String)
            vector = new VarCharVector(name, allocator);
        }

        vector.allocateNew();
        return vector;
    }

    /**
     * Set a single value in an Arrow FieldVector with type-correct coercion.
     *
     * @param vector     the target vector
     * @param index      row index
     * @param value      the value to set (may be null)
     * @param schemaType Python type string for coercion guidance
     */
    public static void setVectorValue(FieldVector vector, int index, Object value, String schemaType) {
        if (value == null) {
            vector.setNull(index);
            return;
        }

        if (vector instanceof VarCharVector) {
            ((VarCharVector) vector).setSafe(index, value.toString().getBytes());
        } else if (vector instanceof BigIntVector) {
            ((BigIntVector) vector).setSafe(index, ((Number) value).longValue());
        } else if (vector instanceof Float8Vector) {
            ((Float8Vector) vector).setSafe(index, ((Number) value).doubleValue());
        } else if (vector instanceof BitVector) {
            boolean boolVal = (value instanceof Boolean) ? (Boolean) value : Boolean.parseBoolean(value.toString());
            ((BitVector) vector).setSafe(index, boolVal ? 1 : 0);
        } else if (vector instanceof DateMilliVector) {
            long millis = (value instanceof Date) ? ((Date) value).getTime() : 0;
            ((DateMilliVector) vector).setSafe(index, millis);
        } else if (vector instanceof DecimalVector) {
            BigDecimal decimal = (value instanceof BigDecimal)
                    ? (BigDecimal) value
                    : new BigDecimal(value.toString());
            ((DecimalVector) vector).setSafe(index, decimal);
        } else {
            // Fallback: try to set as VarChar
            logger.fine("[JavaBridge] Unhandled vector type " + vector.getClass().getSimpleName()
                    + " at index " + index + " -- converting to string");
            if (vector instanceof VarCharVector) {
                ((VarCharVector) vector).setSafe(index, value.toString().getBytes());
            }
        }
    }

    // ------------------------------------------------------------------
    // Decimal helpers
    // ------------------------------------------------------------------

    /**
     * Infer precision and scale from an array of values that may contain BigDecimals.
     *
     * @param values array of values (may contain nulls and non-BigDecimal objects)
     * @return int[2] where [0]=precision, [1]=scale. Defaults to {38, 2} if no BigDecimal found.
     */
    public static int[] inferDecimalPrecisionScale(Object[] values) {
        if (values != null) {
            for (Object value : values) {
                if (value instanceof BigDecimal) {
                    BigDecimal bd = (BigDecimal) value;
                    int precision = Math.max(bd.precision(), 38);
                    int scale = bd.scale();
                    return new int[]{precision, scale};
                }
            }
        }
        // Fallback if no BigDecimal values found (all nulls)
        return new int[]{38, 2};
    }
}
