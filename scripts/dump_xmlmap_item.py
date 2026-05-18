"""Dump tXMLMap nodeData structure from a Talend .item file."""
import xml.etree.ElementTree as ET
import sys

ITEM = r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Nested_XMLMap_0.1.item"

KEYS = ("name", "xpath", "loop", "main", "nodeType", "expression",
        "expressionFilter", "activateExpressionFilter", "allInOne",
        "source", "target", "sourceExpression")

def walk(el, depth=0):
    attrs = {k: v for k, v in el.attrib.items() if k in KEYS}
    print("  " * depth + f"<{el.tag}> {attrs}")
    for child in el:
        walk(child, depth + 1)

tree = ET.parse(ITEM)
root = tree.getroot()

for node in root.findall('.//node[@componentName="tXMLMap"]'):
    nd = node.find("./nodeData")
    if nd is None:
        print("NO nodeData found")
        sys.exit(1)

    print("=== inputTrees ===")
    for it in nd.findall("./inputTrees"):
        walk(it)

    print("\n=== outputTrees ===")
    for ot in nd.findall("./outputTrees"):
        walk(ot)

    print("\n=== connections (source -> target, expr) ===")
    for c in nd.findall("./connections"):
        print(f"  {c.get('source')}")
        print(f"  -> {c.get('target')}")
        expr = c.get("sourceExpression", "")
        if expr:
            print(f"     expr={expr}")
        print()
