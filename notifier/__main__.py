"""Entry point for running the notifier module directly"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from notifier.ntfy_notifier import main

if __name__ == "__main__":
    main()