import os

def in_apptainer() -> bool:
    return "APPTAINER_CONTAINER" in os.environ
