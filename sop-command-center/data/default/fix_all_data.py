#!/usr/bin/env python3
"""Master script to fix all data issues and validate"""

import subprocess
import sys

def run_script(script_name, description):
    """Run a Python script and report success/failure"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(['python3', script_name], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        print(f"Output: {e.stdout}")
        print(f"Errors: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ Script not found: {script_name}")
        return False

def main():
    print("\n" + "="*60)
    print("S&OP COMMAND CENTER - DATA FIX MASTER SCRIPT")
    print("="*60)
    
    fixes = [
        ('fix_products_json.py', 'Convert products.json to array format'),
        ('generate_demand.py', 'Generate weekly demand data'),
        ('fix_inventory.py', 'Add Last_Restocked dates to inventory'),
        ('create_stockout_scenarios.py', 'Create realistic stockout scenarios for demo'),
    ]
    
    all_success = True
    for script, desc in fixes:
        success = run_script(script, desc)
        if not success:
            all_success = False
            print(f"⚠️  Warning: {script} failed, continuing anyway...")
    
    # Run validation
    print("\n" + "="*60)
    print("Running Final Validation")
    print("="*60)
    validation_success = run_script('validate_all_data.py', 'Validate all datasets')
    
    print("\n" + "="*60)
    if validation_success:
        print("✅ ALL DATA FIXED AND VALIDATED!")
        print("="*60)
        return 0
    else:
        print("❌ VALIDATION FAILED - Check errors above")
        print("="*60)
        return 1

if __name__ == '__main__':
    sys.exit(main())