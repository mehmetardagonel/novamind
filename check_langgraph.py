
import sys
try:
    from langgraph.errors import GraphInterrupt
    print(f"Found in errors: {GraphInterrupt}")
except ImportError:
    print("Not found in errors")

try:
    from langgraph.types import GraphInterrupt
    print(f"Found in types: {GraphInterrupt}")
except ImportError:
    print("Not found in types")
