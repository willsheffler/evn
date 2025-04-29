import warnings

def suppress_warnings(deprication=True):
    if deprication: warnings.filterwarnings("ignore", category=DeprecationWarning)
