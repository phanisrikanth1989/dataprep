package com.citi.gru.etl;

import org.apache.arrow.memory.BufferAllocator;
import org.apache.arrow.memory.RootAllocator;
import org.apache.arrow.vector.*;
import org.apache.arrow.vector.ipc.ArrowStreamReader;
import org.apache.arrow.vector.ipc.ArrowStreamWriter;
import groovy.lang.Binding;
import groovy.lang.GroovyShell;
import groovy.lang.Script;
import py4j.GatewayServer;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Java bridge server for executing Java/Groovy expressions on Arrow data.
 *
 * <p>Communicates with the Python engine via Py4J. Receives Arrow-serialized
 * DataFrames, executes Groovy scripts per-row or in batch, and returns
 * Arrow-serialized results. Context and globalMap are synchronised
 * bi-directionally with the Python side at every call boundary.
 *
 * <p>Key design choices (Phase 2 rewrite):
 * <ul>
 *   <li>All Arrow vector operations delegate to {@link ArrowSerializer}</li>
 *   <li>Compiled tMap scripts cache the Script <b>class</b>, not the instance,
 *       so each execution creates a fresh instance with its own Binding
 *       (fixes BRDG-06 -- no synchronized(script) bottleneck)</li>
 *   <li>All logging via java.util.logging with {@code [JavaBridge]} prefix (D-14, D-15)</li>
 *   <li>Zero println statements -- all output via java.util.logging</li>
 * </ul>
 */
public class JavaBridge {

    private static final Logger logger = Logger.getLogger(JavaBridge.class.getName());

    private final BufferAllocator allocator = new RootAllocator(Long.MAX_VALUE);
    private Map<String, Object> context = new HashMap<>();
    private Map<String, Object> globalMap = new HashMap<>();
    private GroovyShell groovyShell;
    private final Map<String, Class<?>> loadedRoutines = new HashMap<>();

    /**
     * Cache of compiled tMap Script *classes* keyed by component ID.
     *
     * <p>BRDG-06 fix: we cache the Class, not the Script instance. Each
     * execution instantiates a new Script from the cached class, giving it
     * its own Binding. This eliminates the need for {@code synchronized(script)}
     * and allows truly parallel chunk execution.
     */
    private final ConcurrentHashMap<String, CachedTMapMeta> compiledScriptClasses = new ConcurrentHashMap<>();

    // ------------------------------------------------------------------
    // Inner class for compiled tMap metadata
    // ------------------------------------------------------------------

    /**
     * Holds a compiled Script class together with the output schema metadata
     * needed to convert script results back to Arrow.
     */
    private static class CachedTMapMeta {
        final Class<? extends Script> scriptClass;
        final Map<String, List<String>> outputSchemas;
        final Map<String, String> outputTypes;
        final String mainTableName;
        final List<String> lookupNames;

        CachedTMapMeta(Class<? extends Script> scriptClass,
                       Map<String, List<String>> outputSchemas,
                       Map<String, String> outputTypes,
                       String mainTableName,
                       List<String> lookupNames) {
            this.scriptClass = scriptClass;
            this.outputSchemas = outputSchemas;
            this.outputTypes = outputTypes;
            this.mainTableName = mainTableName;
            this.lookupNames = lookupNames;
        }
    }

    // ------------------------------------------------------------------
    // Constructor
    // ------------------------------------------------------------------

    public JavaBridge() {
        Binding binding = new Binding();
        this.groovyShell = new GroovyShell(binding);
        logger.info("[JavaBridge] Bridge instance created");
    }

    // ------------------------------------------------------------------
    // Logging configuration
    // ------------------------------------------------------------------

    /**
     * Set the JUL log level from a Python-side level name.
     *
     * @param levelName one of "FINE", "INFO", "WARNING", "SEVERE"
     */
    public void setLogLevel(String levelName) {
        Level level;
        switch (levelName.toUpperCase()) {
            case "FINE":
            case "DEBUG":
                level = Level.FINE;
                break;
            case "INFO":
                level = Level.INFO;
                break;
            case "WARNING":
            case "WARN":
                level = Level.WARNING;
                break;
            case "SEVERE":
            case "ERROR":
                level = Level.SEVERE;
                break;
            default:
                level = Level.INFO;
                break;
        }
        Logger.getLogger("com.citi.gru.etl").setLevel(level);
        logger.info("[JavaBridge] Log level set to " + level.getName());
    }

    // ------------------------------------------------------------------
    // Context / GlobalMap accessors
    // ------------------------------------------------------------------

    public Map<String, Object> getContext() {
        return this.context;
    }

    public Map<String, Object> getGlobalMap() {
        return this.globalMap;
    }

    public void setContext(String key, String value) {
        this.context.put(key, value);
    }

    public void setGlobalMap(String key, String value) {
        this.globalMap.put(key, value);
    }

    // ------------------------------------------------------------------
    // Row-level execution (tJavaRow)
    // ------------------------------------------------------------------

    /**
     * Execute tJavaRow-style Groovy code on every row of the input Arrow data.
     *
     * @param arrowData     input DataFrame serialised as Arrow IPC bytes
     * @param javaCode      Groovy source code to execute per row
     * @param outputSchema  output column types: {colName: pythonTypeString}
     * @param contextVars   context variables to merge
     * @param globalMapVars globalMap variables to merge
     * @return Arrow IPC bytes containing the output DataFrame
     */
    public byte[] executeJavaRow(byte[] arrowData, String javaCode,
                                 Map<String, String> outputSchema,
                                 Map<String, Object> contextVars,
                                 Map<String, Object> globalMapVars) throws Exception {

        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();

        // Output arrays -- one per output column
        Map<String, Object[]> outputArrays = new HashMap<>();
        for (String colName : outputSchema.keySet()) {
            outputArrays.put(colName, new Object[rowCount]);
        }

        // Compile script once
        logger.fine("[JavaBridge] Compiling Groovy script for executeJavaRow");
        long compileStart = System.currentTimeMillis();
        Script compiledScript = groovyShell.parse(javaCode);
        // Cache the class so we can create independent instances per row
        Class<? extends Script> scriptClass = compiledScript.getClass();
        long compileTime = System.currentTimeMillis() - compileStart;
        logger.fine("[JavaBridge] Script compiled in " + compileTime + " ms");

        logger.info("[JavaBridge] executeJavaRow: processing " + rowCount + " rows");
        long execStart = System.currentTimeMillis();

        for (int i = 0; i < rowCount; i++) {
            try {
                // Create a fresh Script instance per row (no synchronization needed)
                Script rowScript = scriptClass.getDeclaredConstructor().newInstance();

                // Build input row map from Arrow vectors
                Map<String, Object> inputRowMap = new HashMap<>();
                for (FieldVector vec : inputRoot.getFieldVectors()) {
                    String fieldName = vec.getName();
                    inputRowMap.put(fieldName, vec.isNull(i) ? null : vec.getObject(i));
                }

                RowWrapper input_row = new RowWrapper();
                input_row.setInputRow(inputRowMap);

                RowWrapper output_row = new RowWrapper();

                Binding binding = new Binding();
                binding.setVariable("input_row", input_row);
                binding.setVariable("output_row", output_row);
                binding.setVariable("context", context);
                binding.setVariable("globalMap", globalMap);

                // Add loaded routines
                addRoutinesToBinding(binding);

                rowScript.setBinding(binding);
                rowScript.run();

                // Collect output values from the output row map (not the input side)
                Map<String, Object> outputValues = output_row.getOutputRow();
                for (String colName : outputSchema.keySet()) {
                    outputArrays.get(colName)[i] = outputValues.get(colName);
                }
            } catch (Exception e) {
                logger.severe("[JavaBridge] Error processing row " + i + ": " + e.getMessage());
                throw new RuntimeException("Error processing row " + i, e);
            }
        }

        long execTime = System.currentTimeMillis() - execStart;
        logger.info("[JavaBridge] executeJavaRow: processed " + rowCount + " rows in " + execTime + " ms");

        // Create output Arrow data via ArrowSerializer
        VectorSchemaRoot outputRoot = ArrowSerializer.createOutputRootFromData(allocator, outputArrays, outputSchema);

        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
        writer.writeBatch();
        writer.close();

        inputRoot.close();
        reader.close();
        outputRoot.close();

        return outputStream.toByteArray();
    }

    // ------------------------------------------------------------------
    // One-time expression execution
    // ------------------------------------------------------------------

    /**
     * Evaluate a single Groovy expression with context/globalMap binding.
     *
     * @param expression  Groovy expression source
     * @param contextVars context variables to merge
     * @return the expression result
     */
    public Object executeOneTimeExpression(String expression, Map<String, Object> contextVars) {
        this.context.putAll(contextVars);

        Binding binding = new Binding();
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);
        addRoutinesToBinding(binding);

        GroovyShell shell = new GroovyShell(binding);
        return shell.evaluate(expression);
    }

    /**
     * Evaluate multiple Groovy expressions in batch with context and globalMap.
     *
     * <p>Renamed from {@code executeBatchOneTimeExpressionsWithGlobalMap} --
     * the dead-code variant without globalMap has been removed.
     *
     * @param expressions  map of {key: expressionString}
     * @param contextVars  context variables to merge
     * @param globalMapVars globalMap variables to merge
     * @return map of {key: resultValue}; errors stored as "{{ERROR}}message"
     */
    public Map<String, Object> executeBatchOneTimeExpressions(
            Map<String, String> expressions,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) {

        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        Binding binding = new Binding();
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);
        addRoutinesToBinding(binding);

        GroovyShell shell = new GroovyShell(binding);

        Map<String, Object> results = new HashMap<>();
        for (Map.Entry<String, String> entry : expressions.entrySet()) {
            String key = entry.getKey();
            String expression = entry.getValue();
            try {
                Object result = shell.evaluate(expression);
                results.put(key, result);
            } catch (Exception e) {
                logger.severe("[JavaBridge] Error evaluating expression '" + key + "': " + expression
                        + " -- " + e.getMessage());
                results.put(key, "{{ERROR}}" + e.getMessage());
            }
        }
        return results;
    }

    /**
     * Backward-compatible alias so existing Python client code that calls
     * {@code executeBatchOneTimeExpressionsWithGlobalMap} keeps working.
     */
    public Map<String, Object> executeBatchOneTimeExpressionsWithGlobalMap(
            Map<String, String> expressions,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) {
        return executeBatchOneTimeExpressions(expressions, contextVars, globalMapVars);
    }

    // ------------------------------------------------------------------
    // tMap preprocessing
    // ------------------------------------------------------------------

    /**
     * Batch-evaluate expressions on every row of the input Arrow data.
     *
     * @param arrowData     input DataFrame as Arrow IPC bytes
     * @param expressions   {exprId: expressionString}
     * @param mainTableName main table name for Groovy binding
     * @param lookupNames   lookup table names already joined
     * @param contextVars   context variables
     * @param globalMapVars globalMap variables
     * @return {exprId: Object[resultPerRow]}
     */
    public Map<String, Object[]> executeTMapPreprocessing(
            byte[] arrowData,
            Map<String, String> expressions,
            String mainTableName,
            List<String> lookupNames,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {

        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();
        logger.info("[JavaBridge] tMap preprocessing: " + rowCount + " rows, " + expressions.size() + " expressions");

        // Compile all expressions once
        logger.fine("[JavaBridge] Compiling " + expressions.size() + " expressions");
        Map<String, Class<? extends Script>> compiledExprClasses = new HashMap<>();
        GroovyShell compileShell = new GroovyShell();

        for (Map.Entry<String, String> entry : expressions.entrySet()) {
            String exprId = entry.getKey();
            String expression = entry.getValue();
            try {
                Script compiled = compileShell.parse(expression);
                compiledExprClasses.put(exprId, compiled.getClass());
            } catch (Exception e) {
                logger.severe("[JavaBridge] Error compiling expression '" + exprId + "': " + e.getMessage());
            }
        }

        // Result arrays
        Map<String, Object[]> results = new HashMap<>();
        for (String exprId : expressions.keySet()) {
            results.put(exprId, new Object[rowCount]);
        }

        long execStart = System.currentTimeMillis();

        for (int i = 0; i < rowCount; i++) {
            // Build row wrappers that read from Arrow vectors
            RowWrapper mainRow = buildArrowRowWrapper(inputRoot, i, mainTableName);

            Binding binding = new Binding();
            binding.setVariable(mainTableName, mainRow);

            for (String lookupName : lookupNames) {
                RowWrapper lookupRow = buildArrowRowWrapper(inputRoot, i, lookupName);
                binding.setVariable(lookupName, lookupRow);
            }

            binding.setVariable("context", context);
            binding.setVariable("globalMap", globalMap);
            addRoutinesToBinding(binding);

            for (Map.Entry<String, Class<? extends Script>> entry : compiledExprClasses.entrySet()) {
                String exprId = entry.getKey();
                try {
                    Script instance = entry.getValue().getDeclaredConstructor().newInstance();
                    instance.setBinding(binding);
                    Object result = instance.run();
                    results.get(exprId)[i] = result;
                } catch (Exception e) {
                    logger.fine("[JavaBridge] Error evaluating '" + exprId + "' at row " + i + ": " + e.getMessage());
                    results.get(exprId)[i] = null;
                }
            }
        }

        long execTime = System.currentTimeMillis() - execStart;
        logger.info("[JavaBridge] tMap preprocessing complete: " + rowCount + " rows in " + execTime + " ms");

        inputRoot.close();
        reader.close();

        return results;
    }

    // ------------------------------------------------------------------
    // tMap compiled execution
    // ------------------------------------------------------------------

    /**
     * Compile and execute a tMap script in a single call (non-cached).
     *
     * @param javaScript    Groovy source for the tMap logic
     * @param arrowData     joined DataFrame as Arrow IPC bytes
     * @param outputSchemas {outputName: [columnNames]}
     * @param outputTypes   {outputName_columnName: pythonTypeString}
     * @param mainTableName main input table name
     * @param lookupNames   lookup table names
     * @param contextVars   context variables
     * @param globalMapVars globalMap variables
     * @return {outputName: arrowBytes}
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

        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();
        logger.info("[JavaBridge] tMap compiled: " + rowCount + " rows, " + outputSchemas.size() + " outputs");

        // Compile script
        Binding compileBinding = buildTMapBinding(inputRoot, rowCount, mainTableName,
                lookupNames, outputSchemas, outputTypes);
        GroovyShell shell = new GroovyShell(compileBinding);
        Script compiledScript = shell.parse(javaScript);
        compiledScript.setBinding(compileBinding);

        long execStart = System.currentTimeMillis();
        Object scriptResult = compiledScript.run();
        long execTime = System.currentTimeMillis() - execStart;
        logger.info("[JavaBridge] tMap compiled: executed in " + execTime + " ms");

        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> outputResults = (Map<String, Map<String, Object>>) scriptResult;

        inputRoot.close();
        reader.close();

        return convertTMapOutputsToArrow(outputResults, outputSchemas, outputTypes);
    }

    /**
     * Compile a tMap script and cache the Script CLASS for repeated execution.
     * (Step 1 of the compile-once execute-many pattern.)
     *
     * <p>BRDG-06 fix: caches {@code script.getClass()} rather than the Script
     * instance. Each {@link #executeCompiledTMap} call creates a new instance
     * from the cached class with its own Binding -- no synchronized block needed.
     *
     * @param componentId  unique component ID (e.g. "tMap_1")
     * @param javaScript   Groovy source for the tMap logic
     * @param outputSchemas {outputName: [columnNames]}
     * @param outputTypes   {outputName_columnName: pythonTypeString}
     * @param mainTableName main input table name
     * @param lookupNames   lookup table names
     * @return componentId (confirmation)
     */
    public String compileTMapScript(
            String componentId,
            String javaScript,
            Map<String, List<String>> outputSchemas,
            Map<String, String> outputTypes,
            String mainTableName,
            List<String> lookupNames) throws Exception {

        logger.info("[JavaBridge] Compiling tMap script for component: " + componentId);
        long compileStart = System.currentTimeMillis();

        Binding compileBinding = new Binding();
        addRoutinesToBinding(compileBinding);
        compileBinding.setVariable("outputSchemas", outputSchemas);
        compileBinding.setVariable("outputTypes", outputTypes);

        GroovyShell shell = new GroovyShell(compileBinding);
        Script compiledScript = shell.parse(javaScript);

        long compileTime = System.currentTimeMillis() - compileStart;
        logger.info("[JavaBridge] Script compiled in " + compileTime + " ms");

        // Cache the Script CLASS, not the instance (BRDG-06 fix)
        @SuppressWarnings("unchecked")
        Class<? extends Script> scriptClass = (Class<? extends Script>) compiledScript.getClass();

        CachedTMapMeta meta = new CachedTMapMeta(
                scriptClass, outputSchemas, outputTypes, mainTableName, lookupNames);
        compiledScriptClasses.put(componentId, meta);

        logger.info("[JavaBridge] Cached compiled script class for: " + componentId);
        return componentId;
    }

    /**
     * Execute a previously compiled tMap script on a chunk of data.
     * (Step 2 of the compile-once execute-many pattern.)
     *
     * @param componentId  component ID used during compilation
     * @param arrowData    joined DataFrame chunk as Arrow IPC bytes
     * @param contextVars  context variables
     * @param globalMapVars globalMap variables
     * @return {outputName: arrowBytes}
     */
    public Map<String, byte[]> executeCompiledTMap(
            String componentId,
            byte[] arrowData,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {

        CachedTMapMeta meta = compiledScriptClasses.get(componentId);
        if (meta == null) {
            throw new IllegalArgumentException(
                    "[JavaBridge] No compiled script found for component: " + componentId
                            + ". Call compileTMapScript() first!");
        }

        this.context.putAll(contextVars);
        this.globalMap.putAll(globalMapVars);

        ByteArrayInputStream inputStream = new ByteArrayInputStream(arrowData);
        ArrowStreamReader reader = new ArrowStreamReader(inputStream, allocator);
        VectorSchemaRoot inputRoot = reader.getVectorSchemaRoot();
        reader.loadNextBatch();

        int rowCount = inputRoot.getRowCount();
        logger.info("[JavaBridge] Executing compiled " + componentId + ": " + rowCount + " rows");

        // Create a FRESH Script instance from the cached class (BRDG-06 -- no synchronization)
        Script scriptInstance = meta.scriptClass.getDeclaredConstructor().newInstance();

        Binding execBinding = buildTMapBinding(inputRoot, rowCount, meta.mainTableName,
                meta.lookupNames, meta.outputSchemas, meta.outputTypes);
        scriptInstance.setBinding(execBinding);

        long execStart = System.currentTimeMillis();
        Object scriptResult = scriptInstance.run();
        long execTime = System.currentTimeMillis() - execStart;
        logger.info("[JavaBridge] Executed " + componentId + " in " + execTime + " ms");

        @SuppressWarnings("unchecked")
        Map<String, Map<String, Object>> outputResults = (Map<String, Map<String, Object>>) scriptResult;

        inputRoot.close();
        reader.close();

        return convertTMapOutputsToArrow(outputResults, meta.outputSchemas, meta.outputTypes);
    }

    /**
     * Execute pre-compiled tMap script on chunked data.
     * Same as {@link #executeCompiledTMap} -- kept for backward compatibility
     * with Python client code that calls this method name.
     */
    public Map<String, byte[]> executeCompiledTMapChunked(
            String componentId,
            byte[] arrowData,
            Map<String, Object> contextVars,
            Map<String, Object> globalMapVars) throws Exception {
        return executeCompiledTMap(componentId, arrowData, contextVars, globalMapVars);
    }

    // ------------------------------------------------------------------
    // Routine / library management
    // ------------------------------------------------------------------

    /**
     * Load a custom routine class by fully-qualified name.
     *
     * @param className fully-qualified class name (e.g. "com.example.MyRoutine")
     */
    public void loadRoutine(String className) throws Exception {
        Class<?> routineClass = Class.forName(className);
        String simpleName = routineClass.getSimpleName();
        loadedRoutines.put(simpleName, routineClass);
        logger.info("[JavaBridge] Loaded routine: " + simpleName + " (" + className + ")");
    }

    /**
     * Validate that required libraries are available.
     *
     * <p>BRDG-04 fix: instead of string-contains on classpath, checks actual
     * file existence for each library path AND attempts {@code Class.forName()}
     * for known entry-point classes.
     *
     * @param libraryPaths list of JAR file paths or filenames to validate
     * @return list of missing/invalid libraries (empty if all are available)
     */
    public List<String> validateLibraries(List<String> libraryPaths) {
        List<String> missing = new ArrayList<>();
        if (libraryPaths == null || libraryPaths.isEmpty()) {
            return missing;
        }

        logger.info("[JavaBridge] Validating " + libraryPaths.size() + " libraries");

        for (String libraryPath : libraryPaths) {
            boolean found = false;

            // Strategy 1: Check if it's an absolute/relative path to a JAR file
            File file = new File(libraryPath);
            if (file.exists() && file.isFile()) {
                found = true;
                logger.fine("[JavaBridge] Library file found: " + libraryPath);
            }

            // Strategy 2: Try to load as a class name (for class-based validation)
            if (!found) {
                try {
                    Class.forName(libraryPath, false, this.getClass().getClassLoader());
                    found = true;
                    logger.fine("[JavaBridge] Library class loaded: " + libraryPath);
                } catch (ClassNotFoundException e) {
                    // Not a class -- check classpath entries
                }
            }

            // Strategy 3: Check classpath entries for JAR filename match
            if (!found) {
                String classpath = System.getProperty("java.class.path", "");
                String[] entries = classpath.split(File.pathSeparator);
                for (String entry : entries) {
                    File cpFile = new File(entry);
                    if (cpFile.getName().equals(libraryPath) || entry.endsWith(libraryPath)) {
                        if (cpFile.exists()) {
                            found = true;
                            logger.fine("[JavaBridge] Library found on classpath: " + libraryPath);
                            break;
                        }
                    }
                }
            }

            if (!found) {
                logger.warning("[JavaBridge] Missing library: " + libraryPath);
                missing.add(libraryPath);
            }
        }

        return missing;
    }

    // ------------------------------------------------------------------
    // Private helpers
    // ------------------------------------------------------------------

    /**
     * Add loaded routine classes to a Groovy binding in two ways:
     * 1. Direct: {@code ValidationUtils.method()}
     * 2. Namespace: {@code routines.ValidationUtils.method()}
     */
    private void addRoutinesToBinding(Binding binding) {
        for (Map.Entry<String, Class<?>> entry : loadedRoutines.entrySet()) {
            binding.setVariable(entry.getKey(), entry.getValue());
        }
        Map<String, Class<?>> routinesNamespace = new HashMap<>(loadedRoutines);
        binding.setVariable("routines", routinesNamespace);
    }

    /**
     * Build a Groovy Binding pre-populated with tMap execution variables.
     */
    private Binding buildTMapBinding(VectorSchemaRoot inputRoot, int rowCount,
                                     String mainTableName, List<String> lookupNames,
                                     Map<String, List<String>> outputSchemas,
                                     Map<String, String> outputTypes) {
        Binding binding = new Binding();
        binding.setVariable("inputRoot", inputRoot);
        binding.setVariable("rowCount", rowCount);
        binding.setVariable("mainTableName", mainTableName);
        binding.setVariable("lookupNames", lookupNames);
        binding.setVariable("context", context);
        binding.setVariable("globalMap", globalMap);
        binding.setVariable("allocator", allocator);
        binding.setVariable("outputSchemas", outputSchemas);
        binding.setVariable("outputTypes", outputTypes);
        addRoutinesToBinding(binding);
        return binding;
    }

    /**
     * Build a RowWrapper that reads column values from Arrow vectors at a given row index.
     * Column lookup supports both "tableName.colName" and plain "colName" conventions.
     */
    private RowWrapper buildArrowRowWrapper(VectorSchemaRoot root, int rowIndex, String tableName) {
        RowWrapper wrapper = new RowWrapper();
        Map<String, Object> rowMap = new HashMap<>();

        for (FieldVector vec : root.getFieldVectors()) {
            String fieldName = vec.getName();
            Object value = vec.isNull(rowIndex) ? null : vec.getObject(rowIndex);

            // Store under plain name
            rowMap.put(fieldName, value);

            // Also store under unprefixed name if field has tableName prefix
            if (tableName != null && fieldName.startsWith(tableName + ".")) {
                String shortName = fieldName.substring(tableName.length() + 1);
                rowMap.put(shortName, value);
            }
        }

        wrapper.setInputRow(rowMap);
        return wrapper;
    }

    /**
     * Convert tMap script output results to Arrow IPC byte arrays.
     */
    private Map<String, byte[]> convertTMapOutputsToArrow(
            Map<String, Map<String, Object>> outputResults,
            Map<String, List<String>> outputSchemas,
            Map<String, String> outputTypes) throws Exception {

        Map<String, byte[]> outputArrowData = new HashMap<>();

        for (Map.Entry<String, Map<String, Object>> entry : outputResults.entrySet()) {
            String outputName = entry.getKey();
            Map<String, Object> outputResult = entry.getValue();

            // Skip __errors__ metadata
            if ("__errors__".equals(outputName)) {
                continue;
            }

            Object[][] data = (Object[][]) outputResult.get("data");
            int count = ((Number) outputResult.get("count")).intValue();
            List<String> columnNames = outputSchemas.get(outputName);

            logger.fine("[JavaBridge] Output '" + outputName + "': " + count + " rows, "
                    + columnNames.size() + " columns");

            // Build schema map for this output
            Map<String, String> schema = new HashMap<>();
            for (String colName : columnNames) {
                String typeKey = outputName + "_" + colName;
                String colType = outputTypes.get(typeKey);
                schema.put(colName, colType);
            }

            // Convert Object[][] to column-oriented Object[]
            Map<String, Object[]> columnData = new HashMap<>();
            for (int colIdx = 0; colIdx < columnNames.size(); colIdx++) {
                String colName = columnNames.get(colIdx);
                Object[] colValues = new Object[count];
                for (int rowIdx = 0; rowIdx < count; rowIdx++) {
                    colValues[rowIdx] = data[rowIdx][colIdx];
                }
                columnData.put(colName, colValues);
            }

            // Create Arrow output via ArrowSerializer
            VectorSchemaRoot outputRoot = ArrowSerializer.createOutputRootFromData(allocator, columnData, schema);

            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            ArrowStreamWriter writer = new ArrowStreamWriter(outputRoot, null, outputStream);
            writer.writeBatch();
            writer.close();

            outputArrowData.put(outputName, outputStream.toByteArray());
            outputRoot.close();
        }

        return outputArrowData;
    }

    // ------------------------------------------------------------------
    // Entry point
    // ------------------------------------------------------------------

    /**
     * Start the Py4J Gateway server.
     *
     * @param args JVM system property {@code py4j.port} controls the listen port (default 25333)
     */
    public static void main(String[] args) {
        int port = Integer.parseInt(System.getProperty("py4j.port", "25333"));

        JavaBridge bridge = new JavaBridge();
        GatewayServer server = new GatewayServer(bridge, port);
        server.start();

        logger.info("[JavaBridge] [OK] Gateway server started on port " + port);
    }
}
