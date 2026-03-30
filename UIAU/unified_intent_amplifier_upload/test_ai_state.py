#!/usr/bin/env python3
"""
Test script to check AI state behavior
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from cognitive_engine import cognitive_engine

def test_ai_state():
    print("=== AI State Test ===")
    print(f"cognitive_engine.enabled: {cognitive_engine.enabled}")
    print(f"hasattr(cognitive_engine, 'enabled'): {hasattr(cognitive_engine, 'enabled')}")
    
    # Test the condition used in voice_nav
    ai_enabled = cognitive_engine and hasattr(cognitive_engine, "enabled") and cognitive_engine.enabled
    print(f"AI enabled condition: {ai_enabled}")
    
    print("\n=== Toggle Test ===")
    print("Testing cognitive_engine.set_enabled(True)...")
    cognitive_engine.set_enabled(True)
    print(f"After set_enabled(True): {cognitive_engine.enabled}")
    
    ai_enabled_after = cognitive_engine and hasattr(cognitive_engine, "enabled") and cognitive_engine.enabled
    print(f"AI enabled condition after: {ai_enabled_after}")
    
    print("\n=== Toggle Back ===")
    print("Testing cognitive_engine.set_enabled(False)...")
    cognitive_engine.set_enabled(False)
    print(f"After set_enabled(False): {cognitive_engine.enabled}")
    
    ai_enabled_final = cognitive_engine and hasattr(cognitive_engine, "enabled") and cognitive_engine.enabled
    print(f"AI enabled condition final: {ai_enabled_final}")

if __name__ == "__main__":
    test_ai_state()
