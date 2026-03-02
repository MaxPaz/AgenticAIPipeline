"""
Quick check script to validate the app can be imported and run.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Checking app dependencies...")

# Check imports
try:
    import streamlit as st
    print("✅ Streamlit imported successfully")
except ImportError as e:
    print(f"❌ Failed to import streamlit: {e}")
    sys.exit(1)

try:
    from agents.coordinator_agent import CoordinatorAgent
    print("✅ CoordinatorAgent imported successfully")
except ImportError as e:
    print(f"❌ Failed to import CoordinatorAgent: {e}")
    sys.exit(1)

try:
    import boto3
    print("✅ boto3 imported successfully")
except ImportError as e:
    print(f"❌ Failed to import boto3: {e}")
    sys.exit(1)

# Check AWS credentials
try:
    session = boto3.Session()
    credentials = session.get_credentials()
    if credentials:
        print("✅ AWS credentials found")
    else:
        print("⚠️  Warning: AWS credentials not found")
except Exception as e:
    print(f"⚠️  Warning: Could not check AWS credentials: {e}")

# Try to instantiate coordinator
try:
    coordinator = CoordinatorAgent()
    print("✅ CoordinatorAgent instantiated successfully")
except Exception as e:
    print(f"❌ Failed to instantiate CoordinatorAgent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test connection
try:
    result = coordinator.test_connection()
    if result['success']:
        print(f"✅ Connection test passed: {result['message']}")
    else:
        print(f"⚠️  Connection test failed: {result['message']}")
except Exception as e:
    print(f"⚠️  Connection test error: {e}")

print("\n" + "="*60)
print("App validation complete!")
print("="*60)
print("\nTo run the app, use:")
print("  streamlit run ui/app.py")
print("\nOr use the launch script:")
print("  ./ui/launch.sh")
