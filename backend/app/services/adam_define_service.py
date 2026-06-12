"""Generate CDISC Define-XML 2.1 for ADaM dataset artifact content."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from xml.dom import minidom

from fastapi import HTTPException, status

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

ET.register_namespace("", ODM_NS)
ET.register_namespace("def", DEF_NS)
ET.register_namespace("xlink", XLINK_NS)

_ADAM_DOCUMENT_TYPES = frozenset({"ADAM_DATASET", "ADAM_SPECIFICATION"})


def build_adam_define_xml(content: dict) -> str:
    """
    Build a CDISC Define-XML 2.1 document from ADaM artifact JSON content.

    Generates ODM-based Define-XML with AnalysisDatasets, variable metadata,
    origins, computational methods, and display formats where present.
    """
    document_type = content.get("document_type", "")
    if document_type not in _ADAM_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOT_ADAM",
                "message": "Artifact content is not an ADaM dataset document.",
            },
        )

    datasets = content.get("datasets", [])
    if not datasets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_DATASETS",
                "message": "ADaM artifact has no datasets to export.",
            },
        )

    study_id = content.get("protocol_number") or content.get("study_name") or "STUDY"
    study_name = content.get("study_name") or study_id
    ig_version = content.get("adam_ig_version", "1.3")

    root = ET.Element(
        "ODM",
        attrib={
            "ODMVersion": "1.3.2",
            "FileType": "Snapshot",
            "FileOID": f"ADAM.DEFINE.{study_id}",
            "CreationDateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )

    study_el = ET.SubElement(root, "Study", attrib={"OID": f"ST.{study_id}"})
    globals_el = ET.SubElement(study_el, "GlobalVariables")
    ET.SubElement(globals_el, "StudyName").text = str(study_name)
    ET.SubElement(
        globals_el, "StudyDescription"
    ).text = f"ADaM IG {ig_version} analysis dataset definitions"
    ET.SubElement(globals_el, "ProtocolName").text = str(study_id)

    mdv = ET.SubElement(
        study_el,
        "MetaDataVersion",
        attrib={
            "OID": f"MDV.{study_id}",
            "Name": f"ADaM IG {ig_version}",
            f"{{{DEF_NS}}}DefineVersion": "2.1.0",
            f"{{{DEF_NS}}}StandardName": "ADaM-IG",
            f"{{{DEF_NS}}}StandardVersion": ig_version,
        },
    )

    analysis_datasets = ET.SubElement(mdv, f"{{{DEF_NS}}}AnalysisDatasets")
    method_defs: dict[str, dict] = {}
    item_defs: dict[str, dict] = {}

    for dataset in datasets:
        dataset_code = dataset.get("dataset", "UNK")
        ig_oid = f"IG.{dataset_code}"
        dataset_label = dataset.get("label", dataset_code)
        structure = dataset.get("structure", "One record per subject")

        analysis_ds = ET.SubElement(
            analysis_datasets,
            f"{{{DEF_NS}}}AnalysisDataset",
        )
        ET.SubElement(
            analysis_ds,
            f"{{{DEF_NS}}}DatasetName",
        ).text = dataset_code.lower()
        ET.SubElement(
            analysis_ds,
            f"{{{DEF_NS}}}ItemGroupOID",
        ).text = ig_oid

        ig = ET.SubElement(
            mdv,
            "ItemGroupDef",
            attrib={
                "OID": ig_oid,
                "Name": dataset_code,
                "Repeating": "No",
                "IsReferenceData": "No",
                "Purpose": "Analysis",
                f"{{{DEF_NS}}}Structure": structure,
                f"{{{DEF_NS}}}Class": _infer_adam_class(dataset_code),
                f"{{{DEF_NS}}}ArchiveLocationID": f"LF.{dataset_code}",
            },
        )
        desc = ET.SubElement(ig, "Description")
        ET.SubElement(
            desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = dataset_label

        leaf = ET.SubElement(
            mdv,
            f"{{{DEF_NS}}}leaf",
            attrib={
                "ID": f"LF.{dataset_code}",
                f"{{{XLINK_NS}}}href": f"{dataset_code.lower()}.xpt",
            },
        )
        ET.SubElement(leaf, f"{{{DEF_NS}}}title").text = dataset_label

        variables = list(_iter_dataset_variables(dataset))
        for order, var in enumerate(variables, start=1):
            normalized = _normalize_variable(var, dataset_code)
            item_oid = f"IT.{dataset_code}.{normalized['name']}"
            item_defs[item_oid] = normalized

            item_ref_attrs: dict[str, str] = {
                "ItemOID": item_oid,
                "Mandatory": (
                    "Yes" if normalized["name"] in {"STUDYID", "USUBJID"} else "No"
                ),
                "OrderNumber": str(order),
            }
            if normalized["derivation"]:
                method_oid = f"MT.{dataset_code}.{normalized['name']}"
                method_defs[method_oid] = {
                    "name": normalized["name"],
                    "derivation": normalized["derivation"],
                    "dataset": dataset_code,
                }
                item_ref_attrs["MethodOID"] = method_oid

            item_ref = ET.SubElement(ig, "ItemRef", attrib=item_ref_attrs)
            origin_attrs: dict[str, str] = {"Type": normalized["origin"]}
            if normalized.get("origin_source"):
                origin_attrs["Source"] = normalized["origin_source"]
            ET.SubElement(item_ref, "Origin", attrib=origin_attrs)

    for item_oid, var in item_defs.items():
        _, dataset_code, var_name = item_oid.split(".", 2)
        item_attrs: dict[str, str] = {
            "OID": item_oid,
            "Name": var_name,
            "DataType": var["data_type"],
            "Length": var["length"],
        }
        if var["description"]:
            item_attrs["Comment"] = var["description"]

        item_def = ET.SubElement(mdv, "ItemDef", attrib=item_attrs)
        item_desc = ET.SubElement(item_def, "Description")
        ET.SubElement(
            item_desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = var["label"]

        if var.get("display_format"):
            ET.SubElement(
                item_def,
                f"{{{DEF_NS}}}AnalysisVariableDisplayFormat",
            ).text = var["display_format"]

    for method_oid, method in sorted(method_defs.items()):
        method_def = ET.SubElement(
            mdv,
            f"{{{DEF_NS}}}MethodDef",
            attrib={
                "OID": method_oid,
                "Name": method["name"],
                "Type": "Computation",
            },
        )
        method_desc = ET.SubElement(method_def, "Description")
        ET.SubElement(
            method_desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = method["derivation"]
        expr = ET.SubElement(
            method_def,
            f"{{{DEF_NS}}}FormalExpression",
            attrib={"Context": "SAS"},
        )
        ET.SubElement(expr, "Code").text = method["derivation"]

    meta = ET.SubElement(root, "MetaData")
    ET.SubElement(meta, "StudyID").text = str(study_id)
    ET.SubElement(meta, "DefineXMLVersion").text = "2.1"
    ET.SubElement(meta, "ValidationEngine").text = content.get(
        "validation_engine", "internal"
    )

    rough = ET.tostring(root, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def _infer_adam_class(dataset_code: str) -> str:
    code = dataset_code.upper()
    if code == "ADSL":
        return "SUBJECT LEVEL ANALYSIS DATASET"
    if code.startswith("ADAE") or code == "ADAE":
        return "OCCURRENCE DATA STRUCTURE"
    if code in {"ADLB", "ADVS", "ADEG"}:
        return "BASIC DATA STRUCTURE"
    if code.startswith("ADTTE"):
        return "BASIC DATA STRUCTURE"
    return "ANALYSIS DATASET"


def _iter_dataset_variables(dataset: dict):
    for var in dataset.get("variables", []):
        yield var
    for flag in dataset.get("population_flags", []):
        yield {
            "variable": flag.get("variable", "UNK"),
            "label": flag.get("label", flag.get("variable", "Population Flag")),
            "derivation": flag.get("derivation", ""),
            "origin": "Derived",
            "type": "Char",
            "notes": "Population flag",
        }


def _normalize_variable(var_spec: str | dict, dataset_code: str) -> dict:
    if isinstance(var_spec, str):
        name = var_spec
        spec: dict = {}
    else:
        name = var_spec.get("variable") or var_spec.get("name") or "UNK"
        spec = var_spec

    derivation = spec.get("derivation") or ""
    description = spec.get("notes") or spec.get("description") or ""
    origin = spec.get("origin") or _infer_origin(name, derivation)
    display_format = spec.get("display_format") or spec.get("format") or ""

    return {
        "name": name,
        "label": spec.get("label") or name,
        "data_type": _infer_data_type(name, spec),
        "length": str(spec.get("length") or _default_length(name)),
        "derivation": derivation.strip() if derivation else "",
        "description": description.strip() if description else "",
        "origin": _map_origin(origin, derivation),
        "origin_source": _default_origin_source(origin),
        "display_format": display_format.strip() if display_format else "",
    }


def _infer_origin(name: str, derivation: str) -> str:
    if derivation:
        return "Derived"
    if name in {"STUDYID", "USUBJID", "SUBJID"}:
        return "Assigned"
    return "Collected"


def _map_origin(origin: str, derivation: str) -> str:
    normalized = origin.strip().upper()
    if normalized.startswith("SDTM") or derivation:
        return "Derived"
    mapping = {
        "ASSIGNED": "Assigned",
        "COLLECTED": "Collected",
        "DERIVED": "Derived",
        "PREDECESSOR": "Predecessor",
        "PROTOCOL": "Protocol",
    }
    return mapping.get(normalized, "Derived" if derivation else "Collected")


def _default_origin_source(origin: str) -> str | None:
    if origin == "Assigned":
        return "Sponsor"
    if origin == "Collected":
        return "Investigator"
    if origin == "Derived":
        return "Sponsor"
    return None


def _infer_data_type(name: str, spec: dict) -> str:
    if spec.get("type"):
        type_map = {
            "char": "text",
            "num": "float",
            "number": "float",
            "integer": "integer",
            "date": "date",
            "datetime": "datetime",
        }
        return type_map.get(str(spec["type"]).lower(), "text")
    if name.endswith("DTC") or name.endswith("DT"):
        return "date"
    if name.endswith("FL"):
        return "text"
    if name in {"AGE", "AVAL", "CHG", "BASE"}:
        return "float"
    return "text"


def _default_length(name: str) -> int:
    if name in {"STUDYID", "USUBJID", "SUBJID"}:
        return 40
    if name.endswith("FL"):
        return 1
    return 200
