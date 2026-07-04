# DataPrep Documentation Index

**Last Updated:** 2026-06-13

Complete guide to all DataPrep documentation and when to use each one.

---

## Quick Navigation by Use Case

### "I want to add a new component"
→ **COMPONENT_IMPLEMENTATION_GUIDE.md**
- Step-by-step walkthrough
- Code templates and examples
- Testing patterns
- Registry integration
- Checklist before committing

### "Something is broken and I need to fix it"
→ **TROUBLESHOOTING.md**
- Quick diagnostics checklist
- Issue-by-issue solutions
- Debug logging setup
- Common error messages
- Stack trace interpretation

### "I need to write tests and meet 95% coverage"
→ **TESTING_STRATEGY.md**
- Test patterns (unit, integration, Java bridge)
- Coverage gate requirements and commands
- Fixture organization
- Mock strategies
- Test checklists
- Performance testing

### "Java bridge won't start or behaves weirdly"
→ **JAVA_BRIDGE_SETUP.md**
- Installation steps
- System requirements verification
- Build troubleshooting
- Port/firewall issues
- Memory/timeout problems
- Performance tuning

### "I need to configure a job or understand the JSON format"
→ **JOB_CONFIGURATION_SCHEMA.md**
- JSON structure reference
- All component types
- Configuration examples
- Flow/trigger syntax
- Schema definitions
- Context variables

---

## Document Overview

### 1. COMPONENT_IMPLEMENTATION_GUIDE.md (17 KB, 592 lines)

**Purpose:** Help developers build new engine components

**Contents:**
- When to add vs extend components
- Two component types: BaseComponent vs BaseIterateComponent
- 5-step implementation process with full code examples
- Unit test patterns (>= 95% coverage required)
- Integration test setup
- Common patterns (filters, aggregations, iterators)
- Troubleshooting component-specific issues
- Pre-commit checklist

**Use when:**
- Adding a new engine component
- Not sure about component architecture
- Need code templates and examples
- Writing component tests
- Debugging component behavior

**Time to read:** 15-20 minutes

---

### 2. TROUBLESHOOTING.md (25 KB, 600+ lines)

**Purpose:** Diagnose and fix issues quickly

**Sections:**
1. **Quick Diagnostics** — What to check first
2. **Converter Issues** — Unsupported components, schema mismatches, expression conversion
3. **Engine Execution Issues** — Missing components, empty DataFrames, execution errors
4. **Java Bridge Issues** — Startup failures, expression evaluation, Arrow serialization
5. **Data & Schema Issues** — Type mismatches, validation failures, encoding errors
6. **Expression Resolution** — {{java}} not working, ${context.var} replacement
7. **Performance Issues** — Slow execution, high memory, Java bridge bottlenecks
8. **File I/O Issues** — File not found, permission denied, encoding errors
9. **Context & GlobalMap Issues** — Variable scoping, persistence
10. **Testing & Coverage Issues** — Failing tests, coverage gaps, import errors

**Use when:**
- Something is broken and you need a quick fix
- Error message is unclear
- Need systematic diagnosis steps
- Want to understand why a feature isn't working
- Trying to improve performance

**Quick reference tables:**
- Common error messages with fixes
- Diagnosis commands by issue type
- Solution patterns for each category

**Time to read:** Read relevant section (5-10 minutes per issue)

---

### 3. TESTING_STRATEGY.md (26 KB, 700+ lines)

**Purpose:** Meet the 95% per-module line coverage gate

**Key Topics:**
1. **Coverage Gate Requirements** — Exact command, per-module measurement, exclusions
2. **Unit Testing Patterns** — 4 patterns with code examples
3. **Integration Testing Patterns** — Full pipeline testing, data integrity checks
4. **Java Bridge Testing** — Expression evaluation tests, tMap tests
5. **Fixtures & Test Data** — Organization, shared fixtures, temporary files
6. **Mocking Strategies** — File system, Java bridge, pandas
7. **Test Checklists** — Unit, integration, Java bridge, coverage
8. **Common Test Failures** — Debugging failing tests
9. **Performance Testing** — Benchmarks, memory usage

**Code Examples:**
- Component initialization tests
- Data processing tests
- Error handling tests
- Schema validation tests
- Full pipeline tests
- Java bridge tests

**Use when:**
- Writing tests for new/modified code
- Coverage report shows gaps
- Need test patterns to follow
- Debugging test failures
- Checking if your code meets coverage gate

**Time to read:** 20-25 minutes (or reference specific pattern)

---

### 4. JAVA_BRIDGE_SETUP.md (17 KB, 500+ lines)

**Purpose:** Set up, configure, and troubleshoot the Java bridge

**Sections:**
1. **What is the Java Bridge** — Architecture, use cases, tech stack
2. **System Requirements** — Java 11+, Python 3.12+, Maven 3.x
3. **Installation & Setup** — 3-step process (Python deps, build JAR, test)
4. **Configuration** — Basic and advanced settings
5. **Testing the Bridge** — Sanity checks, unit tests, integration tests
6. **Troubleshooting** — 8 common issues with diagnosis and fixes
7. **Advanced Configuration** — Custom functions, multiple instances, JVM options
8. **Performance Tuning** — Batch optimization, connection pooling, data transfer
9. **Monitoring & Debugging** — Logging, health checks, performance profiling

**Diagnostic Tools:**
- Quick sanity check commands
- Java version verification
- JAR build troubleshooting
- Port availability checks
- Memory monitoring
- Expression testing

**Use when:**
- Java bridge won't start
- Expressions aren't executing
- Getting "Bridge not available" errors
- Need to tune performance
- Setting up new environment
- JVM 11+ or Maven not installed

**Time to read:** 20-25 minutes (or reference specific issue)

---

### 5. JOB_CONFIGURATION_SCHEMA.md (19 KB, 550+ lines)

**Purpose:** Complete reference for job configuration JSON format

**Sections:**
1. **Overview** — What a job config contains
2. **Top-Level Structure** — Required/optional properties
3. **Components** — Structure, types, execution modes
4. **Flows & Triggers** — Connections, events, conditional execution
5. **Schema Definition** — Column types, properties, constraints
6. **Configuration Options** — Specific component configs with examples
7. **Context & Variables** — Variable definition and usage
8. **Java Bridge Configuration** — JVM settings
9. **Complete Examples** — 4 real-world examples

**Reference Tables:**
- All component properties
- Common component types (input, output, transform, etc.)
- Data types with examples
- Trigger events
- Configuration options per component

**Example Configs:**
1. Simple CSV read/write
2. Complex mapping with Java expressions
3. Multi-component with error handling
4. Aggregation pipeline

**Use when:**
- Creating or editing job.json files
- Unsure about component configuration
- Need to define schema
- Setting up Java bridge config
- Want to see config examples
- Validating JSON structure

**Quick Reference:**
- Component types list
- Data types list
- Flow examples
- Trigger examples
- Context variable examples

**Time to read:** 15-20 minutes (or reference specific component)

---

## How to Use This Documentation

### For New Team Members

**Week 1:**
1. Read COMPONENT_IMPLEMENTATION_GUIDE (understand architecture)
2. Read JAVA_BRIDGE_SETUP (understand Java bridge)
3. Read JOB_CONFIGURATION_SCHEMA (understand job configs)

**Week 2:**
1. Read TESTING_STRATEGY (understand testing requirements)
2. Read TROUBLESHOOTING (bookmark for later)

### For Day-to-Day Development

**When building features:**
1. Component guide → implementation pattern
2. Testing guide → test coverage requirements
3. Troubleshooting → debug issues

**When running jobs:**
1. Configuration schema → config reference
2. Troubleshooting → diagnosis steps

**When stuck:**
1. Troubleshooting → quick diagnostics
2. Check relevant guide for your use case

### Quick Reference Bookmarks

- **Configuration errors** → JOB_CONFIGURATION_SCHEMA.md
- **Component not working** → COMPONENT_IMPLEMENTATION_GUIDE.md
- **Tests failing** → TESTING_STRATEGY.md
- **Java bridge issues** → JAVA_BRIDGE_SETUP.md
- **General errors** → TROUBLESHOOTING.md

---

## Document Sizes & Reading Time

| Document | Size | Lines | Reading Time |
|----------|------|-------|--------------|
| COMPONENT_IMPLEMENTATION_GUIDE.md | 17 KB | 592 | 15-20 min |
| TROUBLESHOOTING.md | 25 KB | 600+ | 5-10 min per issue |
| TESTING_STRATEGY.md | 26 KB | 700+ | 20-25 min |
| JAVA_BRIDGE_SETUP.md | 17 KB | 500+ | 20-25 min |
| JOB_CONFIGURATION_SCHEMA.md | 19 KB | 550+ | 15-20 min |
| **TOTAL** | **104 KB** | **2,942** | **75-100 min complete** |

---

## Additional Resources

### Built-In Project Documentation

- **CLAUDE.md** — Project instructions (read first)
- **CODESPACE_SUMMARY.md** — Architecture overview
- **DataPrep_Architecture_Diagrams.pptx** — Visual architecture
- **README.md** — Quick start guide
- **docs/ARCHITECTURE.md** — Detailed architecture
- **docs/COMPONENT_REFERENCE.md** — All component inventory
- **docs/CONTRIBUTING.md** — Contribution guidelines
- **docs/DEPLOYMENT.md** — Production deployment

### External Resources

- **Apache Arrow** — `pyarrow.readthedocs.io`
- **Py4J** — `py4j.readthedocs.io`
- **Groovy** — `groovy-lang.org`
- **Pandas** — `pandas.pydata.org`
- **pytest** — `docs.pytest.org`

---

## Tips for Using This Documentation

1. **Use the quick navigation section** at the top to find the right guide
2. **Bookmark document URLs** for your frequent use cases
3. **Read the table of contents** to understand structure
4. **Use Ctrl+F (or Cmd+F)** to search within documents
5. **Look for numbered steps** for implementation tasks
6. **Check the checklists** before completing work
7. **Reference the examples** when creating your own configs
8. **Use the troubleshooting tables** for quick diagnosis

---

## Contributing to Documentation

When you discover:
- **New patterns** → Add to COMPONENT_IMPLEMENTATION_GUIDE.md
- **Common issues** → Add to TROUBLESHOOTING.md  
- **Test patterns** → Add to TESTING_STRATEGY.md
- **Bridge issues** → Add to JAVA_BRIDGE_SETUP.md
- **Config options** → Add to JOB_CONFIGURATION_SCHEMA.md

Keep documentation:
- ✓ Practical with code examples
- ✓ Well-organized with clear sections
- ✓ Up-to-date with current code
- ✓ Searchable with keywords
- ✓ Diagnostic (not just "what" but "why" and "how to fix")

---

## Document Version History

| Document | Created | Last Updated | Version |
|----------|---------|--------------|---------|
| COMPONENT_IMPLEMENTATION_GUIDE.md | 2026-06-13 | 2026-06-13 | 1.0 |
| TROUBLESHOOTING.md | 2026-06-13 | 2026-06-13 | 1.0 |
| TESTING_STRATEGY.md | 2026-06-13 | 2026-06-13 | 1.0 |
| JAVA_BRIDGE_SETUP.md | 2026-06-13 | 2026-06-13 | 1.0 |
| JOB_CONFIGURATION_SCHEMA.md | 2026-06-13 | 2026-06-13 | 1.0 |

---

## Support

If documentation is unclear or missing:

1. **Check related documents** — Cross-referenced in each guide
2. **Search across all docs** — Use consistent terminology
3. **Review code examples** — See actual usage in tests/
4. **File an issue** — Request documentation improvements
5. **Update documentation** — Add what you learn
6. **Ask the team** — Pair with someone familiar

---

**Start with the Quick Navigation section above based on what you're trying to do!**
