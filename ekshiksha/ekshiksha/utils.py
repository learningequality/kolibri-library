import json
import os


ROMAN = [
    (1000, "M"),
    ( 900, "CM"),
    ( 500, "D"),
    ( 400, "CD"),
    ( 100, "C"),
    (  90, "XC"),
    (  50, "L"),
    (  40, "XL"),
    (  10, "X"),
    (   9, "IX"),
    (   5, "V"),
    (   4, "IV"),
    (   1, "I"),
]

def int_to_roman(number):
    """
    Converts a decimal number into a roman numeral.

    :param number: Integer number to convert
    :return: Roman numeral string.
    """
    result = ""
    for (arabic, roman) in ROMAN:
        (factor, number) = divmod(number, arabic)
        result += roman * factor
    return result


def js_to_json(js_text):
    """
    Takes a JS file in the form of 'var objectName = {...};' and converts it into a dictionary
    in the form of {'objectName': {...}}.
    :param js_filename: The filename of a JS file containing only a single variable definition.
    :return: A python dictionary
    """

    first_equals = js_text.find('=')
    var_name = js_text[:first_equals].strip()
    var_value = js_text[first_equals+1:].strip()

    # remove the 'var' from the name
    var_name = var_name[3:].strip()

    return {var_name: json.loads(var_value)}


def js_file_to_json(js_filename):
    return js_to_json(open(js_filename).read())
