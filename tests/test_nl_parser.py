from app.nl_parser import parse_natural_language_config


def test_via_lactea_preset():
    changes, matches = parse_natural_language_config(
        "Configure uma galáxia parecida com a Via Láctea"
    )
    assert changes["log_m200"] == 12.0
    assert changes["concentration"] == 9.4


def test_dwarf_preset():
    changes, _ = parse_natural_language_config(
        "Galáxia anã com M200 de 10^9.5, núcleo 0.8 kpc"
    )
    assert abs(changes["log_m200"] - 9.5) < 0.01
    assert abs(changes["core_radius_kpc"] - 0.8) < 0.01


def test_cluster_with_feedback():
    changes, _ = parse_natural_language_config(
        "Aglomerado com M200 1e15, concentração 4, feedback 0.4"
    )
    assert abs(changes["log_m200"] - 15.0) < 0.01
    assert abs(changes["feedback_strength"] - 0.4) < 0.01
