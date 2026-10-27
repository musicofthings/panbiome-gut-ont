"""The EPI2ME parameter schema must stay in sync with nextflow.config."""
import json
import os
import re

import jsonschema

ROOT = os.path.join(os.path.dirname(__file__), "..")


def config_params():
    txt = open(os.path.join(ROOT, "nextflow.config")).read()
    block = re.search(r"\nparams \{(.*?)\n\}\n", txt, re.S).group(1)
    return set(re.findall(r"^\s{4}([a-z0-9_]+)\s*=", block, re.M))


def schema_params(schema):
    out = {}
    for d in schema["definitions"].values():
        out.update(d["properties"])
    return out


def test_schema_is_valid_and_complete():
    schema = json.load(open(os.path.join(ROOT, "nextflow_schema.json")))
    jsonschema.Draft7Validator.check_schema(schema)
    cfg, sch = config_params(), schema_params(schema)
    assert cfg - set(sch) == set(), "params missing from schema: %s" % sorted(cfg - set(sch))
    assert set(sch) - cfg == set(), "schema params not in config: %s" % sorted(set(sch) - cfg)
    for name, spec in sch.items():
        assert "description" in spec and "type" in spec, name


def test_schema_defaults_match_config():
    full = open(os.path.join(ROOT, "nextflow.config")).read()
    txt = re.search(r"\nparams \{(.*?)\n\}\n", full, re.S).group(1)
    schema = json.load(open(os.path.join(ROOT, "nextflow_schema.json")))
    for name, spec in schema_params(schema).items():
        if "default" not in spec:
            continue
        m = re.search(r"^\s{4}%s\s*=\s*(.+?)(?:\s*//.*)?$" % re.escape(name), txt, re.M)
        assert m, name
        raw = m.group(1).strip().strip("'\"")
        d = spec["default"]
        if isinstance(d, bool):
            assert raw == str(d).lower(), (name, raw, d)
        elif isinstance(d, (int, float)):
            assert float(raw) == float(d), (name, raw, d)
        else:
            assert raw == d, (name, raw, d)
