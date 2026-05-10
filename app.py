# -*- coding: utf-8 -*-
"""
Streamlit Community Cloud 엔트리: 본문은 study2/code/test.py
로컬에서 직접 실행: streamlit run study2/code/test.py
"""
from __future__ import annotations

import pathlib
import runpy

_ROOT = pathlib.Path(__file__).resolve().parent
runpy.run_path(str(_ROOT / "study2" / "code" / "test.py"), run_name="__main__")
