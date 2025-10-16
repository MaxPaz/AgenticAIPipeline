"""Test the get_available_kpis Lambda function locally."""

import json
import sys
import os

# Add lambda directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lambda_function import lambda_handler


def test_circle_k():
    """Test getting Customer A KPIs."""
    print("\n" + "="*80)
    print("TEST: Get Customer A KPIs")
    print("="*80)
    
    event = {
        'parameters': [
            {'name': 'customer', 'value': 'Customer A'}
        ]
    }
    
    response = lambda_handler(event, None)
    body = json.loads(response['response']['responseBody']['application/json']['body'])
    
    print(f"\nCustomer: {body['customer']}")
    print(f"KPI Count: {body['kpi_count']}")
    print(f"\nFirst 5 KPIs:")
    for kpi in body['kpis'][:5]:
        print(f"  KPI {kpi['kpi_id']}: {kpi['kpi_name']}")
        print(f"    Definition: {kpi['definition'][:80]}...")
        print(f"    Unit: {kpi['unit']}, Group: {kpi['group']}")
        print()


def test_kroger():
    """Test getting Customer B KPIs."""
    print("\n" + "="*80)
    print("TEST: Get Customer B KPIs")
    print("="*80)
    
    event = {
        'parameters': [
            {'name': 'customer', 'value': 'Customer B'}
        ]
    }
    
    response = lambda_handler(event, None)
    body = json.loads(response['response']['responseBody']['application/json']['body'])
    
    print(f"\nCustomer: {body['customer']}")
    print(f"KPI Count: {body['kpi_count']}")
    print(f"\nFirst 5 KPIs:")
    for kpi in body['kpis'][:5]:
        print(f"  KPI {kpi['kpi_id']}: {kpi['kpi_name']}")


def test_all_customers():
    """Test getting all KPIs."""
    print("\n" + "="*80)
    print("TEST: Get All KPIs")
    print("="*80)
    
    event = {
        'parameters': [
            {'name': 'customer', 'value': 'all'}
        ]
    }
    
    response = lambda_handler(event, None)
    body = json.loads(response['response']['responseBody']['application/json']['body'])
    
    print(f"\nCustomer: {body['customer']}")
    print(f"Total KPI Count: {body['kpi_count']}")
    
    # Count by customer
    customers = {}
    for kpi in body['kpis']:
        # Extract customer from definition or group
        customer = "Unknown"
        if 'Customer A' in str(kpi):
            customer = "Customer A"
        elif 'Customer B' in str(kpi):
            customer = "Customer B"
        elif 'Customer C' in str(kpi):
            customer = "Customer C"
        elif 'Customer D' in str(kpi):
            customer = "Customer D"
        
        customers[customer] = customers.get(customer, 0) + 1
    
    print(f"\nKPIs by customer:")
    for customer, count in sorted(customers.items()):
        print(f"  {customer}: {count} KPIs")


if __name__ == "__main__":
    test_circle_k()
    test_kroger()
    test_all_customers()
