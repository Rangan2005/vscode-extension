# tests/test_graph_query_service_mock.py
import pytest
from uuid import uuid4
#import sys
#sys.path.insert(1, 'D:/VS-Code-Extension/vscode-extension/src/graph')
from src.graph.mock_graph_query_service import MockGraphQueryService
#sys.path.insert(1, 'D:/VS-Code-Extension/vscode-extension/src')
from src.interfaces import ParsedCodeModel, FileNode, FunctionNode, ClassNode

@pytest.fixture
def mock_service():
    return MockGraphQueryService()

@pytest.fixture
def mock_parsed_code():
    fid = f"f_{uuid4().hex}"
    file_node = FileNode(id=fid, filePath='/tmp/foo.py', language='python')
    funcs = [FunctionNode(id=f"fn_{uuid4().hex}", name='foo', fileId=fid, startLine=0, endLine=2)]
    classes = [ClassNode(id=f"cl_{uuid4().hex}", name='Bar', fileId=fid, startLine=3, endLine=5)]
    return ParsedCodeModel(file=file_node, functions=funcs, classes=classes)

def test_mock_ingest_and_queries(mock_service, mock_parsed_code):
    mock_service.ingestParsedCode(mock_parsed_code)
    all_nodes = mock_service.getAllNodes()
    assert any(n.id == mock_parsed_code.file.id and n.type == 'File' for n in all_nodes)
    funcs = mock_service.getAllNodes(nodeType='Function')
    assert len(funcs) == 1 and funcs[0].name == mock_parsed_code.functions[0].name
    connected = mock_service.getConnectedNodes(nodeId=mock_parsed_code.file.id, edgeType='CONTAINS')
    assert any(n.id == mock_parsed_code.functions[0].id for n in connected)
    snapshot = mock_service.getCodeGraphSnapshot(filePath=mock_parsed_code.file.filePath)
    ids = {n.id for n in snapshot['nodes']}
    assert mock_parsed_code.file.id in ids
    assert mock_parsed_code.functions[0].id in ids
    edge_pairs = {(e.sourceId, e.targetId) for e in snapshot['edges']}
    assert (mock_parsed_code.file.id, mock_parsed_code.functions[0].id) in edge_pairs