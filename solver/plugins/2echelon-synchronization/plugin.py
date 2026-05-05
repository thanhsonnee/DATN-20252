from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

# from DecomposedModels import ...

def get_name() -> str:
    return "2echelon-synchronization"

def get_description() -> str:
    return "Algorithm 2echelon-synchronization"

def run(instance, time_limit_sec: float, seed: int, **kwargs):
    raise NotImplementedError("Implement run() here")
