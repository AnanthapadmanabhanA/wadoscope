from wadoscope.web import qido


def test_path_builders():
    assert qido.studies_path() == "/studies"
    assert qido.series_path("1.2.3") == "/studies/1.2.3/series"
    assert qido.instances_path("1.2", "4.5") == "/studies/1.2/series/4.5/instances"


def test_build_params_includes_filters_and_limit():
    p = qido.build_params({"PatientID": "42"}, limit=5)
    assert p["PatientID"] == "42"
    assert p["limit"] == "5"
    assert p["includefield"] == "all"


def test_flatten_person_name_and_tags():
    ds = {
        "00100010": {"vr": "PN", "Value": [{"Alphabetic": "DOE^JANE"}]},
        "00100020": {"vr": "LO", "Value": ["PID123"]},
        "0020000D": {"vr": "UI", "Value": ["1.2.840.1"]},
        "00080060": {"vr": "CS", "Value": ["CT"]},
    }
    out = qido.flatten(ds)
    assert out["PatientName"] == "DOE^JANE"
    assert out["PatientID"] == "PID123"
    assert out["StudyInstanceUID"] == "1.2.840.1"
    assert out["Modality"] == "CT"


def test_flatten_ignores_empty():
    assert qido.flatten({"00100010": {"vr": "PN"}}) == {}
