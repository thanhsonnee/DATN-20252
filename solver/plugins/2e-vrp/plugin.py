from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

# from files/display import ...

def get_name() -> str:
    return "2e-VRP"

def get_description() -> str:
    return "Algorithm 2e-VRP"

def run(instance, time_limit_sec: float, seed: int, **kwargs):
    raise NotImplementedError("Implement run() here")
