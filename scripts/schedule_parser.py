Run python scripts/schedule_parser.py
Traceback (most recent call last):
  File "/home/runner/work/misis-itkn-schedule/misis-itkn-schedule/scripts/schedule_parser.py", line 10, in <module>
    import pandas as pd
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/__init__.py", line 22, in <module>
    from pandas.compat import is_numpy_dev as _is_numpy_dev  # pyright: ignore # noqa:F401
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/compat/__init__.py", line 25, in <module>
    from pandas.compat.numpy import (
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/compat/numpy/__init__.py", line 4, in <module>
    from pandas.util.version import Version
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/util/__init__.py", line 2, in <module>
    from pandas.util._decorators import (  # noqa:F401
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/util/_decorators.py", line 14, in <module>
    from pandas._libs.properties import cache_readonly
  File "/opt/hostedtoolcache/Python/3.9.23/x64/lib/python3.9/site-packages/pandas/_libs/__init__.py", line 13, in <module>
    from pandas._libs.interval import Interval
  File "pandas/_libs/interval.pyx", line 1, in init pandas._libs.interval
ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88 from PyObject
Error: Process completed with exit code 1.
