import sys
import os

# Add the workspace directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.core.ai_agent import FuzzyMembership

def test_elevation_suitability():
    # Test case 1: input within range
    # crop range: 1000 to 3000
    # margin: 200 -> a=800, b=1000, c=3000, d=3200
    print("Test range 1000-3000 (margin 200):")
    for val in [700, 800, 900, 1000, 2000, 3000, 3100, 3200, 3300]:
        res = FuzzyMembership.elevation_suitability(val, 1000, 3000)
        print(f"  elev: {val} -> suitability: {res:.2f}")

    # Test case 2: lower bound at 0
    # crop range: 0 to 600
    # margin: 200 -> a=0 (capped), b=0, c=600, d=800
    print("\nTest range 0-600 (margin 200):")
    for val in [-50, 0, 50, 300, 600, 700, 800, 900]:
        res = FuzzyMembership.elevation_suitability(val, 0, 600)
        print(f"  elev: {val} -> suitability: {res:.2f}")

if __name__ == "__main__":
    test_elevation_suitability()
