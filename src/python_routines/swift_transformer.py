"""
SWIFT Message Transformer
Reads YAML configuration and processes input files to produce pipe-delimited output.

Usage:
    python swift_transformer.py --config config.yaml --input input.txt --output output.txt
    python swift_transformer.py --config config.yaml --input input.txt --output output.txt --input-delimiter "|"
"""

import yaml
import re
import argparse
from datetime import datetime
from typing import Dict, Any, Optional


# =============================================================================
# HELPER FUNCTIONS - Readable alternatives to lambda expressions
# =============================================================================

def safe_str(value: Any) -> str:
    """Safely convert value to string, handling None/empty."""
    if value is None:
        return ''
    return str(value)


def safe_get(input_row: Dict, field: str) -> str:
    """Safely get a field from input_row as string."""
    return safe_str(input_row.get(field, ''))


def substring(s: str, start: int, end: Optional[int] = None) -> str:
    """Safe substring extraction - won't error on short strings."""
    if not s:
        return ''
    if end is None:
        return s[start:]
    return s[start:end]


def char_at(s: str, index: int) -> str:
    """Get character at index, empty string if out of bounds."""
    if s and len(s) > index:
        return s[index]
    return ''


def extract_decimal(s: str) -> str:
    """Extract first decimal number from string."""
    if not s:
        return '0.00'
    s = s.replace(',', '.')
    match = re.search(r'[\d.]+', s)
    return match.group() if match else '0.00'


def count_significant_digits(s: str) -> int:
    """Count digits that are not 0 or decimal point."""
    return len(re.sub(r'[0.]', '', s))


# =============================================================================
# FIELD EXTRACTION FUNCTIONS
# =============================================================================

def get_temp2(input_row: Dict) -> str:
    """TEMP2: Column 3 value"""
    return safe_get(input_row, 'COLUMN3')


def get_temp6(input_row: Dict) -> str:
    """TEMP6: Extract sfield9 value from block4_61"""
    v = safe_get(input_row, 'block4_61')
    if v and 'sfield9=' in v:
        return v[v.find('sfield9=') + 8:]
    return ''


def get_side(input_row: Dict) -> str:
    """SIDE: Always 'S'"""
    return 'S'


def get_termid(input_row: Dict) -> str:
    """TERMID: block2bic with position 8 removed"""
    v = safe_get(input_row, 'block2bic')
    if v and len(v) > 9:
        return v[:8] + v[9:]
    return ''


def get_destid(input_row: Dict) -> str:
    """DESTID: block1bic with position 8 removed"""
    v = safe_get(input_row, 'block1bic')
    if v and len(v) > 9:
        return v[:8] + v[9:]
    return ''


def get_the3ref(input_row: Dict) -> str:
    """THE3REF: block4_20 transaction reference"""
    return safe_get(input_row, 'block4_20')


def get_subacc(input_row: Dict) -> str:
    """SUBACC: block4_25 account identifier"""
    v = safe_get(input_row, 'block4_25')
    return '40000202' if v == '40000202' else v


def get_stmtno(input_row: Dict) -> str:
    """STMTNO: Statement number from block4_28C (before /)"""
    v = safe_get(input_row, 'block4_28C')
    if v and '/' in v:
        return v[:v.find('/')]
    return v


def get_stmtgp(input_row: Dict) -> str:
    """STMTGP: Statement page from block4_28C (after /)"""
    v = safe_get(input_row, 'block4_28C')
    if v and '/' in v:
        return v[v.find('/') + 1:]
    return ''


def get_ivaluedate(input_row: Dict) -> str:
    """IVALUEDATE: Value date from block4_61 (first 6 digits)"""
    v = safe_get(input_row, 'block4_61')
    if v and len(v) >= 6 and v[:6].isdigit():
        return v[:6]
    return ''


def get_opbalsign(input_row: Dict) -> str:
    """OPBALSIGN: Opening balance sign (C/D)"""
    f = safe_get(input_row, 'block4_60F')
    m = safe_get(input_row, 'block4_60M')
    if f:
        return char_at(f, 0)
    if m:
        return char_at(m, 0)
    return ''


def get_opbaltp(input_row: Dict) -> str:
    """OPBALTP: Opening balance type (F or M)"""
    return 'F' if safe_get(input_row, 'block4_60F') else 'M'


def get_opbaldate(input_row: Dict) -> str:
    """OPBALDATE: Opening balance date"""
    f = safe_get(input_row, 'block4_60F')
    m = safe_get(input_row, 'block4_60M')
    if f and len(f) >= 7:
        return f[1:7]
    if m and len(m) >= 7:
        return m[1:7]
    return ''


def get_opbalcy(input_row: Dict) -> str:
    """OPBALCY: Opening balance currency"""
    f = safe_get(input_row, 'block4_60F')
    m = safe_get(input_row, 'block4_60M')
    if f and len(f) >= 10:
        return f[7:10]
    if m and len(m) >= 10:
        return m[7:10]
    return ''


def get_opbal(input_row: Dict) -> str:
    """OPBAL: Opening balance amount"""
    f = safe_get(input_row, 'block4_60F')
    m = safe_get(input_row, 'block4_60M')
    if f and len(f) > 10:
        return f[10:].replace(',', '.')
    if m and len(m) > 10:
        return m[10:].replace(',', '.')
    return ''


def get_clbalsign(input_row: Dict) -> str:
    """CLBALSIGN: Closing balance sign (C/D)"""
    f = safe_get(input_row, 'block4_62F')
    m = safe_get(input_row, 'block4_62M')
    if f:
        return char_at(f, 0)
    if m:
        return char_at(m, 0)
    return ''


def get_clbaltp(input_row: Dict) -> str:
    """CLBALTP: Closing balance type (F or M)"""
    return 'F' if safe_get(input_row, 'block4_62F') else 'M'


def get_clbaldate(input_row: Dict) -> str:
    """CLBALDATE: Closing balance date"""
    f = safe_get(input_row, 'block4_62F')
    m = safe_get(input_row, 'block4_62M')
    if f and len(f) >= 7:
        return f[1:7]
    if m and len(m) >= 7:
        return m[1:7]
    return ''


def get_clbalcy(input_row: Dict) -> str:
    """CLBALCY: Closing balance currency"""
    f = safe_get(input_row, 'block4_62F')
    m = safe_get(input_row, 'block4_62M')
    if f and len(f) >= 10:
        return f[7:10]
    if m and len(m) >= 10:
        return m[7:10]
    return ''


def get_clbal(input_row: Dict) -> str:
    """CLBAL: Closing balance amount"""
    f = safe_get(input_row, 'block4_62F')
    m = safe_get(input_row, 'block4_62M')
    if f and len(f) > 10:
        return f[10:].replace(',', '.')
    if m and len(m) > 10:
        return m[10:].replace(',', '.')
    return ''


def get_idrorcr(input_row: Dict) -> str:
    """IDRORCR: Debit/Credit indicator from block4_61"""
    v = safe_get(input_row, 'block4_61')
    if not v:
        return ''
    
    # Check if positions 6-10 are digits (entry date present)
    if len(v) >= 10 and v[6:10].isdigit():
        # Entry date present, D/C indicator at position 10
        if len(v) > 10:
            indicator = v[10]
            if indicator == 'R':
                # Reversal - check next character
                if len(v) > 11:
                    return 'DR' if v[11] == 'C' else 'CR'
            return indicator
    else:
        # No entry date, D/C indicator at position 6
        if len(v) > 6:
            indicator = v[6]
            if indicator == 'R':
                return 'D'
            return indicator
    return ''


def get_iamount(input_row: Dict) -> str:
    """IAMOUNT: Transaction amount from block4_61"""
    v = safe_get(input_row, 'block4_61')
    if not v:
        return ''
    
    # Check if positions 6-10 are digits (entry date present)
    if len(v) > 10 and v[6:10].isdigit():
        return extract_decimal(v[10:])
    elif len(v) > 6:
        return extract_decimal(v[6:])
    return '0.00'


def get_itrancode(input_row: Dict) -> str:
    """ITRANCODE: Transaction type code from block4_61"""
    v = safe_get(input_row, 'block4_61')
    if not v or ',' not in v:
        return ''
    
    # Extract text after comma, remove leading digits
    after_comma = v[v.find(','):]
    code = re.sub(r'^[\d,]+', '', after_comma)
    return code[:4] if len(code) >= 4 else code


def get_ientrydate(input_row: Dict) -> str:
    """IENTRYDATE: Entry date from block4_61"""
    v = safe_get(input_row, 'block4_61')
    f62 = safe_get(input_row, 'block4_62F')
    m62 = safe_get(input_row, 'block4_62M')
    
    if not v:
        return ''
    
    # Check if positions 6-10 contain entry date (MMDD)
    if len(v) >= 10 and v[6:10].isdigit():
        now = datetime.now()
        # Handle year rollover (December entry in January)
        if now.month == 1 and v[6:8] == '12':
            year = str(now.year - 1)[2:4]
        else:
            year = str(now.year)[2:4]
        return year + v[6:10]
    else:
        # Use closing balance date as fallback
        if f62 and len(f62) >= 7:
            return f62[1:7]
        if m62 and len(m62) >= 7:
            return m62[1:7]
    return ''


def get_isfield7(input_row: Dict) -> str:
    """ISFIELD7: Customer reference from block4_61"""
    v = safe_get(input_row, 'block4_61')
    if not v or ',' not in v:
        return ''
    
    # Find transaction code position
    after_comma = v[v.find(','):]
    trancode = re.sub(r'^[\d,]+', '', after_comma)[:4]
    if not trancode:
        return ''
    
    trancode_pos = v.find(trancode)
    if trancode_pos == -1:
        return ''
    
    start = trancode_pos + 4
    
    # Determine end position
    if '//' in v:
        return v[start:v.find('//')]
    elif 'sfield9=' in v:
        return v[start:v.find('sfield9=')]
    else:
        return v[start:]


def get_isfield8(input_row: Dict) -> str:
    """ISFIELD8: Bank reference from block4_61 (after //)"""
    v = safe_get(input_row, 'block4_61')
    if not v or '//' not in v:
        return ''
    
    start = v.find('//') + 2
    
    if 'sfield9=' in v and v.find('//') < v.find('sfield9='):
        return v[start:v.find('sfield9=')]
    return v[start:]


def get_istring6(input_row: Dict) -> str:
    """ISTRING6: Composite key for matching"""
    v61 = safe_get(input_row, 'block4_61')
    bic2 = safe_get(input_row, 'block2bic')
    acc = safe_get(input_row, 'block4_25')
    
    # Check if value date exists
    if not (v61 and len(v61) >= 6 and v61[:6].isdigit()):
        return 'NA'
    
    # Special handling for CEDELULL
    if bic2[:8] == 'CEDELULL':
        return bic2[:8]
    
    # Build composite key
    result = bic2
    
    # Add truncated account (first 5 chars after removing leading zeros)
    acc_stripped = acc.strip().lstrip('0')
    result += acc_stripped[:5]
    
    # Add amount
    if v61[6:10].isdigit():
        result += extract_decimal(v61[10:])
    else:
        result += extract_decimal(v61[6:])
    
    # Add sfield9 portion (up to 20 chars)
    if 'sfield9=' in v61:
        sfield9_start = v61.find('sfield9=') + 8
        result += v61[sfield9_start:sfield9_start + 12]
    
    return result


def get_iflag15(input_row: Dict) -> str:
    """IFLAG15: Message type"""
    return safe_get(input_row, 'messagetype')


def get_xstring17(input_row: Dict) -> str:
    """XSTRING17: Extended composite key"""
    v61 = safe_get(input_row, 'block4_61')
    bic2 = safe_get(input_row, 'block2bic')
    acc = safe_get(input_row, 'block4_25')
    
    if not (v61 and len(v61) >= 6 and v61[:6].isdigit()):
        return 'NA'
    
    if bic2[:8] == 'CEDELULL':
        return bic2[:8]
    
    result = bic2
    acc_stripped = acc.strip().lstrip('0')
    result += acc_stripped[:5]
    
    if v61[6:10].isdigit():
        result += extract_decimal(v61[10:])
    else:
        result += extract_decimal(v61[6:])
    
    # Add full sfield9 (no truncation unlike ISTRING6)
    if 'sfield9=' in v61:
        result += v61[v61.find('sfield9=') + 8:]
    
    return result


def get_istring17(input_row: Dict) -> str:
    """ISTRING17: Column 2 value"""
    return safe_get(input_row, 'COLUMN2')


def get_istring51(input_row: Dict) -> str:
    """ISTRING51: block1bic with position 8 removed"""
    v = safe_get(input_row, 'block1bic')
    if v and len(v) > 9:
        return v[:8] + v[9:]
    return ''


def get_iflag11(input_row: Dict) -> str:
    """IFLAG11: DR/CR flag as 1 or 2"""
    v = safe_get(input_row, 'block4_61')
    if not v or len(v) <= 10:
        return ''
    
    indicator = v[10]
    if indicator == 'C':
        return '1'
    elif indicator == 'D':
        return '2'
    elif indicator == 'R' and len(v) > 11:
        # Reversal
        return '2' if v[11] == 'C' else ('1' if v[11] == 'D' else '')
    return ''


def get_icurrency(input_row: Dict) -> str:
    """ICURRENCY: Currency from opening balance"""
    f = safe_get(input_row, 'block4_60F')
    m = safe_get(input_row, 'block4_60M')
    if f and len(f) >= 10:
        return f[7:10]
    if m and len(m) >= 10:
        return m[7:10]
    return ''


def get_iflag8(input_row: Dict) -> str:
    """IFLAG8: Count of significant digits in amount"""
    v = safe_get(input_row, 'block4_61')
    if not v:
        return '0'
    
    if len(v) > 10 and v[6:10].isdigit():
        amount = extract_decimal(v[10:])
    elif len(v) > 6:
        amount = extract_decimal(v[6:])
    else:
        return '0'
    
    return str(count_significant_digits(amount))


def get_availbalsign(input_row: Dict) -> str:
    """AVAILBALSIGN: Available balance sign"""
    v = safe_get(input_row, 'block4_64')
    return char_at(v, 0)


def get_availbalcy(input_row: Dict) -> str:
    """AVAILBALCY: Available balance currency"""
    v = safe_get(input_row, 'block4_64')
    if v and len(v) >= 10:
        return v[7:10]
    return ''


def get_availbal(input_row: Dict) -> str:
    """AVAILBAL: Available balance amount"""
    v = safe_get(input_row, 'block4_64')
    if v and len(v) > 10:
        return v[10:].replace(',', '.')
    return ''


def get_msgtype(input_row: Dict) -> str:
    """MSGTYPE: Message type"""
    return safe_get(input_row, 'messagetype')


def get_iamount4(input_row: Dict) -> str:
    """IAMOUNT4: Truncated reference (11 chars, alphanumeric only)"""
    v = safe_get(input_row, 'block4_61')
    if not v or ',' not in v:
        return ''
    
    # Find transaction code
    after_comma = v[v.find(','):]
    trancode = re.sub(r'^[\d,]+', '', after_comma)[:4]
    if not trancode:
        return ''
    
    trancode_pos = v.find(trancode)
    if trancode_pos == -1:
        return ''
    
    start = trancode_pos + 4
    
    # Get reference portion
    if '//' in v:
        ref = v[start:v.find('//')]
    elif 'sfield9=' in v:
        ref = v[start:v.find('sfield9=')]
    else:
        ref = v[start:]
    
    # Remove non-alphanumeric and truncate to 11
    return re.sub(r'[^\w]', '', ref)[:11]


# =============================================================================
# FIELD FUNCTION MAPPING
# =============================================================================

FIELD_FUNCTIONS = {
    'TEMP2': get_temp2,
    'TEMP6': get_temp6,
    'SIDE': get_side,
    'TERMID': get_termid,
    'DESTID': get_destid,
    'THE3REF': get_the3ref,
    'SUBACC': get_subacc,
    'STMTNO': get_stmtno,
    'STMTGP': get_stmtgp,
    'IVALUEDATE': get_ivaluedate,
    'OPBALSIGN': get_opbalsign,
    'OPBALTP': get_opbaltp,
    'OPBALDATE': get_opbaldate,
    'OPBALCY': get_opbalcy,
    'OPBAL': get_opbal,
    'CLBALSIGN': get_clbalsign,
    'CLBALTP': get_clbaltp,
    'CLBALDATE': get_clbaldate,
    'CLBALCY': get_clbalcy,
    'CLBAL': get_clbal,
    'IDRORCR': get_idrorcr,
    'IAMOUNT': get_iamount,
    'ITRANCODE': get_itrancode,
    'IENTRYDATE': get_ientrydate,
    'ISFIELD7': get_isfield7,
    'ISFIELD8': get_isfield8,
    'ISTRING6': get_istring6,
    'IFLAG15': get_iflag15,
    'XSTRING17': get_xstring17,
    'ISTRING17': get_istring17,
    'ISTRING51': get_istring51,
    'IFLAG11': get_iflag11,
    'ICURRENCY': get_icurrency,
    'IFLAG8': get_iflag8,
    'AVAILBALSIGN': get_availbalsign,
    'AVAILBALCY': get_availbalcy,
    'AVAILBAL': get_availbal,
    'MSGTYPE': get_msgtype,
    'IAMOUNT4': get_iamount4,
}


# =============================================================================
# MAIN TRANSFORMER CLASS
# =============================================================================

class SwiftTransformer:
    """Transforms SWIFT messages using YAML configuration."""
    
    def __init__(self, config_path: str):
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.input_fields = self.config.get('input_fields', [])
        self.output_fields = self.config.get('output_fields', [])
        
    def get_output_field_names(self) -> list:
        """Get list of output field names."""
        return [field['name'] for field in self.output_fields]
    
    def transform_row(self, input_row: Dict) -> Dict:
        """Transform a single input row to output row."""
        output_row = {}
        
        for field in self.output_fields:
            field_name = field['name']
            
            # Use helper function if available
            if field_name in FIELD_FUNCTIONS:
                try:
                    output_row[field_name] = FIELD_FUNCTIONS[field_name](input_row)
                except Exception as e:
                    print(f"Warning: Error computing {field_name}: {e}")
                    output_row[field_name] = ''
            else:
                # Field not implemented
                output_row[field_name] = ''
        
        return output_row
    
    def process_file(self, input_path: str, output_path: str, 
                     input_delimiter: str = '|', output_delimiter: str = '|',
                     has_header: bool = True):
        """Process input file and write output file."""
        
        with open(input_path, 'r', encoding='utf-8') as infile:
            lines = infile.readlines()
        
        if not lines:
            print("Warning: Input file is empty")
            return
        
        # Parse header
        if has_header:
            header_line = lines[0].strip()
            headers = header_line.split(input_delimiter)
            data_lines = lines[1:]
        else:
            # Use input_fields from config as headers
            headers = self.input_fields
            data_lines = lines
        
        # Get output field names
        output_field_names = self.get_output_field_names()
        
        with open(output_path, 'w', encoding='utf-8') as outfile:
            # Write header
            outfile.write(output_delimiter.join(output_field_names) + '\n')
            
            # Process each row
            row_count = 0
            for line in data_lines:
                line = line.strip()
                if not line:
                    continue
                
                values = line.split(input_delimiter)
                
                # Build input row dictionary
                input_row = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        input_row[header] = values[i]
                    else:
                        input_row[header] = ''
                
                # Transform
                output_row = self.transform_row(input_row)
                
                # Write output
                output_values = [str(output_row.get(name, '')) for name in output_field_names]
                outfile.write(output_delimiter.join(output_values) + '\n')
                row_count += 1
        
        print(f"Processed {row_count} rows")
        print(f"Output written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='SWIFT Message Transformer')
    parser.add_argument('--config', '-c', required=True, help='Path to YAML configuration file')
    parser.add_argument('--input', '-i', required=True, help='Path to input file')
    parser.add_argument('--output', '-o', required=True, help='Path to output file')
    parser.add_argument('--input-delimiter', '-id', default='|', help='Input file delimiter (default: |)')
    parser.add_argument('--output-delimiter', '-od', default='|', help='Output file delimiter (default: |)')
    parser.add_argument('--no-header', action='store_true', help='Input file has no header row')
    
    args = parser.parse_args()
    
    print(f"Loading configuration from: {args.config}")
    transformer = SwiftTransformer(args.config)
    
    print(f"Processing input file: {args.input}")
    transformer.process_file(
        input_path=args.input,
        output_path=args.output,
        input_delimiter=args.input_delimiter,
        output_delimiter=args.output_delimiter,
        has_header=not args.no_header
    )


if __name__ == '__main__':
    main()
