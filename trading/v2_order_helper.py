#!/usr/bin/env python3
"""
CLOB V2 Order Helper — Creates V2-compliant orders.

CLOB V2 Changes:
- timestamp (ms) instead of nonce
- metadata field added
- builder field added (for builder program)
- feeRateBps REMOVED (fees set at match time)
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class V2OrderParams:
    """V2 Order Parameters."""
    token_id: str
    side: str  # 'BUY' or 'SELL'
    price: float  # 0.01 to 0.99
    size: float  # In pUSD
    timestamp: Optional[int] = None  # Milliseconds
    metadata: Optional[str] = None  # Optional metadata
    builder: Optional[str] = None  # Builder code for attribution
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = int(time.time() * 1000)

def create_v2_order_params(
    token_id: str,
    side: str,
    price: float,
    size: float,
    builder_code: Optional[str] = None,
    metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create V2 order parameters.
    
    Args:
        token_id: The token ID to trade
        side: 'BUY' or 'SELL'
        price: Price in cents (0.01 to 0.99)
        size: Order size in pUSD
        builder_code: Optional builder code for fee discounts
        metadata: Optional metadata string
    
    Returns:
        Dict with V2 order parameters
    """
    # Generate timestamp in milliseconds (REQUIRED for V2)
    timestamp_ms = int(time.time() * 1000)
    
    order = {
        'token_id': token_id,
        'side': side,
        'price': price,
        'size': size,
        'timestamp': timestamp_ms,  # NEW in V2 (replaces nonce)
    }
    
    # Add optional fields
    if metadata:
        order['metadata'] = metadata
    
    if builder_code:
        order['builder'] = builder_code
    
    return order

def convert_v1_to_v2_order(v1_order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert V1 order format to V2.
    
    V1 -> V2 Changes:
    - Remove: nonce, feeRateBps, taker
    - Add: timestamp (ms)
    - Optional: metadata, builder
    """
    v2_order = {
        'token_id': v1_order.get('token_id'),
        'side': v1_order.get('side'),
        'price': v1_order.get('price'),
        'size': v1_order.get('size'),
        'timestamp': int(time.time() * 1000),  # NEW required field
    }
    
    # Copy optional fields if present
    if 'metadata' in v1_order:
        v2_order['metadata'] = v1_order['metadata']
    
    if 'builder' in v1_order:
        v2_order['builder'] = v1_order['builder']
    
    return v2_order

def validate_v2_order(order: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate V2 order has required fields.
    
    Returns:
        (is_valid, error_message)
    """
    required = ['token_id', 'side', 'price', 'size', 'timestamp']
    
    for field in required:
        if field not in order:
            return False, f"Missing required field: {field}"
    
    # Validate timestamp is recent (within last 60 seconds)
    current_time = int(time.time() * 1000)
    timestamp = order.get('timestamp', 0)
    
    if timestamp > current_time + 1000:  # Future timestamp
        return False, "Timestamp is in the future"
    
    if timestamp < current_time - 60000:  # Older than 60 seconds
        return False, "Timestamp is too old (>60s)"
    
    # Validate price range
    price = order.get('price', 0)
    if not (0.01 <= price <= 0.99):
        return False, f"Price {price} out of range (0.01-0.99)"
    
    # Validate size
    size = order.get('size', 0)
    if size < 1.0:
        return False, f"Size {size} below minimum ($1)"
    
    return True, "Valid V2 order"

# Builder codes for fee discounts
BUILDER_CODES = {
    'DEFAULT': None,
    'HIGH_VOLUME': 'high_vol_001',  # Example
    'MARKET_MAKER': 'mm_001',  # Example
}

def get_builder_code(tier: str = 'default') -> Optional[str]:
    """Get builder code for fee discounts."""
    return BUILDER_CODES.get(tier.upper(), None)

if __name__ == "__main__":
    # Test V2 order creation
    print("Testing V2 Order Helper")
    print("=" * 60)
    
    order = create_v2_order_params(
        token_id="0x1234567890abcdef",
        side="BUY",
        price=0.55,
        size=10.0,
        builder_code="test_builder"
    )
    
    print(f"V2 Order: {order}")
    
    is_valid, msg = validate_v2_order(order)
    print(f"Validation: {is_valid} - {msg}")
    
    # Test V1 to V2 conversion
    v1_order = {
        'token_id': '0xabc',
        'side': 'SELL',
        'price': 0.45,
        'size': 5.0,
        'nonce': 12345,  # V1 field
        'feeRateBps': 100,  # V1 field
    }
    
    v2 = convert_v1_to_v2_order(v1_order)
    print(f"\nConverted V1->V2: {v2}")