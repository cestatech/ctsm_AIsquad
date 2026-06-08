"""Unit tests for base generator context graph node and event mapping."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.artifact import ArtifactType
from app.models.graph import GraphNodeType
from app.services.generators.edc_generator import EDCGenerator
from app.services.generators.sap_generator import SAPGenerator


class TestBaseGeneratorGraphMapping:
    def test_sap_uses_artifact_node_and_sap_event(self):
        gen = SAPGenerator(MagicMock())
        assert gen._primary_graph_node_type() == GraphNodeType.ARTIFACT
        assert gen._graph_event_type() == "SAP_GENERATED"

    def test_edc_uses_ecr_form_node(self):
        gen = EDCGenerator(MagicMock())
        assert gen._primary_graph_node_type() == GraphNodeType.ECR_FORM

    def test_edc_skips_base_event(self):
        gen = EDCGenerator(MagicMock())
        assert gen._graph_event_type() is None

    def test_protocol_mapping_via_sap_generator_class_attrs(self):
        gen = SAPGenerator(MagicMock())
        original = gen.ARTIFACT_TYPE
        gen.ARTIFACT_TYPE = ArtifactType.PROTOCOL
        try:
            assert gen._primary_graph_node_type() == GraphNodeType.PROTOCOL
            assert gen._graph_event_type() == "PROTOCOL_GENERATED"
        finally:
            gen.ARTIFACT_TYPE = original
