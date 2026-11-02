"""Regression gate for Gensim BLAS error-sentinel bug #3665.
Calls the selected exported Cython wrapper, with valid one-element C arrays.
https://github.com/piskvorky/gensim/issues/3665
"""

import ctypes as ct


def check_blas():
    from gensim.models import word2vec_inner as inner

    name = {0: "our_dot_double", 1: "our_dot_float", 2: "our_dot_noblas"}[
        inner.FAST_VERSION
    ]
    capsule = ct.py_object(inner.__pyx_capi__[name])
    capsule_name = ct.pythonapi.PyCapsule_GetName
    capsule_name.restype = ct.c_char_p
    capsule_name.argtypes = [ct.py_object]
    capsule_ptr = ct.pythonapi.PyCapsule_GetPointer
    capsule_ptr.restype = ct.c_void_p
    capsule_ptr.argtypes = [ct.py_object, ct.c_char_p]
    address = capsule_ptr(capsule, capsule_name(capsule))
    i, f = ct.POINTER(ct.c_int), ct.POINTER(ct.c_float)
    dot = ct.CFUNCTYPE(ct.c_float, i, f, i, f, i)(address)
    n = ct.c_int(1)
    x = (ct.c_float * 1)(1)
    for expected in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
        y = (ct.c_float * 1)(expected)
        actual = dot(ct.byref(n), x, ct.byref(n), y, ct.byref(n))
        if abs(actual - expected) > 1e-5:
            raise RuntimeError(
                f"Gensim BLAS regression: dot={actual}, expected={expected}. Use pinned requirements."
            )
    return dict(wrapper=name, negativeOneDot=-1.0)
