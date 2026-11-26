"""Export recorded relationships without inferring scientific support or running providers."""

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from ._sources import SourceCatalog, SourceEntry, digest, load_case
from .catalog import Catalog, _normalized_distribution, load_record, package_catalog
from .coverage import _local, _relative


def _identity(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _pointer(*parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _source(provider, path, sha256, kind, version):
    return {"id": _identity(provider, path, sha256, kind), "provider": provider,
            "path": path, "sha256": sha256, "kind": kind, "version": version}


def _contract_source(entry):
    return _source(entry.provider, entry.path, entry.sha256, "contract", entry.contract.schema_version)


def _node_id(source, kind, key, revision=None, parent=None):
    parts = (source["id"], kind, key, revision)
    return _identity(*parts, parent) if parent is not None else _identity(*parts)


class _Graph:
    """Small directed multigraph; only the input provenance subgraph is a DAG."""

    def __init__(self):
        self.sources = {}
        self.nodes = {}
        self.edges = {}
        self.selections = []

    @staticmethod
    def _put(collection, item):
        previous = collection.setdefault(item["id"], item)
        if previous != item:
            raise ValueError(f"Conflicting graph identity: {item['id']}")
        return item["id"]

    def source(self, source):
        self._put(self.sources, source)
        return source

    def node(self, source, kind, key, record, pointer, revision=None, label=None, parent=None):
        self.source(source)
        reference = {"provider": source["provider"], "path": source["path"],
                     "type": kind, "id": key, "revision": revision}
        if parent is not None:
            reference["parent"] = parent
        return self._put(self.nodes, {
            "id": _node_id(source, kind, key, revision, parent), "type": kind, "label": label or key,
            "ref": reference,
            "origin": {"source": source["id"], "pointer": pointer}, "record": record,
        })

    def edge(self, start, end, kind, source, pointer, data=None):
        origin = {"source": source["id"], "pointer": pointer}
        return self._put(self.edges, {
            "id": _identity(start, end, kind, origin), "type": kind,
            "source": start, "target": end, "origin": origin, "data": data or {},
        })

    def contract(self, entry):
        c = entry.contract
        source = _contract_source(entry)
        data = c.model_dump(mode="json")
        model_record = {k: data[k] for k in ("model", "assumptions", "domains", "limitations")}
        if data.get("migration") is not None:
            model_record["migration"] = data["migration"]
        model = self.node(source, "model", c.model.id, model_record, "", label=c.model.name)
        collections = {"claim": "claims", "evidence": "evidence", "subject": "subjects",
                       "context": "contexts", "condition": "conditions", "assessment": "assessments",
                       "follow_up": "follow_ups", "resolution": "follow_up_resolutions",
                       "equation": "equations", "binding": "bindings", "decision": "decisions",
                       "quantity": "quantities", "mathematical_model": "mathematical_models"}
        versioned = {"claim", "condition", "equation", "decision", "quantity", "mathematical_model"}

        def node_id(kind, key, revision=None):
            return _node_id(source, kind, key, revision)

        def link(start, kind, key, relation, pointer, revision=None, data=None):
            return self.edge(start, node_id(kind, key, revision), relation, source, pointer, data)

        for kind, collection in collections.items():
            for i, record in enumerate(data.get(collection, [])):
                key = record["follow_up"] if kind == "resolution" else record["id"]
                revision = record.get("revision") if kind in versioned else None
                pointer = _pointer(collection, i)
                identifier = self.node(source, kind, key, record, pointer, revision)
                self.edge(model, identifier, "contains", source, pointer)
                if kind == "mathematical_model":
                    parent = {"id": key, "revision": revision}
                    aliases = {}
                    for alias, quantity in record["quantities"].items():
                        local_pointer = _pointer(collection, i, "quantities", alias)
                        aliases[alias] = self.node(source, "model_quantity", alias, quantity,
                                                  local_pointer, parent=parent)
                        self.edge(identifier, aliases[alias], "uses_quantity", source, local_pointer)
                        ref = quantity["quantity"]
                        link(aliases[alias], "quantity", ref["id"], "defines_quantity",
                             local_pointer + "/quantity", ref["revision"])
                    for j, relation in enumerate(record["relations"]):
                        local_pointer = _pointer(collection, i, "relations", j)
                        relation_node = self.node(source, "relation_instance", relation["id"], relation,
                                                  local_pointer, parent=parent)
                        self.edge(identifier, relation_node, "adopts_relation", source, local_pointer)
                        ref = relation["equation"]
                        link(relation_node, "equation", ref["id"], "uses_definition",
                             local_pointer + "/equation", ref["revision"])
                        for symbol, alias in relation["quantities"].items():
                            self.edge(relation_node, aliases[alias], "involves_quantity", source,
                                      local_pointer + "/quantities/" + _pointer(symbol)[1:],
                                      {"symbol": symbol, "directed": False})
                if kind == "decision":
                    parent = {"id": key, "revision": revision}
                    for j, option in enumerate(record["options"]):
                        option_pointer = _pointer(collection, i, "options", j)
                        target = self.node(source, "decision_option", option["id"], option,
                                           option_pointer, revision, parent=parent)
                        self.edge(identifier, target, "considers", source, option_pointer)
                        if option["id"] == record["selected"]:
                            self.edge(identifier, target, "selects", source,
                                      _pointer(collection, i, "selected"))

        # These unkeyed records stay in the model payload, with field-level edge origins.
        for collection in ("assumptions", "domains", "limitations"):
            for i, record in enumerate(data[collection]):
                for j, key in enumerate(record["evidence"]):
                    link(model, "evidence", key, "uses_evidence", _pointer(collection, i, "evidence", j))

        for kind, collection in collections.items():
            for i, record in enumerate(data.get(collection, [])):
                key = record["follow_up"] if kind == "resolution" else record["id"]
                revision = record.get("revision") if kind in versioned else None
                start = node_id(kind, key, revision)

                def field(*parts):
                    return _pointer(collection, i, *parts)

                for j, evidence in enumerate(record.get("evidence", [])):
                    link(start, "evidence", evidence, "uses_evidence", field("evidence", j))
                for target_kind in ("subject", "context"):
                    if record.get(target_kind) is not None:
                        link(start, target_kind, record[target_kind], "has_" + target_kind, field(target_kind))
                if kind == "claim":
                    for j, equation in enumerate(record.get("equations", [])):
                        link(start, "equation", equation["id"], "refers_to_equation",
                             field("equations", j), equation["revision"])
                    for j, ref in enumerate(record.get("mathematical_models", [])):
                        link(start, "mathematical_model", ref["id"], "refers_to_mathematical_model",
                             field("mathematical_models", j), ref["revision"])
                elif kind == "quantity":
                    for j, ref in enumerate(record["coordinates"]):
                        link(start, "quantity", ref["id"], "has_coordinate",
                             field("coordinates", j), ref["revision"])
                elif kind == "binding":
                    equation = record["equation"]
                    link(start, "equation", equation["id"], "binds_equation", field("equation"),
                         equation["revision"])
                if kind == "evidence" and record.get("provenance"):
                    for j, parent in enumerate(record["provenance"]["derived_from"]):
                        link(start, "evidence", parent["evidence"], "derived_from",
                             field("provenance", "derived_from", j),
                             data={"comparison": parent["comparison"], "note": parent["note"]})
                if kind == "assessment":
                    target_kind = "claim" if record["kind"] == "evidence_support" else "condition"
                    link(start, target_kind, record[target_kind], "assesses", field(target_kind),
                         record[target_kind + "_revision"])
                    for j, pin in enumerate(record.get("equation_pins", [])):
                        link(start, "equation", pin["id"], "pins_equation", field("equation_pins", j),
                             pin["revision"], data={"sha256": pin["sha256"]})
                    for j, pin in enumerate(record.get("binding_pins", [])):
                        link(start, "binding", pin["id"], "pins_binding", field("binding_pins", j),
                             data={"sha256": pin["sha256"]})
                    for j, pin in enumerate(record.get("mathematical_model_pins", [])):
                        link(start, "mathematical_model", pin["id"], "pins_mathematical_model",
                             field("mathematical_model_pins", j), pin["revision"],
                             data={"sha256": pin["sha256"]})
                elif kind == "follow_up":
                    link(start, record["target_kind"], record["target"], "targets", field("target"),
                         record["revision"])
                elif kind == "resolution":
                    link(start, "follow_up", record["follow_up"], "resolves", field("follow_up"))
                elif kind == "decision":
                    for j, basis in enumerate(record["basis"]):
                        link(start, basis["kind"], basis["id"], "based_on", field("basis", j),
                             data={"sha256": basis["sha256"]})
                    if record["supersedes"] is not None:
                        previous = record["supersedes"]
                        link(start, "decision", previous["id"], "supersedes", field("supersedes"),
                             previous["revision"])
        return model

    def case(self, case, source):
        """The same case/component graph is consumed by JSON and documentation."""
        record = case.model_dump(mode="json")
        case_node = self.node(source, "case", case.id, record, "", label=case.title)
        components = {}
        for key, component in case.components.items():
            pointer = _pointer("components", key)
            components[key] = self.node(source, "component", key, component.model_dump(mode="json"), pointer)
            self.edge(case_node, components[key], "selects", source, pointer)
        for i, connection in enumerate(case.connections):
            self.edge(components[connection.consumer], components[connection.dependency], "requires",
                      source, _pointer("connections", i),
                      {"quantity": connection.quantity, "description": connection.description})
        return case_node, components

    def case_selections(self, case, source, entries, legacy, catalog):
        case_node, components = self.case(case, source)
        for key, component in case.components.items():
            entry = entries[key]
            pointer = _pointer("components", key)
            selected = {"kind": "case_component", "origin": {"source": source["id"], "pointer": pointer},
                        "component": components[key], "model": None, "subject": None,
                        "context": None, "assessments": [], "registration": "unregistered"}
            if entry is not None:
                target = _contract_source(entry)
                selected.update(model=self.contract(entry), registration="registered")
                self.edge(components[key], selected["model"], "selects", source, pointer)
                for kind in ("subject", "context"):
                    value = getattr(component, kind)
                    if value is not None:
                        selected[kind] = _node_id(target, kind, value)
                        self.edge(components[key], selected[kind], "has_" + kind,
                                  source, pointer + "/" + kind)
                for i, value in enumerate(component.assessments):
                    identifier = _node_id(target, "assessment", value)
                    selected["assessments"].append(identifier)
                    self.edge(components[key], identifier, "selects", source, pointer + f"/assessments/{i}")
            self.selections.append(selected)
        if legacy is not None:
            ref = case.legacy_case
            legacy_source = self.source(_source(ref.provider, ref.path, ref.sha256, "manual_case", "0.1"))
            snapshot = self.node(legacy_source, "manual_case", legacy.get("id", ref.path), legacy, "")
            self.edge(case_node, snapshot, "uses_record", source, "/legacy_case")
            for i, record in enumerate(legacy["assessments"]):
                pointer = _pointer("assessments", i)
                node = self.node(legacy_source, "manual_assessment", record["id"], record, pointer)
                self.edge(snapshot, node, "contains", legacy_source, pointer)
                for j, locator in enumerate(record["evidence"]):
                    path, _, key = locator.partition("#")
                    entry = catalog.entries[(ref.provider, path)]
                    self.edge(node, _node_id(_contract_source(entry), "evidence", key), "uses_evidence",
                              legacy_source, pointer + f"/evidence/{j}")

    def result(self):
        for edge in self.edges.values():
            if edge["source"] not in self.nodes or edge["target"] not in self.nodes:
                raise ValueError(f"Unknown graph endpoint: {edge['id']}")
        return {"format": "mceg_graph_v1",
                "sources": sorted(self.sources.values(), key=lambda r: r["id"]),
                "nodes": sorted(self.nodes.values(), key=lambda r: r["id"]),
                "edges": sorted(self.edges.values(), key=lambda r: r["id"]),
                "selections": sorted(self.selections, key=lambda r: json.dumps(r, sort_keys=True))}


def _contract_graph(entry):
    graph = _Graph()
    graph.contract(entry)
    return graph.result()


def _case_graph(case):
    # Rendering an already validated Case needs no output directory or source file.
    graph = _Graph()
    source = _source(None, None, _identity(case.model_dump(mode="json")), "inline_case", case.format)
    graph.case(case, source)
    return graph.result()


def build_graph(*, paths=(), provider="local", root=".", cases=(), package=None, catalog=None) -> dict:
    """Return a JSON-ready snapshot of explicit records and selections.

    Local contract/case paths resolve from root. Case provider roots resolve from
    the case file. Package/catalog inputs cannot be mixed with local inputs.
    No provider code is imported or executed, and external locators are not
    followed. Catalog-listed files and case pins retain their existing checks.
    """
    if isinstance(paths, (str, Path)) or isinstance(cases, (str, Path)):
        raise ValueError("paths and cases must be sequences of paths")
    paths, cases = list(paths), list(cases)
    if package is not None and catalog is not None:
        raise ValueError("Choose --package or --catalog")
    if (package is not None or catalog is not None) and (paths or cases or provider != "local" or Path(root) != Path(".")):
        raise ValueError("Package/catalog lookup cannot be combined with local paths, cases, provider or root")
    if not paths and not cases and package is None and catalog is None:
        raise ValueError("Provide contract paths, --case, --package or --catalog")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("Provide a nonempty provider namespace")
    graph = _Graph()
    sources = SourceCatalog()
    distribution = None
    if package is not None:
        catalog, distribution = package_catalog(package)
    if catalog is not None:
        catalog = Path(catalog).resolve()
        payload = catalog.read_bytes()
        index = Catalog.model_validate_json(payload)
        if distribution and _normalized_distribution(index.provider) != _normalized_distribution(distribution["name"]):
            raise ValueError("Catalog provider does not match the selected distribution")
        source = graph.source(_source(index.provider, catalog.name, hashlib.sha256(payload).hexdigest(),
                                      "catalog", index.schema_version))
        source.update(record_version=index.record_version, distribution=distribution)
        for i, model in enumerate(index.models):
            for j, record in enumerate(model.records):
                _, contract, assessments, _ = load_record(catalog.parent, record)
                entry = SourceEntry(index.provider, catalog.parent, record.path, record.sha256, contract)
                model_id = graph.contract(entry)
                graph.selections.append({
                    "kind": "catalog_record", "origin": {"source": source["id"], "pointer": _pointer("models", i, "records", j)},
                    "catalog_model": model.model_dump(mode="json", exclude={"records"}),
                    "record": record.model_dump(mode="json"), "model": model_id,
                    "assessments": [_node_id(_contract_source(entry), "assessment", a.id) for a in assessments],
                })
    else:
        root = Path(root).resolve()

        def local_path(path):
            path = Path(path)
            absolute = path if path.is_absolute() else root / path
            # Preserve lexical paths so shared loaders can reject symlink components.
            try:
                relative = absolute.relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError("Input path is outside root; supply --root explicitly") from exc
            return _local(root, _relative(relative)), relative

        for path in paths:
            _, relative = local_path(path)
            graph.contract(sources.add(provider, root, relative))
        case_ids = set()
        for path in cases:
            absolute, relative = local_path(path)
            case, entries, legacy = load_case(absolute, sources)
            if case.id in case_ids:
                raise ValueError(f"Duplicate case IDs: {case.id}")
            case_ids.add(case.id)
            source = _source(provider, relative, digest(absolute), "case", case.format)
            graph.case_selections(case, source, entries, legacy, sources)
    result = graph.result()
    # Legacy manual-case payloads are untyped; reject non-JSON values in the API too.
    json.dumps(result, allow_nan=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mceg graph", description=
                                     "Export recorded relationships as Graph JSON; no scientific judgment is inferred.")
    parser.add_argument("paths", nargs="*", type=Path, help="Contract paths relative to --root")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--package", help="Installed distribution with an MCEG catalog")
    group.add_argument("--catalog", type=Path, help="Provider-owned mceg/index.json")
    parser.add_argument("--case", action="append", default=[], type=Path, dest="cases", help="Calculation case (repeatable)")
    parser.add_argument("--provider", default="local", help="Local source namespace (default: local)")
    parser.add_argument("--root", type=Path, default=Path("."), help="Local source root (default: current directory)")
    args = parser.parse_args(argv)
    try:
        report = build_graph(**vars(args))
        output = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        parser.exit(1, f"mceg graph: {exc}\n")
    print(output)
    return 0
