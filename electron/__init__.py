__version__ = "0.0.2"
__logo__ = f"""
        __          __                      
  ___  / /__  _____/ /__________  ____      
 / _ \/ / _ \/ ___/ __/ ___/ __ \/ __ \     
/  __/ /  __/ /__/ /_/ /  / /_/ / / / /     
\___/_/\___/\___/\__/_/   \____/_/ /_/      

⚡ electron build v{__version__}                              
"""

from electron.server import Server

__all__ = ["Server"]
