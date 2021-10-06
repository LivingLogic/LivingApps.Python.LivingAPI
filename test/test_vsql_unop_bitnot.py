"""
Tests for the vSQL unary bitwise not operator ``~``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_bool1(config_persons):
	check_vsql(config_persons, "repr(~app.p_bool_none.value) == 'None'")

def test_bool2(config_persons):
	check_vsql(config_persons, "repr(~app.p_bool_false.value) == '-1'")

def test_bool3(config_persons):
	check_vsql(config_persons, "repr(~app.p_bool_true.value) == '-2'")

def test_int1(config_persons):
	check_vsql(config_persons, "repr(~app.p_int_none.value) == 'None'")

def test_int2(config_persons):
	check_vsql(config_persons, "repr(~app.p_int_value.value) == '-1778'")
