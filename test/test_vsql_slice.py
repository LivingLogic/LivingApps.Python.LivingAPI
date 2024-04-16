"""
Tests for the vSQL slice operator ``A[B:C]``.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

from conftest import *


###
### Tests
###

d1 = "@(2000-02-29)"
d2 = "@(2000-03-01)"
d3 = "@(2000-03-02)"
d4 = "@(2000-03-03)"

dt1 = "@(2000-02-29T12:34:56)"
dt2 = "@(2000-03-01T12:34:56)"
dt3 = "@(2000-03-02T12:34:56)"
dt4 = "@(2000-03-03T12:34:56)"

def test_str_1(config_data):
	check_vsql(config_data, "app.p_str_value.value[1:3] == 'ur'")

def test_str_2(config_data):
	check_vsql(config_data, "app.p_str_value.value[-3:-1] == 'ur'")

def test_str_3(config_data):
	check_vsql(config_data, "app.p_str_value.value[4:10] == ''")

def test_str_4(config_data):
	check_vsql(config_data, "app.p_str_value.value[-10:-5] == ''")

def test_str_5(config_data):
	check_vsql(config_data, "app.p_str_value.value[1:] == 'urk'")

def test_str_6(config_data):
	check_vsql(config_data, "app.p_str_value.value[-3:] == 'urk'")

def test_str_7(config_data):
	check_vsql(config_data, "app.p_str_value.value[4:] == ''")

def test_str_8(config_data):
	check_vsql(config_data, "app.p_str_value.value[-10:] == 'gurk'")

def test_str_9(config_data):
	check_vsql(config_data, "app.p_str_value.value[:3] == 'gur'")

def test_str_10(config_data):
	check_vsql(config_data, "app.p_str_value.value[:-1] == 'gur'")

def test_str_11(config_data):
	check_vsql(config_data, "app.p_str_value.value[:10] == 'gurk'")

def test_str_12(config_data):
	check_vsql(config_data, "app.p_str_value.value[:-5] == ''")

def test_str_13(config_data):
	check_vsql(config_data, "app.p_str_value.value[:] == 'gurk'")

def test_str_14(config_data):
	check_vsql(config_data, "app.p_str_value.value[None:None] == 'gurk'")

def test_intlist_1(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][1:3] == [2, 3]")

def test_intlist_2(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][-3:-1] == [2, 3]")

def test_intlist_3(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][4:10] == []")

def test_intlist_4(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][-10:-5] == []")

def test_intlist_5(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][1:] == [2, 3, 4]")

def test_intlist_6(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][-3:] == [2, 3, 4]")

def test_intlist_7(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][4:] == []")

def test_intlist_8(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][-10:] == [1, 2, 3, 4]")

def test_intlist_9(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][:3] == [1, 2, 3]")

def test_intlist_10(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][:-1] == [1, 2, 3]")

def test_intlist_11(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][:10] == [1, 2, 3, 4]")

def test_intlist_12(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][:-5] == []")

def test_intlist_13(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][:] == [1, 2, 3, 4]")

def test_intlist_14(config_data):
	check_vsql(config_data, "[1, 2, 3, 4][None:None] == [1, 2, 3, 4]")

def test_numberlist_1(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][1:3] == [2.2, 3.3]")

def test_numberlist_2(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][-3:-1] == [2.2, 3.3]")

def test_numberlist_3(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][4:10] == []")

def test_numberlist_4(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][-10:-5] == []")

def test_numberlist_5(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][1:] == [2.2, 3.3, 4.4]")

def test_numberlist_6(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][-3:] == [2.2, 3.3, 4.4]")

def test_numberlist_7(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][4:] == []")

def test_numberlist_8(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][-10:] == [1.1, 2.2, 3.3, 4.4]")

def test_numberlist_9(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][:3] == [1.1, 2.2, 3.3]")

def test_numberlist_10(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][:-1] == [1.1, 2.2, 3.3]")

def test_numberlist_11(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][:10] == [1.1, 2.2, 3.3, 4.4]")

def test_numberlist_12(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][:-5] == []")

def test_numberlist_13(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][:] == [1.1, 2.2, 3.3, 4.4]")

def test_numberlist_14(config_data):
	check_vsql(config_data, "[1.1, 2.2, 3.3, 4.4][None:None] == [1.1, 2.2, 3.3, 4.4]")

def test_datelist_1(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][1:3] == [{d2}, {d3}]")

def test_datelist_2(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][-3:-1] == [{d2}, {d3}]")

def test_datelist_3(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][4:10] == []")

def test_datelist_4(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][-10:-5] == []")

def test_datelist_5(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][1:] == [{d2}, {d3}, {d4}]")

def test_datelist_6(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][-3:] == [{d2}, {d3}, {d4}]")

def test_datelist_7(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][4:] == []")

def test_datelist_8(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][-10:] == [{d1}, {d2}, {d3}, {d4}]")

def test_datelist_9(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][:3] == [{d1}, {d2}, {d3}]")

def test_datelist_10(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][:-1] == [{d1}, {d2}, {d3}]")

def test_datelist_11(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][:10] == [{d1}, {d2}, {d3}, {d4}]")

def test_datelist_12(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][:-5] == []")

def test_datelist_13(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][:] == [{d1}, {d2}, {d3}, {d4}]")

def test_datelist_14(config_data):
	check_vsql(config_data, f"[{d1}, {d2}, {d3}, {d4}][None:None] == [{d1}, {d2}, {d3}, {d4}]")

def test_datetimelist_1(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][1:3] == [{dt2}, {dt3}]")

def test_datetimelist_2(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][-3:-1] == [{dt2}, {dt3}]")

def test_datetimelist_3(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][4:10] == []")

def test_datetimelist_4(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][-10:-5] == []")

def test_datetimelist_5(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][1:] == [{dt2}, {dt3}, {dt4}]")

def test_datetimelist_6(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][-3:] == [{dt2}, {dt3}, {dt4}]")

def test_datetimelist_7(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][4:] == []")

def test_datetimelist_8(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][-10:] == [{dt1}, {dt2}, {dt3}, {dt4}]")

def test_datetimelist_9(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][:3] == [{dt1}, {dt2}, {dt3}]")

def test_datetimelist_10(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][:-1] == [{dt1}, {dt2}, {dt3}]")

def test_datetimelist_11(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][:10] == [{dt1}, {dt2}, {dt3}, {dt4}]")

def test_datetimelist_12(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][:-5] == []")

def test_datetimelist_13(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][:] == [{dt1}, {dt2}, {dt3}, {dt4}]")

def test_datetimelist_14(config_data):
	check_vsql(config_data, f"[{dt1}, {dt2}, {dt3}, {dt4}][None:None] == [{dt1}, {dt2}, {dt3}, {dt4}]")

def test_nulllist_1(config_data):
	check_vsql(config_data, f"[None, None, None, None][1:3] == [None, None]")

def test_nulllist_2(config_data):
	check_vsql(config_data, f"[None, None, None, None][-3:-1] == [None, None]")

def test_nulllist_3(config_data):
	check_vsql(config_data, f"[None, None, None, None][4:10] == []")

def test_nulllist_4(config_data):
	check_vsql(config_data, f"[None, None, None, None][-10:-5] == []")

def test_nulllist_5(config_data):
	check_vsql(config_data, f"[None, None, None, None][1:] == [None, None, None]")

def test_nulllist_6(config_data):
	check_vsql(config_data, f"[None, None, None, None][-3:] == [None, None, None]")

def test_nulllist_7(config_data):
	check_vsql(config_data, f"[None, None, None, None][4:] == []")

def test_nulllist_8(config_data):
	check_vsql(config_data, f"[None, None, None, None][-10:] == [None, None, None, None]")

def test_nulllist_9(config_data):
	check_vsql(config_data, f"[None, None, None, None][:3] == [None, None, None]")

def test_nulllist_10(config_data):
	check_vsql(config_data, f"[None, None, None, None][:-1] == [None, None, None]")

def test_nulllist_11(config_data):
	check_vsql(config_data, f"[None, None, None, None][:10] == [None, None, None, None]")

def test_nulllist_12(config_data):
	check_vsql(config_data, f"[None, None, None, None][:-5] == []")

def test_nulllist_13(config_data):
	check_vsql(config_data, f"[None, None, None, None][:] == [None, None, None, None]")

def test_nulllist_14(config_data):
	check_vsql(config_data, f"[None, None, None, None][None:None] == [None, None, None, None]")

def test_nulllist_15(config_data):
	check_vsql(config_data, f"[][:] == []")
