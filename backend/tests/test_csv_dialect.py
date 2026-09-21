import pytest
from csv_detector import CsvDialectDetector

def test_detect_comma_csv():
    data = b"Fecha,Cliente,Importe\n01/05/2026,Acme,\"1.200,50\"\n02/05/2026,Beta,\"3.400,00\"\n"
    res = CsvDialectDetector.analyze(data)
    assert res["delimiter"] == ","
    assert res["confidence"] >= 0.8
    assert res["confidence_level"] == "Alta"
    assert res["is_ambiguous"] is False

def test_detect_semicolon_european_csv():
    data = b"Fecha;Cliente;Importe;IVA\n01/05/2026;Acme Iberica;1250,50;262,60\n02/05/2026;Logistica;3400,00;714,00\n"
    res = CsvDialectDetector.analyze(data)
    assert res["delimiter"] == ";"
    assert res["col_count"] == 4
    assert res["confidence"] >= 0.85

def test_detect_tab_tsv():
    data = b"Fecha\tCliente\tImporte\n01/05/2026\tAcme\t1200.50\n02/05/2026\tBeta\t3400.00\n"
    res = CsvDialectDetector.analyze(data)
    assert res["delimiter"] == "\t"
    assert res["confidence"] >= 0.80
    assert res["confidence_level"] == "Alta"

def test_detect_pipe_delimited():
    data = b"ID|Nombre|Dpto|Salario\n101|Carlos|Ventas|2500,00\n102|Maria|Finanzas|3200,00\n103|Juan|IT|2900,00\n"
    res = CsvDialectDetector.analyze(data)
    assert res["delimiter"] == "|"
    assert res["col_count"] == 4
    assert res["confidence"] >= 0.85

def test_manual_override_delimiter():
    data = b"ID,Nombre,Email\n1,Carlos,carlos@test.com\n"
    res = CsvDialectDetector.analyze(data, manual_override_delimiter=";")
    assert res["delimiter"] == ";"
    assert res["confidence"] == 1.0

def test_utf8_bom_detection():
    data = b"\xef\xbb\xbfFecha,Importe\n01/05/2026,100\n"
    res = CsvDialectDetector.analyze(data)
    assert res["encoding"] == "utf-8-sig"
    assert res["delimiter"] == ","
