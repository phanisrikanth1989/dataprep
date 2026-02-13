"""
SwiftTransformer component - Transforms SWIFT MT940/MT950 bank messages

This component transforms SWIFT financial messages from one format to another
using configurable field extraction rules. Supports both YAML configuration
and inline field definitions.

Equivalent to a specialized tMap for SWIFT message parsing.
"""
import pandas as pd
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS - Safe data extraction utilities
# =============================================================================

def safe_str(value: Any) -> str:
    """Safely convert value to string, handling None/empty."""
    if value is None:
        return ''
    return str(value)


def safe_get(input_row: Dict, field: str) -> str:
    """Safely get a field from input_row as string."""
    return safe_str(input_row.get(field, ''))


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
    
    # Add sfield9 portion (up to 12 chars)
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
# SWIFT TRANSFORMER COMPONENT
# =============================================================================

class SwiftTransformer(BaseComponent):
    """
    SWIFT Message Transformer component.
    
    Transforms SWIFT MT940/MT950 bank statement messages into a business format
    by extracting and computing fields from SWIFT message blocks.
    
    Configuration:
        output_fields (list): List of output field definitions
            - name (str): Field name
            - type (str): 'builtin' or 'python_expression'
            - expression (str): Python expression (if type is python_expression)
        
        include_input_fields (bool): Whether to include original input fields (default: False)
        use_all_builtin_fields (bool): Use all 35 built-in SWIFT fields (default: True)
        custom_fields (list): Additional custom field definitions
    
    Inputs:
        main: DataFrame with SWIFT message fields
    
    Outputs:
        main: Transformed DataFrame with computed fields
        reject: Rows that failed transformation
    
    Example config:
        {
            "use_all_builtin_fields": True,
            "include_input_fields": False,
            "custom_fields": [
                {"name": "CUSTOM1", "expression": "input_row.get('block4_20', '')[:5]"}
            ]
        }
    """
    
    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Execute SWIFT transformation.
        
        Args:
            input_data: DataFrame with SWIFT message fields as columns
            
        Returns:
            Dict with 'main' (transformed data) and 'reject' (failed rows)
        """
        logger.debug(f"SwiftTransformer[{self.id}] - Starting transformation")
        
        if input_data is None or input_data.empty:
            logger.warning(f"SwiftTransformer[{self.id}] - Empty input data")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}
        
        config = self.config
        use_all_builtin = config.get('use_all_builtin_fields', True)
        include_input = config.get('include_input_fields', False)
        custom_fields = config.get('custom_fields', [])
        output_field_config = config.get('output_fields', [])
        
        # Determine which fields to compute
        fields_to_compute = []
        
        if use_all_builtin:
            # Use all built-in SWIFT fields
            fields_to_compute = list(FIELD_FUNCTIONS.keys())
        elif output_field_config:
            # Use fields from output_fields config
            for field_def in output_field_config:
                if field_def.get('type') == 'builtin' or field_def['name'] in FIELD_FUNCTIONS:
                    fields_to_compute.append(field_def['name'])
        
        logger.info(f"SwiftTransformer[{self.id}] - Computing {len(fields_to_compute)} built-in fields")
        
        # Process each row
        output_rows = []
        reject_rows = []
        
        for idx, row in input_data.iterrows():
            input_row = row.to_dict()
            output_row = {}
            row_failed = False
            
            # Optionally include input fields
            if include_input:
                output_row.update(input_row)
            
            # Compute built-in fields
            for field_name in fields_to_compute:
                if field_name in FIELD_FUNCTIONS:
                    try:
                        output_row[field_name] = FIELD_FUNCTIONS[field_name](input_row)
                    except Exception as e:
                        logger.warning(f"SwiftTransformer[{self.id}] - Error computing {field_name} at row {idx}: {e}")
                        output_row[field_name] = ''
            
            # Compute custom fields (Python expressions)
            for custom_field in custom_fields:
                field_name = custom_field.get('name')
                expression = custom_field.get('expression', '')
                
                if not field_name or not expression:
                    continue
                
                try:
                    # Evaluate Python expression with input_row in scope
                    result = eval(expression, {'input_row': input_row, 're': re, 'datetime': datetime})
                    output_row[field_name] = str(result) if result is not None else ''
                except Exception as e:
                    logger.warning(f"SwiftTransformer[{self.id}] - Error in custom field {field_name}: {e}")
                    output_row[field_name] = ''
            
            # Compute fields from output_fields config with python_expression type
            for field_def in output_field_config:
                if field_def.get('type') == 'python_expression':
                    field_name = field_def['name']
                    expression = field_def.get('python_expression', '').replace('((python))', '').strip()
                    
                    if not expression:
                        continue
                    
                    try:
                        result = eval(expression, {'input_row': input_row, 're': re, 'datetime': datetime})
                        output_row[field_name] = str(result) if result is not None else ''
                    except Exception as e:
                        logger.warning(f"SwiftTransformer[{self.id}] - Error in field {field_name}: {e}")
                        output_row[field_name] = ''
            
            if row_failed:
                reject_rows.append(input_row)
            else:
                output_rows.append(output_row)
        
        # Create output DataFrames
        if output_rows:
            main_df = pd.DataFrame(output_rows)
        else:
            main_df = pd.DataFrame()
        
        if reject_rows:
            reject_df = pd.DataFrame(reject_rows)
        else:
            reject_df = pd.DataFrame()
        
        # Update statistics
        self._update_stats(
            rows_read=len(input_data),
            rows_ok=len(output_rows),
            rows_reject=len(reject_rows)
        )
        
        logger.info(f"SwiftTransformer[{self.id}] - Processed {len(input_data)} rows: "
                   f"{len(output_rows)} OK, {len(reject_rows)} rejected")
        
        return {'main': main_df, 'reject': reject_df}
    
    def get_output_schema(self) -> List[Dict[str, str]]:
        """
        Get output schema based on configuration.
        
        Returns:
            List of field definitions with name and type
        """
        schema = []
        
        config = self.config
        use_all_builtin = config.get('use_all_builtin_fields', True)
        
        if use_all_builtin:
            for field_name in FIELD_FUNCTIONS.keys():
                schema.append({'name': field_name, 'type': 'id_String'})
        
        # Add custom fields
        for custom_field in config.get('custom_fields', []):
            schema.append({'name': custom_field.get('name'), 'type': 'id_String'})
        
        return schema
