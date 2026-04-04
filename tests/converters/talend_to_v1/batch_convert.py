# Talend-to-V1 Batch Converter
# Add your converter commands below (one per line).
# Each line should be: INPUT_ITEM_FILE, OUTPUT_JSON_FILE
#
# Usage: Run this script from the recdataprep folder:
#   python batch_convert.py

import subprocess
import sys

# ============================================================
# PASTE YOUR CONVERSIONS BELOW as tuples: (input_item, output_json)
# ============================================================
conversions = [
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tAggregatedSortedRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tAggregatedSortedRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tAggregateRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tAggregateRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tChangeFileEncoding_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tChangeFileEncoding_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tContextLoad_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tContextLoad_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tDenormalize_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tDenormalize_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tExtractDelimitedFields_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tExtractDelimitedFields_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tExtractJSONFields_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tExtractJSONFields_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tExtractXMLFields_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tExtractXMLFields_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFileInputDelimited_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFileInputDelimited_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFileInputJSON_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFileInputJSON_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFileInputXML_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFileInputXML_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFileOutputDelimited_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFileOutputDelimited_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFileRowCount_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFileRowCount_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFilterColumns_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFilterColumns_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFilterRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFilterRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tFixedFlowInput_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tFixedFlowInput_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tJavaRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tJavaRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tJoin_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tJoin_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tMap_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tMap_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tNormalize_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tNormalize_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tPivotToColumnsDelimited_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tPivotToColumnsDelimited_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tReplace_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tReplace_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tReplicate_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tReplicate_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tRowGenerator_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tRowGenerator_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tSchemaComplianceCheck_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tSchemaComplianceCheck_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tSetGlobalVar_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tSetGlobalVar_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tSortRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tSortRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tUniqRow_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tUniqRow_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tUnite_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tUnite_0.1.json"),
    (r"C:\Softwares\TOS_DI-20211109_1610-V8.0.1\TOS_DI-20211109_1610-V8.0.1\workspace\RECON_ETL\process\Job_tXMLMap_0.1.item", r"C:\Users\phani\Documents\JSON\Job_tXMLMap_0.1.json"),
]

def main():
    total = len(conversions)
    passed = 0
    failed = 0
    errors = []

    print(f"Starting batch conversion: {total} jobs\n")

    for i, (input_file, output_file) in enumerate(conversions, 1):
        job_name = input_file.split("\\")[-1]
        print(f"[{i}/{total}] Converting {job_name} ... ", end="", flush=True)
        
        result = subprocess.run(
            [sys.executable, "-m", "src.converters.talend_to_v1.converter", input_file, output_file],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("OK")
            passed += 1
        else:
            print("FAILED")
            failed += 1
            errors.append((job_name, result.stderr.strip()))
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {total} total")
    
    if errors:
        print(f"\nFailed jobs:")
        for name, err in errors:
            print(f"  - {name}: {err[:200]}")

if __name__ == "__main__":
    main()
