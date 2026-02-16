"""
Quick test script for TSwiftDataTransformer with lonye_python.yaml
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import pandas as pd
from v1.engine.components.transform.t_swift_data_transformer import TSwiftDataTransformer


class MockGlobalMap:
    """Mock global map for testing"""
    def get(self, key, default=None):
        return default
    def set(self, key, value):
        pass


class MockContextManager:
    """Mock context manager for testing"""
    def resolve_string(self, s):
        return s
    def get(self, key, default=None):
        return default


def main():
    # Load sample input data
    input_file = 'data/lonye_input.txt'
    print(f"Loading input from: {input_file}")
    input_df = pd.read_csv(input_file, delimiter='|')
    print(f"Loaded {len(input_df)} rows with columns: {list(input_df.columns)}")
    
    # Create transformer config
    config = {
        'config_file': 'config/lonye_python.yaml',
        'delimiter': '|',
        'die_on_error': False,
        'skip_error_rows': False
    }
    
    # Initialize transformer
    global_map = MockGlobalMap()
    context_manager = MockContextManager()
    
    print("\nInitializing TSwiftDataTransformer...")
    transformer = TSwiftDataTransformer('test_transformer', config, global_map, context_manager)
    
    print(f"Loaded {len(transformer.output_fields)} output field definitions")
    
    # Process data
    print("\nTransforming data...")
    result = transformer._process(input_df)
    
    output_df = result['main']
    print(f"\nTransformed to {len(output_df)} rows with {len(output_df.columns)} columns")
    print(f"Output columns: {list(output_df.columns)}")
    
    # Show first few rows
    print("\n" + "="*80)
    print("FIRST 3 ROWS OF OUTPUT:")
    print("="*80)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    print(output_df.head(3).to_string())
    
    # Save output
    output_file = 'data/lonye_output.txt'
    output_df.to_csv(output_file, sep='|', index=False)
    print(f"\nOutput saved to: {output_file}")


if __name__ == '__main__':
    main()
