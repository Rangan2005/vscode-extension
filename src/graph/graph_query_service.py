# src/graph/graph_query_service.py
from typing import List, Optional, Dict, Any
from gremlin_python.process.traversal import P
from gremlin_python.process.graph_traversal import __
from src.interfaces import IGraphQueryService, ParsedCodeModel, GraphNodeData, GraphEdgeData
from src.graph.graph_database_manager import GraphDatabaseManager

class GraphQueryService(IGraphQueryService):
    def __init__(self, dbManager: GraphDatabaseManager):
        self.dbManager = dbManager
        self.g = dbManager.getClient()

    def ingestParsedCode(self, parsedCode: ParsedCodeModel):
        file_node = parsedCode.file
        file_id = file_node.id
        try:
            self.g.V().has('nodeId', file_id).drop().iterate()
        except Exception:
            pass
        self.g.add_v('File') \
            .property('nodeId', file_id) \
            .property('filePath', file_node.filePath) \
            .property('language', getattr(file_node, 'language', '')) \
            .iterate()
        for fn in parsedCode.functions:
            try:
                self.g.V().has('nodeId', fn.id).drop().iterate()
            except Exception:
                pass
            self.g.add_v('Function') \
                .property('nodeId', fn.id) \
                .property('name', fn.name) \
                .property('fileId', fn.fileId) \
                .property('startLine', fn.startLine) \
                .property('endLine', fn.endLine) \
                .iterate()
            self.g.V().has('nodeId', file_id).as_('f') \
                .V().has('nodeId', fn.id) \
                .add_e('CONTAINS').from_('f') \
                .iterate()
        for cls in parsedCode.classes:
            try:
                self.g.V().has('nodeId', cls.id).drop().iterate()
            except Exception:
                pass
            self.g.add_v('Class') \
                .property('nodeId', cls.id) \
                .property('name', cls.name) \
                .property('fileId', cls.fileId) \
                .property('startLine', cls.startLine) \
                .property('endLine', cls.endLine) \
                .iterate()
            self.g.V().has('nodeId', file_id).as_('f') \
                .V().has('nodeId', cls.id) \
                .add_e('CONTAINS').from_('f') \
                .iterate()

    def getAllNodes(self, nodeType: Optional[str] = None) -> List[GraphNodeData]:
        traversal = self.g.V()
        if nodeType:
            traversal = traversal.has_label(nodeType)
        results = traversal.value_map(True).to_list()
        nodes: List[GraphNodeData] = []
        for vm in results:
            # Flatten only string keys
            flat: Dict[Any, Any] = {}
            for k, v in vm.items():
                if not isinstance(k, str):
                    continue
                flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
            node_id = flat.get('nodeId', '')
            label = flat.get('label') or ''
            name = flat.get('name', '')
            filePath = flat.get('filePath', '')
            startLine = flat.get('startLine', 0) or 0
            endLine = flat.get('endLine', 0) or 0
            props = {
                k: val for k, val in flat.items()
                if isinstance(k, str) and k not in {'label','nodeId','name','filePath','startLine','endLine','fileId','language'}
            }
            nodes.append(GraphNodeData(
                id=str(node_id),
                type=str(label),
                name=str(name),
                filePath=str(filePath),
                startLine=int(startLine),
                endLine=int(endLine),
                properties=props
            ))
        return nodes

    def getConnectedNodes(self, nodeId: str, edgeType: Optional[str] = None) -> List[GraphNodeData]:
        traversal = self.g.V().has('nodeId', nodeId)
        if edgeType:
            traversal = traversal.both_e(edgeType).other_v()
        else:
            traversal = traversal.both()
        results = traversal.value_map(True).to_list()
        nodes: List[GraphNodeData] = []
        for vm in results:
            flat: Dict[Any, Any] = {}
            for k, v in vm.items():
                if not isinstance(k, str):
                    continue
                flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
            nid = flat.get('nodeId', '')
            label = flat.get('label') or ''
            name = flat.get('name', '')
            filePath = flat.get('filePath', '')
            startLine = flat.get('startLine', 0) or 0
            endLine = flat.get('endLine', 0) or 0
            props = {
                k: val for k, val in flat.items()
                if isinstance(k, str) and k not in {'label','nodeId','name','filePath','startLine','endLine','fileId','language'}
            }
            nodes.append(GraphNodeData(
                id=str(nid),
                type=str(label),
                name=str(name),
                filePath=str(filePath),
                startLine=int(startLine),
                endLine=int(endLine),
                properties=props
            ))
        return nodes

    def getCodeGraphSnapshot(self, filePath: str) -> Dict[str, Any]:
        try:
            vm_list = self.g.V().has('filePath', filePath).value_map('nodeId').to_list()
            if not vm_list:
                return {'nodes': [], 'edges': []}
            file_nodeId = vm_list[0].get('nodeId')[0]
        except Exception:
            return {'nodes': [], 'edges': []}
        nodes_raw = self.g.V().has('nodeId', file_nodeId).union(__.identity(), __.out('CONTAINS')).value_map(True).to_list()
        nodes: List[GraphNodeData] = []
        ids = set()
        for vm in nodes_raw:
            flat: Dict[Any, Any] = {}
            for k, v in vm.items():
                if not isinstance(k, str):
                    continue
                flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
            nid = flat.get('nodeId', '')
            ids.add(nid)
            label = flat.get('label') or ''
            name = flat.get('name', '')
            filePathProp = flat.get('filePath', '')
            startLine = flat.get('startLine', 0) or 0
            endLine = flat.get('endLine', 0) or 0
            props = {
                k: val for k, val in flat.items()
                if isinstance(k, str) and k not in {'label','nodeId','name','filePath','startLine','endLine','fileId','language'}
            }
            nodes.append(GraphNodeData(
                id=str(nid),
                type=str(label),
                name=str(name),
                filePath=str(filePathProp),
                startLine=int(startLine),
                endLine=int(endLine),
                properties=props
            ))
        edges_raw = self.g.E().has_label('CONTAINS') \
            .where(__.out_v().values('nodeId').is_(P.within(ids))) \
            .where(__.in_v().values('nodeId').is_(P.within(ids))) \
            .project('source','target','type') \
                .by(__.out_v().values('nodeId')) \
                .by(__.in_v().values('nodeId')) \
                .by(__.label()) \
            .to_list()
        edges: List[GraphEdgeData] = []
        for e in edges_raw:
            src = e.get('source')
            tgt = e.get('target')
            etype = e.get('type')
            edge_id = f"{src}->{tgt}"
            edges.append(GraphEdgeData(
                id=edge_id,
                sourceId=str(src),
                targetId=str(tgt),
                type=str(etype),
                properties={}
            ))
        return {'nodes': nodes, 'edges': edges}