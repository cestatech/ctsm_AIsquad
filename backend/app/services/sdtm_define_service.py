"""Generate CDISC define.xml from SDTM dataset artifact content."""

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

# Representative CDISC CT codelist snapshot (NCI codes as of SDTM IG 3.3).
CDISC_CT_CODELISTS: dict[str, dict] = {
    "SEX": {
        "oid": "CL.SEX",
        "name": "SEX",
        "nci": "C66731",
        "data_type": "text",
        "items": [
            ("M", "Male"),
            ("F", "Female"),
            ("U", "Unknown"),
            ("UN", "Undifferentiated"),
        ],
    },
    "RACE": {
        "oid": "CL.RACE",
        "name": "RACE",
        "nci": "C74457",
        "data_type": "text",
        "items": [
            ("WHITE", "White"),
            ("BLACK", "Black or African American"),
            ("ASIAN", "Asian"),
            ("AMERICAN INDIAN OR ALASKA NATIVE", "American Indian or Alaska Native"),
            ("NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER", "Native Hawaiian or Other Pacific Islander"),
            ("OTHER", "Other"),
            ("MULTIPLE", "Multiple"),
            ("NOT REPORTED", "Not Reported"),
            ("UNKNOWN", "Unknown"),
        ],
    },
    "ETHNIC": {
        "oid": "CL.ETHNIC",
        "name": "ETHNIC",
        "nci": "C66790",
        "data_type": "text",
        "items": [
            ("HISPANIC OR LATINO", "Hispanic or Latino"),
            ("NOT HISPANIC OR LATINO", "Not Hispanic or Latino"),
            ("NOT REPORTED", "Not Reported"),
            ("UNKNOWN", "Unknown"),
        ],
    },
    "COUNTRY": {
        "oid": "CL.COUNTRY",
        "name": "COUNTRY",
        "nci": "C66734",
        "data_type": "text",
        "items": [
            ("USA", "United States"),
            ("CAN", "Canada"),
            ("GBR", "United Kingdom"),
            ("DEU", "Germany"),
            ("FRA", "France"),
            ("JPN", "Japan"),
        ],
    },
}

_ASSIGNED_VARIABLES = frozenset({"STUDYID", "DOMAIN", "USUBJID"})
_CODELIST_VARIABLES = frozenset(CDISC_CT_CODELISTS.keys())


def build_define_xml(content: dict) -> str:
    """
    Build a CDISC Define-XML 2.1 document from SDTM artifact JSON content.

    Generates ODM-based Define-XML with codelists, origins, computational
    methods, and value-level metadata where present in the artifact content.
    """
    if content.get("document_type") != "SDTM_DATASET":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOT_SDTM",
                "message": "Artifact content is not an SDTM_DATASET document.",
            },
        )

    study_id = content.get("protocol_number") or content.get("study_name") or "STUDY"
    study_name = content.get("study_name") or study_id
    ig_version = content.get("sdtm_ig_version", "3.3")
    derivation_index = _build_derivation_index(content)

    root = ET.Element(
        "ODM",
        attrib={
            "ODMVersion": "1.3.2",
            "FileType": "Snapshot",
            "FileOID": f"DEFINE.{study_id}",
            "CreationDateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )

    study_el = ET.SubElement(root, "Study", attrib={"OID": f"ST.{study_id}"})
    globals_el = ET.SubElement(study_el, "GlobalVariables")
    ET.SubElement(globals_el, "StudyName").text = str(study_name)
    ET.SubElement(globals_el, "StudyDescription").text = (
        f"SDTM IG {ig_version} dataset definitions"
    )
    ET.SubElement(globals_el, "ProtocolName").text = str(study_id)

    mdv = ET.SubElement(
        study_el,
        "MetaDataVersion",
        attrib={
            "OID": f"MDV.{study_id}",
            "Name": f"SDTM IG {ig_version}",
            f"{{{DEF_NS}}}DefineVersion": "2.1.0",
            f"{{{DEF_NS}}}StandardName": "SDTM-IG",
            f"{{{DEF_NS}}}StandardVersion": ig_version,
        },
    )

    used_codelists: set[str] = set()
    method_defs: dict[str, dict] = {}
    value_list_defs: list[dict] = []
    where_clause_defs: list[dict] = []
    item_defs: dict[str, dict] = {}

    for domain in content.get("domains", []):
        domain_code = domain.get("domain", "UNK")
        ig_oid = f"IG.{domain_code}"
        ig = ET.SubElement(
            mdv,
            "ItemGroupDef",
            attrib={
                "OID": ig_oid,
                "Name": domain_code,
                "Repeating": "No",
                "IsReferenceData": "No",
                "Purpose": "Tabulation",
                f"{{{DEF_NS}}}Structure": "One record per subject",
                f"{{{DEF_NS}}}Class": _normalize_class(domain.get("class", "General")),
                f"{{{DEF_NS}}}ArchiveLocationID": f"LF.{domain_code}",
            },
        )
        desc = ET.SubElement(ig, "Description")
        ET.SubElement(
            desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = domain.get("domain_label", domain_code)

        leaf = ET.SubElement(
            mdv,
            f"{{{DEF_NS}}}leaf",
            attrib={
                "ID": f"LF.{domain_code}",
                f"{{{XLINK_NS}}}href": f"{domain_code.lower()}.xpt",
            },
        )
        ET.SubElement(leaf, f"{{{DEF_NS}}}title").text = domain.get(
            "domain_label", domain_code
        )

        for order, var_spec in enumerate(_iter_variables(domain), start=1):
            var = _normalize_variable(var_spec, domain_code, derivation_index)
            item_oid = f"IT.{domain_code}.{var['name']}"
            item_defs[item_oid] = var

            item_ref_attrs: dict[str, str] = {
                "ItemOID": item_oid,
                "Mandatory": "Yes" if var["name"] in {"STUDYID", "USUBJID"} else "No",
                "OrderNumber": str(order),
            }
            if var["derivation"]:
                method_oid = f"MT.{domain_code}.{var['name']}"
                method_defs[method_oid] = {
                    "name": var["name"],
                    "derivation": var["derivation"],
                    "domain": domain_code,
                }
                item_ref_attrs["MethodOID"] = method_oid

            item_ref = ET.SubElement(ig, "ItemRef", attrib=item_ref_attrs)
            origin_type = var["origin"]
            origin_attrs: dict[str, str] = {"Type": origin_type}
            if var.get("origin_source"):
                origin_attrs["Source"] = var["origin_source"]
            ET.SubElement(item_ref, "Origin", attrib=origin_attrs)

            if var["codelist"]:
                used_codelists.add(var["codelist"])

            if var["value_level_metadata"]:
                vl_oid = f"VL.{domain_code}.{var['name']}"
                entries = [
                    {**entry, "domain": domain_code}
                    for entry in var["value_level_metadata"]
                ]
                value_list_defs.append(
                    {
                        "oid": vl_oid,
                        "name": var["name"],
                        "domain": domain_code,
                        "item_oid": item_oid,
                        "entries": entries,
                    }
                )
                ET.SubElement(
                    ig,
                    f"{{{DEF_NS}}}ValueListRef",
                    attrib={"ValueListOID": vl_oid},
                )

    for item_oid, var in item_defs.items():
        _, domain_code, var_name = item_oid.split(".", 2)
        item_attrs: dict[str, str] = {
            "OID": item_oid,
            "Name": var_name,
            "DataType": var["data_type"],
            "Length": var["length"],
        }
        if var["codelist"]:
            item_attrs[f"{{{DEF_NS}}}CodeListOID"] = var["codelist"]
        if var["description"]:
            item_attrs["Comment"] = var["description"]

        item_def = ET.SubElement(mdv, "ItemDef", attrib=item_attrs)
        item_desc = ET.SubElement(item_def, "Description")
        ET.SubElement(
            item_desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = var["label"]

    for cl_oid in sorted(used_codelists):
        cl_meta = next(
            (meta for meta in CDISC_CT_CODELISTS.values() if meta["oid"] == cl_oid),
            None,
        )
        if cl_meta is None:
            continue
        cl_name = cl_meta["name"]
        cl = ET.SubElement(
            mdv,
            "CodeList",
            attrib={
                "OID": cl_meta["oid"],
                "Name": cl_meta["name"],
                "DataType": cl_meta["data_type"],
                f"{{{DEF_NS}}}StandardOID": f"NCIT.{cl_meta['nci']}",
            },
        )
        cl_desc = ET.SubElement(cl, "Description")
        ET.SubElement(
            cl_desc,
            "TranslatedText",
            attrib={XML_LANG: "en"},
        ).text = f"CDISC CT codelist for {cl_name}"
        for coded_value, decode in cl_meta["items"]:
            cli = ET.SubElement(
                cl,
                "CodeListItem",
                attrib={"CodedValue": coded_value},
            )
            decode_el = ET.SubElement(cli, "Decode")
            ET.SubElement(
                decode_el,
                "TranslatedText",
                attrib={XML_LANG: "en"},
            ).text = decode

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

    for vl in value_list_defs:
        vl_def = ET.SubElement(
            mdv,
            f"{{{DEF_NS}}}ValueListDef",
            attrib={"OID": vl["oid"], "Name": vl["name"]},
        )
        for entry_order, entry in enumerate(vl["entries"], start=1):
            wc_oid = f"WC.{vl['domain']}.{vl['name']}.{entry_order}"
            where_clause_defs.append({"oid": wc_oid, "entry": entry})
            item_ref = ET.SubElement(
                vl_def,
                "ItemRef",
                attrib={
                    "ItemOID": vl["item_oid"],
                    "Mandatory": "No",
                    "OrderNumber": str(entry_order),
                },
            )
            ET.SubElement(
                item_ref,
                f"{{{DEF_NS}}}WhereClauseRef",
                attrib={"WhereClauseOID": wc_oid},
            )

    for wc in where_clause_defs:
        entry = wc["entry"]
        wc_def = ET.SubElement(
            mdv,
            f"{{{DEF_NS}}}WhereClauseDef",
            attrib={"OID": wc["oid"]},
        )
        where_clause = ET.SubElement(wc_def, f"{{{DEF_NS}}}WhereClause")
        range_check = ET.SubElement(
            where_clause,
            f"{{{DEF_NS}}}RangeCheck",
            attrib={
                "Comparator": "EQ",
                "SoftHard": "Soft",
            },
        )
        check_var = entry.get("where", {}).get("variable", "QSCAT")
        check_val = entry.get("where", {}).get("value", "")
        domain_for_wc = entry.get("domain") or wc["oid"].split(".")[1]
        ET.SubElement(
            range_check,
            f"{{{DEF_NS}}}CheckValue",
            attrib={"ItemOID": f"IT.{domain_for_wc}.{check_var}"},
        ).text = check_val

    meta = ET.SubElement(root, "MetaData")
    ET.SubElement(meta, "StudyID").text = str(study_id)
    ET.SubElement(meta, "DefineXMLVersion").text = "2.1"
    ET.SubElement(meta, "ValidationEngine").text = content.get(
        "validation_engine", "internal"
    )

    rough = ET.tostring(root, encoding="unicode")
    return minidom.parseString(rough).toprettyxml(indent="  ")


def _normalize_class(class_name: str) -> str:
    normalized = class_name.upper().replace("-", "").replace(" ", "")
    mapping = {
        "SPECIALPURPOSE": "SPECIAL PURPOSE",
        "GENERAL": "GENERAL",
        "FINDINGS": "FINDINGS",
        "EVENTS": "EVENTS",
        "INTERVENTIONS": "INTERVENTIONS",
        "TRIALDESIGN": "TRIAL DESIGN",
    }
    return mapping.get(normalized, class_name.upper())


def _build_derivation_index(content: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for entry in content.get("derived_variables", []):
        var_key = entry.get("variable", "")
        logic = entry.get("logic") or entry.get("derivation") or ""
        if var_key and logic:
            index[var_key] = logic
            if "." in var_key:
                _, short = var_key.split(".", 1)
                index[short] = logic
    return index


def _iter_variables(domain: dict):
    for var in domain.get("variables", []):
        yield var


def _normalize_variable(
    var_spec: str | dict,
    domain_code: str,
    derivation_index: dict[str, str],
) -> dict:
    if isinstance(var_spec, str):
        name = var_spec
        spec: dict = {}
    else:
        name = var_spec.get("variable") or var_spec.get("name") or "UNK"
        spec = var_spec

    derivation = spec.get("derivation") or derivation_index.get(f"{domain_code}.{name}")
    derivation = derivation or derivation_index.get(name) or ""
    description = spec.get("description") or spec.get("notes") or ""
    origin = spec.get("origin") or _infer_origin(name, derivation)
    controlled = spec.get("controlled_terminology")
    codelist = _resolve_codelist(name, controlled)
    vlm = spec.get("value_level_metadata") or []

    return {
        "name": name,
        "label": spec.get("label") or name,
        "data_type": _infer_data_type(name, spec, vlm),
        "length": str(spec.get("length") or _default_length(name)),
        "derivation": derivation.strip() if derivation else "",
        "description": description.strip() if description else "",
        "origin": origin,
        "origin_source": spec.get("origin_source") or _default_origin_source(origin),
        "codelist": codelist,
        "value_level_metadata": vlm,
    }


def _infer_origin(name: str, derivation: str) -> str:
    if derivation:
        return "Derived"
    if name in _ASSIGNED_VARIABLES:
        return "Assigned"
    return "Collected"


def _default_origin_source(origin: str) -> str | None:
    if origin == "Assigned":
        return "Sponsor"
    if origin == "Collected":
        return "Investigator"
    return None


def _resolve_codelist(name: str, controlled_terminology: str | None) -> str | None:
    if name in _CODELIST_VARIABLES:
        return CDISC_CT_CODELISTS[name]["oid"]
    if controlled_terminology:
        for var_name, meta in CDISC_CT_CODELISTS.items():
            if meta["nci"] in controlled_terminology:
                return meta["oid"]
    return None


def _infer_data_type(name: str, spec: dict, vlm: list) -> str:
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
    if vlm:
        first = vlm[0].get("data_type", "text")
        return first
    if name.endswith("DTC") or name.endswith("DT"):
        return "date"
    if name in {"AGE", "HEIGHT", "WEIGHT", "BMI"}:
        return "float"
    return "text"


def _default_length(name: str) -> int:
    if name in _CODELIST_VARIABLES:
        return 50
    if name in {"STUDYID", "USUBJID"}:
        return 40
    return 200
