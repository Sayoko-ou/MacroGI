main.py -> API manager for features that will be called by the frontend (e.g. create food entry, edit food entry, etc.)
database.py -> connects to our MongoDB Atlas cluster and provides definitions for all collections
routes -> contains all of the .py files that will be used by main.py
models -> contains all of the .pkl files that will be used by main.py
modules -> additional helper functions


NOTE: .env is not included, please request this file from project owner for testing and development