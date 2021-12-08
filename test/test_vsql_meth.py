"""
Tests for vSQL methods.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

def test_str_lower(config_persons):
	check_vsql(config_persons, "'MISSISSIPPI'.lower() == 'mississippi'")

def test_str_upper(config_persons):
	check_vsql(config_persons, "'mississippi'.upper() == 'MISSISSIPPI'")

def test_str_startswith(config_persons):
	check_vsql(config_persons, "'mississippi'.startswith('missi')")

def test_str_endswith(config_persons):
	check_vsql(config_persons, "'mississippi'.endswith('sippi')")

def test_str_strip1(config_persons):
	check_vsql(config_persons, "'\\r\\t\\n foo \\r\\t\\n '.strip() == 'foo'")

def test_str_strip2(config_persons):
	check_vsql(config_persons, "'xyzzygurkxyzzy'.strip('xyz') == 'gurk'")

def test_str_lstrip1(config_persons):
	check_vsql(config_persons, "'\\r\\t\\n foo \\r\\t\\n '.lstrip() == 'foo \\r\\t\\n '")

def test_str_lstrip2(config_persons):
	check_vsql(config_persons, "'xyzzygurkxyzzy'.lstrip('xyz') == 'gurkxyzzy'")

def test_str_rstrip1(config_persons):
	check_vsql(config_persons, "'\\r\\t\\n foo \\r\\t\\n '.rstrip() == '\\r\\t\\n foo'")

def test_str_rstrip2(config_persons):
	check_vsql(config_persons, "'xyzzygurkxyzzy'.rstrip('xyz') == 'xyzzygurk'")

def test_str_find1(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('ks') == -1")

def test_str_find2(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk') == 2")

def test_str_find3(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', 2) == 2")

def test_str_find4(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', -3) == 6")

def test_str_find5(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', 2, 4) == 2")

def test_str_find6(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', 4, 8) == 6")

def test_str_find7(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('ur', -4, -1) == 5")

def test_str_find8(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', 2, 3) == -1")

def test_str_find9(config_persons):
	check_vsql(config_persons, "'gurkgurk'.find('rk', 7) == -1")

def test_str_replace(config_persons):
	check_vsql(config_persons, "'gurk'.replace('u', 'oo') == 'goork'")

def test_str_split1(config_persons):
	check_vsql(config_persons, "' \\t\\r\\nf \\t\\r\\no \\t\\r\\no \\t\\r\\n'.split() == ['f', 'o', 'o']")

def test_str_split2(config_persons):
	check_vsql(config_persons, "' \\t\\r\\nf \\t\\r\\no \\t\\r\\no \\t\\r\\n'.split(None, 1) == ['f', 'o \\t\\r\\no']")

def test_str_split3(config_persons):
	check_vsql(config_persons, "'xxfxxoxxoxx'.split('xx') == [None, 'f', 'o', 'o', None]")

def test_str_split4(config_persons):
	check_vsql(config_persons, "'xxfxxoxxoxx'.split('xx', 2) == [None, 'f', 'oxxoxx']")

def test_str_join_str(config_persons):
	check_vsql(config_persons, "','.join('1234') == '1,2,3,4'")

def test_str_join_list(config_persons):
	check_vsql(config_persons, "','.join(['1', '2', '3', '4']) == '1,2,3,4'")

def test_color_lum1(config_persons):
	check_vsql(config_persons, "#000.lum() == 0.0")

def test_color_lum2(config_persons):
	check_vsql(config_persons, "#fff.lum() == 1.0")

def test_date_week(config_persons):
	check_vsql(config_persons, "@(2000-02-29).week() == 9")

def test_datetime_week(config_persons):
	check_vsql(config_persons, "@(2000-02-29T12:34:56).week() == 9")
