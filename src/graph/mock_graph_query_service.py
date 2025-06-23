# src/graph/mock_graph_query_service.py
from typing import List, Optional, Dict, Any
from src.interfaces import IGraphQueryService, ParsedCodeModel, GraphNodeData, GraphEdgeData, FileNode, FunctionNode, ClassNode

class MockGraphQueryService(IGraphQueryService):
    def __init__(self):
        # Pre-populate with some dummy data or leave empty
        self._nodes: Dict[str, GraphNodeData] = {}
        self._edges: List[GraphEdgeData] = []

    def ingestParsedCode(self, parsedCode: ParsedCodeModel):
        # Simulate ingestion by creating GraphNodeData entries
        file = parsedCode.file
        file_node = GraphNodeData(
            id=file.id, type='File', name=file.filePath.split('/')[-1],
            filePath=file.filePath, startLine=None, properties={'language': file.language}
        )
        self._nodes[file.id] = file_node
        for fn in parsedCode.functions:
            node = GraphNodeData(
                id=fn.id, type='Function', name=fn.name,
                filePath=parsedCode.file.filePath, startLine=fn.startLine, properties={}
            )
            self._nodes[fn.id] = node
            edge = GraphEdgeData(
                id=f"e_{file.id}_{fn.id}", sourceId=file.id, targetId=fn.id, type='CONTAINS', properties={}
            )
            self._edges.append(edge)
        for cls in parsedCode.classes:
            node = GraphNodeData(
                id=cls.id, type='Class', name=cls.name,
                filePath=parsedCode.file.filePath, startLine=cls.startLine, properties={}
            )
            self._nodes[cls.id] = node
            edge = GraphEdgeData(
                id=f"e_{file.id}_{cls.id}", sourceId=file.id, targetId=cls.id, type='CONTAINS', properties={}
            )
            self._edges.append(edge)

    def getAllNodes(self, nodeType: Optional[str] = None) -> List[GraphNodeData]:
        nodes = list(self._nodes.values())
        if nodeType:
            nodes = [n for n in nodes if n.type == nodeType]
        return nodes

    def getConnectedNodes(self, nodeId: str, edgeType: Optional[str] = None) -> List[GraphNodeData]:
        connected = []
        for e in self._edges:
            if edgeType and e.type != edgeType:
                continue
            if e.sourceId == nodeId and e.targetId in self._nodes:
                connected.append(self._nodes[e.targetId])
            elif e.targetId == nodeId and e.sourceId in self._nodes:
                connected.append(self._nodes[e.sourceId])
        return connected

    def getCodeGraphSnapshot(self, filePath: str) -> Dict[str, Any]:
        # Return all nodes with matching filePath, and edges among them
        nodes = [n for n in self._nodes.values() if n.filePath == filePath]
        ids = {n.id for n in nodes}
        edges = [e for e in self._edges if e.sourceId in ids and e.targetId in ids]
        return {'nodes': nodes, 'edges': edges}