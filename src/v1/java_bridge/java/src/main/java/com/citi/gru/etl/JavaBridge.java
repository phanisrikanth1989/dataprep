package com.citi.gru.etl;

import org.apache.arrow.memory.RootAllocator;
import org.apache.arrow.vector.*;
import org.apache.arrow.vector.ipc.ArrowStreamReader;
import org.apache.arrow.vector.ipc.ArrowStreamWriter;
import org.apache.arrow.vector.types.pojo.Schema;
import org.apache.arrow.vector.types.pojo.Field;
import org.apache.arrow.vector.types.pojo.FieldType;
import org.apache.arrow.vector.types.pojo.ArrowType;
import groovy.lang.Binding;
import groovy.lang.GroovyShell;
import groovy.lang.Script;
import py4j.GatewayServer;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.Date;
import java.util.concurrent.*;
import java.util.stream.IntStream;

/**
 * Main Java bridge for executing Java/Groovy expressions on Arrow data
 */
public class JavaBridge {

    private RootAllocator allocator;
    private Map<String, Object> context;
    private Map<String, Object> globalMap;
    private GroovyShell groovyShell;
    private Map<String, Class<?>> loadedRoutines;

    // Cache for compiled tMap scripts (key = component ID like "tMap_1")
    private Map<String, CompiledTMapScript> compiledScripts;

    public JavaBridge() {
        this.allocator = new RootAllocator(Long.MAX_VALUE);
        this.context = new HashMap<>();
        this.globalMap = new HashMap<>();
        this.loadedRoutines = new HashMap<>();
        this.compiledScripts = new ConcurrentHashMap<>();

        // Initialize Groovy shell
        Binding binding = new Binding();
        this.groovyShell = new GroovyShell(binding);
    }

    /**
     * Inner class to hold compiled tMap script metadata
     */
    private static class CompiledTMapScript {
        Script script;
        Map<String, List<String>> outputSchemas;
        Map<String, String> outputTypes;
        String mainTableName;
        List<String> lookupNames;

        CompiledTMapScript(Script script, Map<String, List<String>> outputSchemas,
                           Map<String, String> outputTypes, String mainTableName,
                           List<String> lookupNames) {
            this.script = script;
            this.outputSchemas = outputSchemas;
            this.outputTypes = outputTypes;
            this.mainTableName = mainTableName;
            this.lookupNames = lookupNames;
        }
    }

    /**
     * Execute tJavaRow-style code block
     */
    public byte[] executeJavaRow(byte[] arrowData, String javaCode,
                                 Map<String, String> outputSchema,
                                 Map<String, Object> contextVars,
                                 Map<String, Object> globalMapVars) throws Exception {

        // Update context and globalMap
        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        // Read input Arrow data
        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();

        // Prepare output vectors based on schema
        // Use arrays to store results (thread-safe access by index)
        Map<String, Object[]> outputArrays = new HashMap<>();
        for (String colName : outputSchema.keySet()) {
            outputArrays.put(colName, new Object[rowCount]);
        }

        // ==========================================
        // OPTIMIZATION: Compile Groovy script ONCE
        // ==========================================
        System.out.println("Compiling Groovy script...");
        long compileStart = System.currentTimeMillis();
        GroovyShell shell = new GroovyShell();
        Script compiledScript = shell.parse(javaCode);
        long compileTime = System.currentTimeMillis() - compileStart;
        System.out.println("Script compiled in " + compileTime + " ms");

        // Execute code for each row IN PARALLEL
        System.out.println("Processing " + rowCount + " rows in parallel...");
        long execStart = System.currentTimeMillis();

        IntStream.range(0, rowCount).parallel().forEach(i -> {
            try {
                RowWrapper input_row = new RowWrapper(inputRoot, i, "input_row");
                RowWrapper output_row = new RowWrapper(outputSchema);

                // System.out.println("input_row: " + input_row.toString());
                // System.out.println("output_row: " + output_row.toString());

                // Prepare Groovy binding for this row
                Binding binding = new Binding();
                binding.setVariable("input_row", input_row);
                binding.setVariable("output_row", output_row);
                binding.setVariable("context", context);
                binding.setVariable("globalMap", globalMap);

                // Add loaded routines to binding in TWO ways:
                // 1. Direct access: ValidationUtils.method()
                for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
                    binding.setVariable(entry.getKey(), entry.getValue());
                }
                // 2. Namespace access: routines.ValidationUtils.method()
                Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
                binding.setVariable("routines", routinesNamespace);

                // Execute COMPILED script with this row's binding
                synchronized (compiledScript) {
                    compiledScript.setBinding(binding);
                    compiledScript.run();
                }

                // Collect output_row values into arrays (thread-safe by index)
                for (String colName : outputSchema.keySet()) {
                    outputArrays.get(colName)[i] = output_row.get(colName);
                }
            } catch (Exception e) {
                throw new RuntimeException("Error processing row " + i, e);
            }
        });

        long execTime = System.currentTimeMillis() - execStart;
        System.out.println("Processed " + rowCount + " rows in " + execTime + " ms (" + (rowCount * 1000 / execTime) + " rows/sec)");

        // Convert arrays to Lists for createOutputRootFromData
        Map<String, List<Object>> outputData = new HashMap<>();
        for (Map.Entry<String, Object[]> entry : outputArrays.entrySet()) {
            outputData.put(entry.getKey(), Arrays.asList(entry.getValue()));
        }

        // Create output Arrow table
        VectorSchemaRoot outputRoot = createOutputRootFromData(outputSchema, outputData, rowCount);

        // Write to Arrow bytes
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
        writer.writeBatch();
        writer.close();

        // Cleanup
        inputRoot.close();
        reader.close();
        outputRoot.close();

        return outputStream.toByteArray();
    }

    /**
     * Execute one-time expression
     */
    public Object executeOneTimeExpression(String expression, Map<String, Object> contextVars) {
        this.context.putAll(contextVars);

        Binding binding = new Binding();
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);

        // Add loaded routines in TWO ways:
        // 1. Direct access: ValidationUtils.method()
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            binding.setVariable(entry.getKey(), entry.getValue());
        }
        // 2. Namespace access: routines.ValidationUtils.method()
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        binding.setVariable("routines", routinesNamespace);

        // Create new GroovyShell with binding
        GroovyShell shell = new GroovyShell(binding);
        return shell.evaluate(expression);
    }

    /**
     * Execute multiple one-time expressions in batch
     *
     * Efficient batch execution of multiple Java/Groovy expressions.
     * Creates one GroovyShell and reuses it for all expressions.
     *
     * @param expressions Map of {key: expression_string} to evaluate
     * @param contextVars Context variables available to expressions
     * @return Map of {key: result_value} for each expression
     *
     * Example:
     *   Input: {"footer": "1 + context.count", "limit": "context.rows * 2"}
     *   Output: {"footer": 6, "limit": 200}
     */
    public Map<String, Object> executeBatchOneTimeExpressions(
            Map<String, String> expressions,
            Map<String, Object> contextVars) {

        // Update context
        this.context.putAll(contextVars);

        // Prepare shared binding (reused for all expressions)
        Binding binding = new Binding();
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);

        // Add loaded routines in TWO ways:
        // 1. Direct access: ValidationUtils.method()
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            binding.setVariable(entry.getKey(), entry.getValue());
        }
        // 2. Namespace access: routines.ValidationUtils.method()
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        binding.setVariable("routines", routinesNamespace);

        // Create one GroovyShell to reuse
        GroovyShell shell = new GroovyShell(binding);

        // Evaluate all expressions
        Map<String, Object> results = new HashMap<>();
        for (Map.Entry<String, String> entry : expressions.entrySet()) {
            String key = entry.getKey();
            String expression = entry.getValue();

            try {
                Object result = shell.evaluate(expression);
                results.put(key, result);
            } catch (Exception e) {
                System.err.println("Error evaluating expression '" + key + "': " + expression);
                System.err.println("Error: " + e.getMessage());
                // Store the error as a string so Python can handle it
                results.put(key, "{{ERROR}}" + e.getMessage());
            }
        }

        return results;
    }

    /**
     * Execute tMap preprocessing - batch evaluate expressions on all rows
     *
     * Used for evaluating filters and join key expressions during tMap preprocessing.
     * Each expression is evaluated once per row, returning an array of results.
     *
     * @param arrowData Input DataFrame as Arrow bytes
     * @param expressions Map of {expr_id: expression_string} to evaluate on each row
     * @param mainTableName Name of the main table (for row variable binding)
     * @param lookupNames List of lookup table names already joined
     * @param contextVars Context variables
     * @param globalMapVars Global map variables
     * @return Map of {expr_id: Object[]} where Object[] contains result for each row
     *
     * Example:
     *   Input: 3 rows, expressions: {"filter": "orders.status == 'COMPLETE'", "join_key": "customers.region_id"}
     *   Output: {"filter": [true, false, true], "join_key": [5, 3, 5]}
     */
    public Map<String, Object[]> executeTMapPreprocessing(
            byte[] arrowData,
            Map<String, String> expressions,
            String mainTableName,
            List<String> lookupNames,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {

        // Update context and globalMap
        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        // Read input Arrow data
        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();

        System.out.println("tMap Preprocessing: " + rowCount + " rows, " + expressions.size() + " expressions");

        // ==========================================
        // OPTIMIZATION: Compile all expressions ONCE
        // ==========================================
        System.out.println("Compiling " + expressions.size() + " expressions...");
        long compileStart = System.currentTimeMillis();

        Map<String, Script> compiledExpressions = new HashMap<>();
        GroovyShell compileShell = new GroovyShell();

        for (Map.Entry<String, String> entry : expressions.entrySet()) {
            String exprId = entry.getKey();
            String expression = entry.getValue();
            try {
                Script compiledScript = compileShell.parse(expression);
                compiledExpressions.put(exprId, compiledScript);
            } catch (Exception e) {
                System.err.println("Error compiling expression '" + exprId + "': " + expression);
                System.err.println("Error: " + e.getMessage());
                // Skip expressions that don't compile
            }
        }

        long compileTime = System.currentTimeMillis() - compileStart;
        System.out.println("Compiled " + compiledExpressions.size() + " expressions in " + compileTime + " ms");

        // Prepare result arrays for each expression
        Map<String, Object[]> results = new HashMap<>();
        for (String exprId : expressions.keySet()) {
            results.put(exprId, new Object[rowCount]);
        }

        // Execute compiled expressions in parallel
        System.out.println("Processing " + rowCount + " rows in parallel...");
        long execStart = System.currentTimeMillis();

        IntStream.range(0, rowCount).parallel().forEach(i -> {
            try {
                // Create RowWrapper for main table
                RowWrapper mainRow = new RowWrapper(inputRoot, i, mainTableName);

                // Prepare binding for this row
                Binding binding = new Binding();
                binding.setVariable(mainTableName, mainRow);  // e.g., "orders"

                // Create RowWrappers for ALL joined lookup tables
                for (String lookupName : lookupNames) {
                    RowWrapper lookupRow = new RowWrapper(inputRoot, i, lookupName);
                    binding.setVariable(lookupName, lookupRow);
                }

                binding.setVariable("context", context);
                binding.setVariable("globalMap", globalMap);

                // Add loaded routines
                for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
                    binding.setVariable(entry.getKey(), entry.getValue());
                }
                Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
                binding.setVariable("routines", routinesNamespace);

                // Evaluate all COMPILED expressions for this row
                for (Map.Entry<String, Script> entry : compiledExpressions.entrySet()) {
                    String exprId = entry.getKey();
                    Script compiledScript = entry.getValue();

                    try {
                        // Execute compiled script with this row's binding
                        synchronized (compiledScript) {
                            compiledScript.setBinding(binding);
                            Object result = compiledScript.run();
                            results.get(exprId)[i] = result;
                        }
                    } catch (Exception e) {
                        System.err.println("Error evaluating expression '" + exprId + "' at row " + i);
                        System.err.println("Error: " + e.getMessage());
                        results.get(exprId)[i] = null;  // Store null on error
                    }
                }
            } catch (Exception e) {
                throw new RuntimeException("Error processing row " + i, e);
            }
        });

        long execTime = System.currentTimeMillis() - execStart;
        System.out.println("Processed " + rowCount + " rows in " + execTime + " ms (" + (rowCount * 1000 / execTime) + " rows/sec)");

        // Cleanup
        inputRoot.close();
        reader.close();

        System.out.println("tMap Preprocessing complete: " + results.size() + " result arrays");

        return results;
    }

    /**
     * Execute tMap outputs with COMPILED script (OPTIMIZED)
     *
     * This is the optimized version that compiles the entire tMap logic once
     * and executes in parallel, similar to tJavaRow. Achieves much higher throughput
     * than executeTMapOutputs().
     *
     * @param javaScript Pre-generated Java/Groovy script containing all tMap logic
     * @param arrowData Joined DataFrame as Arrow bytes
     * @param outputSchemas Map of {output_name: [column_names...]}
     * @param outputTypes Map of {output_name_columnName: type_string}
     * @param mainTableName Main input table name (e.g., "orders")
     * @param lookupNames List of lookup table names (e.g., ["customers", "products"])
     * @param contextVars Context variables
     * @param globalMapVars Global map variables
     * @return Map of {output_name: arrow_bytes} for each output
     *
     * The script should use this pattern:
     * - Setup output arrays and counters
     * - Process rows in parallel
     * - Evaluate variables in order (with dependencies)
     * - Route to outputs based on filters
     * - Return map with {output_name: {data: Object[][], count: int}}
     */
    public Map<String, byte[]> executeTMapCompiled(
            String javaScript,
            byte[] arrowData,
            Map<String, List<String>> outputSchemas,
            Map<String, String> outputTypes,
            String mainTableName,
            List<String> lookupNames,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {

        // Update context and globalMap
        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        // Read joined Arrow data
        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();

        System.out.println("tMap Compiled: " + rowCount + " rows, " + outputSchemas.size() + " outputs");

        // ==========================================
        // OPTIMIZATION: Compile script ONCE
        // ==========================================
        System.out.println("Compiling tMap script...");
        long compileStart = System.currentTimeMillis();

        // Create binding with framework variables
        Binding compileBinding = new Binding();
        compileBinding.setVariable("inputRoot", inputRoot);
        compileBinding.setVariable("rowCount", rowCount);
        compileBinding.setVariable("mainTableName", mainTableName);
        compileBinding.setVariable("lookupNames", lookupNames);
        compileBinding.setVariable("context", context);
        compileBinding.setVariable("globalMap", globalMap);
        compileBinding.setVariable("allocator", allocator);

        // Add loaded routines
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            compileBinding.setVariable(entry.getKey(), entry.getValue());
        }
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        compileBinding.setVariable("routines", routinesNamespace);

        // Add output schema information
        compileBinding.setVariable("outputSchemas", outputSchemas);
        compileBinding.setVariable("outputTypes", outputTypes);

        GroovyShell shell = new GroovyShell(compileBinding);
        Script compiledScript = shell.parse(javaScript);
        compiledScript.setBinding(compileBinding);

        long compileTime = System.currentTimeMillis() - compileStart;
        System.out.println("Script compiled in " + compileTime + " ms");

        // Execute compiled script
        System.out.println("Executing compiled script...");
        long execStart = System.currentTimeMillis();

        Object scriptResult = compiledScript.run();

        long execTime = System.currentTimeMillis() - execStart;
        System.out.println("Executed in " + execTime + " ms (" + (rowCount * 1000 / execTime) + " rows/sec)");

        // Script returns: Map<String, Map<String, Object>>
        // {output_name: {data: Object[][], count: int}}
        Map<String, Map<String, Object>> outputResults = (Map<String, Map<String, Object>>) scriptResult;

        // Cleanup input
        inputRoot.close();
        reader.close();

        // ==========================================
        // Convert results to Arrow format
        // ==========================================
        Map<String, byte[]> outputArrowData = new HashMap<>();

        for (Map.Entry<String, Map<String, Object>> entry : outputResults.entrySet()) {
            String outputName = entry.getKey();
            Map<String, Object> outputResult = entry.getValue();

            // Skip __errors__ - it's metadata, not a DataFrame output
            if ("__errors__".equals(outputName)) {
                continue;
            }

            Object[][] data = (Object[][]) outputResult.get("data");
            int count = ((Number) outputResult.get("count")).intValue();

            List<String> columnNames = outputSchemas.get(outputName);

            System.out.println("Output '" + outputName + "': " + count + " rows, " + columnNames.size() + " columns");

            // Build schema
            Map<String, String> schema = new HashMap<>();
            for (String colName : columnNames) {
                String typeKey = outputName + "_" + colName;
                String colType = outputTypes.get(typeKey);
                schema.put(colName, colType);
            }

            // Convert Object[][] to column-oriented data
            Map<String, List<Object>> columnData = new HashMap<>();
            for (int colIdx = 0; colIdx < columnNames.size(); colIdx++) {
                String colName = columnNames.get(colIdx);
                List<Object> colValues = new ArrayList<>();
                for (int rowIdx = 0; rowIdx < count; rowIdx++) {
                    colValues.add(data[rowIdx][colIdx]);
                }
                columnData.put(colName, colValues);
            }

            // Create Arrow table
            VectorSchemaRoot outputRoot = createOutputRootFromData(schema, columnData, count);

            // Write to Arrow bytes
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
            writer.writeBatch();
            writer.close();

            outputArrowData.put(outputName, outputStream.toByteArray());

            // Cleanup
            outputRoot.close();
        }

        return outputArrowData;
    }

    /**
     * Compile tMap script ONCE and cache it (STEP 1 of 2)
     *
     * Compiles the tMap script and stores it with the component ID as key.
     * This allows executing the script multiple times on different chunks without recompiling.
     *
     * @param componentId Unique component ID (e.g., "tMap_1", "tMap_2")
     * @param javaScript Pre-generated Java/Groovy script containing all tMap logic
     * @param outputSchemas Map of {output_name: [column_names...]}
     * @param outputTypes Map of {output_name_columnName: type_string}
     * @param mainTableName Main input table name (e.g., "orders")
     * @param lookupNames List of lookup table names (e.g., ["customers", "products"])
     * @return componentId (for confirmation)
     */
    public String compileTMapScript(
            String componentId,
            String javaScript,
            Map<String, List<String>> outputSchemas,
            Map<String, String> outputTypes,
            String mainTableName,
            List<String> lookupNames) throws Exception {

        System.out.println("=== Compiling tMap script for component: " + componentId + " ===");
        long compileStart = System.currentTimeMillis();

        // Create binding template (will be cloned for each execution)
        Binding compileBinding = new Binding();

        // Add loaded routines
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            compileBinding.setVariable(entry.getKey(), entry.getValue());
        }
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        compileBinding.setVariable("routines", routinesNamespace);

        // Add output schema information
        compileBinding.setVariable("outputSchemas", outputSchemas);
        compileBinding.setVariable("outputTypes", outputTypes);

        // Compile the script
        GroovyShell shell = new GroovyShell(compileBinding);
        Script compiledScript = shell.parse(javaScript);

        long compileTime = System.currentTimeMillis() - compileStart;
        System.out.println("Script compiled in " + compileTime + " ms");

        // Cache the compiled script with metadata
        CompiledTMapScript cachedScript = new CompiledTMapScript(
                compiledScript,
                outputSchemas,
                outputTypes,
                mainTableName,
                lookupNames
        );
        compiledScripts.put(componentId, cachedScript);

        System.out.println("Cached compiled script for: " + componentId);

        return componentId;
    }

    /**
     * Execute pre-compiled tMap script on a chunk of data (STEP 2 of 2)
     *
     * Executes a previously compiled tMap script on the given chunk of data.
     * This avoids recompiling the script for each chunk, providing massive performance gains.
     *
     * @param componentId Component ID used during compilation
     * @param arrowData Joined DataFrame chunk as Arrow bytes
     * @param contextVars Context variables
     * @param globalMapVars Global map variables
     * @return Map of {output_name: arrow_bytes} for each output
     */
    public Map<String, byte[]> executeCompiledTMap(
            String componentId,
            byte[] arrowData,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {

        // Get cached compiled script
        CompiledTMapScript cachedScript = compiledScripts.get(componentId);
        if (cachedScript == null) {
            throw new IllegalArgumentException("No compiled script found for component: " + componentId + 
                ". Call compileTMapScript() first!");
        }

        // Update context and globalMap
        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        // Read joined Arrow data
        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();

        System.out.println("Executing compiled " + componentId + ": " + rowCount + " rows, " + 
            cachedScript.outputSchemas.size() + " outputs");

        // Prepare binding with this chunk's data
        Binding execBinding = new Binding();
        execBinding.setVariable("inputRoot", inputRoot);
        execBinding.setVariable("rowCount", rowCount);
        execBinding.setVariable("mainTableName", cachedScript.mainTableName);
        execBinding.setVariable("lookupNames", cachedScript.lookupNames);
        execBinding.setVariable("context", context);
        execBinding.setVariable("globalMap", globalMap);
        execBinding.setVariable("allocator", allocator);

        // Add loaded routines
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            execBinding.setVariable(entry.getKey(), entry.getValue());
        }
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        execBinding.setVariable("routines", routinesNamespace);

        // Add output schema information
        execBinding.setVariable("outputSchemas", cachedScript.outputSchemas);
        execBinding.setVariable("outputTypes", cachedScript.outputTypes);

        // Execute compiled script with this chunk's binding
        long execStart = System.currentTimeMillis();
        Script script = cachedScript.script;

        synchronized (script) {
            script.setBinding(execBinding);
            Object scriptResult = script.run();

            long execTime = System.currentTimeMillis() - execStart;
            System.out.println("Executed in " + execTime + " ms (" + (rowCount * 1000 / execTime) + " rows/sec)");

            // Script returns: Map<String, Map<String, Object>>
            // {output_name: {data: Object[][], count: int}}
            Map<String, Map<String, Object>> outputResults = (Map<String, Map<String, Object>>) scriptResult;

            // Cleanup input
            inputRoot.close();
            reader.close();

            // Convert results to Arrow format
            Map<String, byte[]> outputArrowData = new HashMap<>();

            for (Map.Entry<String, Map<String, Object>> entry : outputResults.entrySet()) {
                String outputName = entry.getKey();
                Map<String, Object> outputResult = entry.getValue();

                // Skip __errors__ - it's metadata, not a DataFrame output
                if ("__errors__".equals(outputName)) {
                    continue;
                }

                Object[][] data = (Object[][]) outputResult.get("data");
                int count = ((Number) outputResult.get("count")).intValue();

                List<String> columnNames = cachedScript.outputSchemas.get(outputName);

                System.out.println("Output '" + outputName + "': " + count + " rows, " + columnNames.size() + " columns");

                // Build schema
                Map<String, String> schema = new HashMap<>();
                for (String colName : columnNames) {
                    String typeKey = outputName + "_" + colName;
                    String colType = cachedScript.outputTypes.get(typeKey);
                    schema.put(colName, colType);
                }

                // Convert Object[][] to column-oriented data
                Map<String, List<Object>> columnData = new HashMap<>();
                for (int colIdx = 0; colIdx < columnNames.size(); colIdx++) {
                    String colName = columnNames.get(colIdx);
                    List<Object> colValues = new ArrayList<>();
                    for (int rowIdx = 0; rowIdx < count; rowIdx++) {
                        colValues.add(data[rowIdx][colIdx]);
                    }
                    columnData.put(colName, colValues);
                }

                // Create Arrow table
                VectorSchemaRoot outputRoot = createOutputRootFromData(schema, columnData, count);

                // Write to Arrow bytes
                ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
                ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
                writer.writeBatch();
                writer.close();

                outputArrowData.put(outputName, outputStream.toByteArray());

                // Cleanup
                outputRoot.close();
            }

            return outputArrowData;
        }
    }

    /**
     * Load a custom routine class
     */
    public void loadRoutine(String className) throws Exception {
        Class<?> routineClass = Class.forName(className);
        String simpleName = routineClass.getSimpleName();
        loadedRoutines.put(simpleName, routineClass);
        System.out.println("Loaded routine: " + simpleName);
    }

    /**
     * Validate that required libraries are available on classpath
     *
     * @param libraryNames List of JAR filenames to validate
     * @return List of missing libraries (empty if all are available)
     */
    public List<String> validateLibraries(List<String> libraryNames) {
        List<String> missing = new ArrayList<>();

        if (libraryNames == null || libraryNames.isEmpty()) {
            return missing;
        }

        // Get the classpath
        String classpath = System.getProperty("java.class.path");

        System.out.println("Validating libraries against classpath...");

        for (String libraryName : libraryNames) {
            // Check if the library JAR is in the classpath
            if (!classpath.contains(libraryName)) {
                System.out.println("Missing: " + libraryName);
                missing.add(libraryName);
            } else {
                System.out.println("Found: " + libraryName);
            }
        }

        return missing;
    }

    public Map<String, Object> getContext() {
        return this.context;
    }

    public Map<String, Object> getGlobalMap() {
        return this.globalMap;
    }

    // Helper methods for creating Arrow output
    private VectorSchemaRoot createOutputRootFromData(Map<String, String> schema,
                                                      Map<String, List<Object>> data,
                                                      int rowCount) throws Exception {
        List<Field> fields = new ArrayList<>();
        List<FieldVector> vectors = new ArrayList<>();

        // Create vector for each column
        for (Map.Entry<String, String> entry : schema.entrySet()) {
            String colName = entry.getKey();
            String colType = entry.getValue();
            List<Object> colData = data.get(colName);

            // Infer type from schema string or first non-null value
            Class<?> javaType = inferJavaTypeFromSchema(colType, colData);

            FieldVector vector = createVectorForType(colName, javaType, rowCount, colData);

            // Populate vector
            for (int i = 0; i < rowCount; i++) {
                Object value = (colData != null && i < colData.size()) ? colData.get(i) : null;
                setVectorValue(vector, i, value);
            }
            vector.setValueCount(rowCount);

            fields.add(vector.getField());
            vectors.add(vector);
        }

        VectorSchemaRoot root = new VectorSchemaRoot(fields, vectors);
        root.setRowCount(rowCount);

        return root;
    }

    private FieldVector createVectorForType(String name, Class<?> type, int rowCount, List<Object> colData) {
        FieldVector vector;

        if (type == String.class) {
            vector = new VarCharVector(name, allocator);
        } else if (type == Integer.class || type == int.class) {
            vector = new IntVector(name, allocator);
        } else if (type == Long.class || type == long.class) {
            vector = new BigIntVector(name, allocator);
        } else if (type == Double.class || type == double.class) {
            vector = new Float8Vector(name, allocator);
        } else if (type == Float.class || type == float.class) {
            vector = new Float4Vector(name, allocator);
        } else if (type == Boolean.class || type == boolean.class) {
            vector = new BitVector(name, allocator);
        } else if (type == Date.class) {
            vector = new DateMilliVector(name, allocator);
        } else if (type == BigDecimal.class) {
            // Infer precision and scale from first non-null value
            int[] precisionScale = inferDecimalPrecisionScale(colData);
            int precision = precisionScale[0];
            int scale = precisionScale[1];
            vector = new DecimalVector(name, allocator, precision, scale);
        } else {
            // Default to String for unknown types
            vector = new VarCharVector(name, allocator);
        }

        vector.allocateNew();
        return vector;
    }

    private int[] inferDecimalPrecisionScale(List<Object> colData) {
        // Find first non-null BigDecimal value and use its precision/scale
        // This assumes all values in the column have the same scale (typical for financial data)
        if (colData != null) {
            for (Object value : colData) {
                if (value instanceof BigDecimal) {
                    BigDecimal bd = (BigDecimal) value;
                    int precision = bd.precision();
                    int scale = bd.scale();

                    // Ensure minimum precision to avoid overflow
                    precision = Math.max(precision, 38);

                    return new int[]{precision, scale};
                }
            }
        }

        // Fallback if no BigDecimal values found (all nulls)
        return new int[]{38, 2};
    }

    private void setVectorValue(FieldVector vector, int index, Object value) {
        if (value == null) {
            vector.setNull(index);
            return;
        }

        if (vector instanceof VarCharVector) {
            ((VarCharVector) vector).setSafe(index, value.toString().getBytes());
        } else if (vector instanceof IntVector) {
            ((IntVector) vector).setSafe(index, ((Number) value).intValue());
        } else if (vector instanceof BigIntVector) {
            ((BigIntVector) vector).setSafe(index, ((Number) value).longValue());
        } else if (vector instanceof Float8Vector) {
            ((Float8Vector) vector).setSafe(index, ((Number) value).doubleValue());
        } else if (vector instanceof Float4Vector) {
            ((Float4Vector) vector).setSafe(index, ((Number) value).floatValue());
        } else if (vector instanceof BitVector) {
            ((BitVector) vector).setSafe(index, (Boolean) value ? 1 : 0);
        } else if (vector instanceof DateMilliVector) {
            long millis = (value instanceof Date) ? ((Date) value).getTime() : 0;
            ((DateMilliVector) vector).setSafe(index, millis);
        } else if (vector instanceof DecimalVector) {
            BigDecimal decimal = (value instanceof BigDecimal) ? (BigDecimal) value : new BigDecimal(value.toString());
            ((DecimalVector) vector).setSafe(index, decimal);
        }
    }

    private Class<?> inferJavaTypeFromSchema(String schemaType, List<Object> data) {
        // Try to infer from schema string
        if (schemaType != null) {
            switch (schemaType.toLowerCase()) {
                case "string":
                    return String.class;
                case "integer":
                case "int":
                    return Integer.class;
                case "long":
                    return Long.class;
                case "double":
                    return Double.class;
                case "float":
                    return Float.class;
                case "boolean":
                    return Boolean.class;
                case "date":
                    return Date.class;
                case "bigdecimal":
                case "id_bigdecimal":
                case "decimal":
                    return BigDecimal.class;
            }
        }

        // Fallback: infer from first non-null data value
        if (data != null) {
            for (Object value : data) {
                if (value != null) {
                    return value.getClass();
                }
            }
        }

        return String.class; // Default
    }

    /**
     * Execute batch one-time expressions with both context and globalMap
     * This version accepts globalMap as a parameter to ensure iteration variables are available
     */
    public Map<String, Object> executeBatchOneTimeExpressionsWithGlobalMap(
            Map<String, String> expressions,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) {

        // Update context
        this.context.putAll(contextVars);

        // Update globalMap with provided values (important for iteration variables)
        this.globalMap.putAll(globalMapVars);

        // Prepare shared binding (reused for all expressions)
        Binding binding = new Binding();
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);

        // Add loaded routines in TWO ways:
        // 1. Direct access: ValidationUtils.method()
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            binding.setVariable(entry.getKey(), entry.getValue());
        }
        // 2. Namespace access: routines.ValidationUtils.method()
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        binding.setVariable("routines", routinesNamespace);

        // Create one GroovyShell to reuse
        GroovyShell shell = new GroovyShell(binding);

        // Evaluate all expressions
        Map<String, Object> results = new HashMap<>();
        for (Map.Entry<String, String> entry : expressions.entrySet()) {
            String key = entry.getKey();
            String expression = entry.getValue();

            try {
                Object result = shell.evaluate(expression);
                results.put(key, result);
            } catch (Exception e) {
                System.err.println("Error evaluating expression '" + key + "': " + expression);
                System.err.println("Error: " + e.getMessage());
                // Store the error as a string so Python can handle it
                results.put(key, "{{ERROR}}" + e.getMessage());
            }
        }

        return results;
    }

    /**
     * Main method to start Py4J gateway
     */
    public static void main(String[] args) {
        // Print JVM arguments for debugging
        System.out.println("JVM Arguments:");
        java.lang.management.ManagementFactory.getRuntimeMXBean().getInputArguments().forEach(System.out::println);

        // Read port from system property (default: 25333)
        int port = Integer.parseInt(System.getProperty("py4j.port", "25333"));
        System.out.println("Starting gateway on port: " + port);

        JavaBridge bridge = new JavaBridge();
        GatewayServer server = new GatewayServer(bridge, port);
        server.start();
        System.out.println("com.citi.gru.etl.JavaBridge Gateway Server Started on port " + port);
    }
}
