from src.converters.talend_to_v1.type_mapping import convert_type


def test_string_types():
    assert convert_type("id_String") == "str"
    assert convert_type("id_Character") == "str"


def test_integer_types():
    assert convert_type("id_Integer") == "int"
    assert convert_type("id_Long") == "int"
    assert convert_type("id_Byte") == "int"
    assert convert_type("id_Short") == "int"


def test_float_types():
    assert convert_type("id_Double") == "float"
    assert convert_type("id_Float") == "float"


def test_other_types():
    assert convert_type("id_Boolean") == "bool"
    assert convert_type("id_Date") == "datetime"
    assert convert_type("id_BigDecimal") == "Decimal"
    assert convert_type("id_Object") == "object"


def test_unknown_type_defaults_to_str():
    assert convert_type("id_SomeUnknown") == "str"
    assert convert_type("") == "str"
