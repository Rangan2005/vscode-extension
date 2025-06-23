# tests/test_graph_query_service.py
import pytest
import socket
import time
from pathlib import Path
import uuid
from src.graph.graph_database_manager import GraphDatabaseManager
from src.graph.graph_query_service import GraphQueryService
from src.interfaces import ParsedCodeModel, FileNode, FunctionNode, ClassNode

def is_gremlin_server_running(host='localhost', port=8182):
    """Check if Gremlin server is running"""
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def wait_for_gremlin_server(host='localhost', port=8182, timeout=30):
    """Wait for Gremlin server to be ready"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_gremlin_server_running(host, port):
            # Additional wait to ensure server is fully ready
            time.sleep(2)
            return True
        time.sleep(1)
    return False

@pytest.fixture(scope='module')
def gremlin_server():
    print("Checking for Gremlin server...")
    if not wait_for_gremlin_server():
        pytest.skip("Gremlin server is not running on localhost:8182")
    print("Gremlin server is running!")
    return True

@pytest.fixture
def db_manager(gremlin_server):
    print("Creating database manager...")
    mgr = GraphDatabaseManager('ws://localhost:8182/gremlin')
    
    # Test the connection
    if not mgr.test_connection():
        pytest.fail("Failed to establish connection to Gremlin server")
    
    # Clear the graph before each test
    try:
        print("Clearing graph before test...")
        mgr.clear_graph()
        print("Graph cleared successfully")
    except Exception as e:
        print(f"Warning: Could not clear graph: {e}")
    
    yield mgr
    
    # Cleanup
    try:
        mgr.close()
    except Exception as e:
        print(f"Warning: Error closing connection: {e}")

@pytest.fixture
def graph_service(db_manager):
    return GraphQueryService(db_manager)

@pytest.fixture
def mock_parsed_code():
    mock_file_id = f"f_{uuid.uuid4().hex}"
    file_node = FileNode(id=mock_file_id, filePath='/tmp/my_module.py', language='python')
    funcs = [
        FunctionNode(id=f"fn_{uuid.uuid4().hex}", name='funcA', fileId=mock_file_id, startLine=1, endLine=3),
        FunctionNode(id=f"fn_{uuid.uuid4().hex}", name='funcB', fileId=mock_file_id, startLine=5, endLine=8),
    ]
    classes = [
        ClassNode(id=f"cl_{uuid.uuid4().hex}", name='MyClass', fileId=mock_file_id, startLine=10, endLine=20)
    ]
    return ParsedCodeModel(file=file_node, functions=funcs, classes=classes)

def test_ingest_and_counts(graph_service, mock_parsed_code, db_manager):
    print("Starting test_ingest_and_counts...")
    
    try:
        # Ingest parsed code
        print("Ingesting parsed code...")
        graph_service.ingestParsedCode(mock_parsed_code)
        print("Ingestion completed")
        
        # Verify counts: 1 file + 2 functions + 1 class = 4 vertices
        print("Checking vertex count...")
        total_nodes = db_manager.getClient().V().count().next()
        print(f"Total nodes found: {total_nodes}")
        assert total_nodes == 4, f"Expected 4 nodes, got {total_nodes}"
        
        # Verify edges: CONTAINS edges count = 3
        print("Checking edge count...")
        total_edges = db_manager.getClient().E().has_label('CONTAINS').count().next()
        print(f"Total CONTAINS edges found: {total_edges}")
        assert total_edges == 3, f"Expected 3 CONTAINS edges, got {total_edges}"

        # Verify function names
        print("Checking function names...")
        fn_names = set(db_manager.getClient().V().has_label('Function').values('name').to_list())
        print(f"Function names found: {fn_names}")
        assert fn_names == {'funcA', 'funcB'}, f"Expected {{'funcA', 'funcB'}}, got {fn_names}"

        # Verify class name
        print("Checking class name...")
        class_names = set(db_manager.getClient().V().has_label('Class').values('name').to_list())
        print(f"Class names found: {class_names}")
        assert class_names == {'MyClass'}, f"Expected {{'MyClass'}}, got {class_names}"
        
        print("test_ingest_and_counts completed successfully!")
        
    except Exception as e:
        print(f"Error in test_ingest_and_counts: {e}")
        print(f"Error type: {type(e).__name__}")
        # Print current graph state for debugging
        try:
            all_vertices = db_manager.getClient().V().valueMap().to_list()
            print(f"Current vertices: {all_vertices}")
            all_edges = db_manager.getClient().E().valueMap().to_list()
            print(f"Current edges: {all_edges}")
        except:
            print("Could not retrieve graph state for debugging")
        raise

def test_getAllNodes(graph_service, mock_parsed_code, db_manager):
    print("Starting test_getAllNodes...")
    
    try:
        # First ingest
        print("Ingesting parsed code...")
        graph_service.ingestParsedCode(mock_parsed_code)
        
        # Retrieve all Function nodes via service
        print("Retrieving all Function nodes...")
        funcs = graph_service.getAllNodes(nodeType='Function')
        print(f"Retrieved {len(funcs)} functions")
        
        names = {f.name for f in funcs}
        expected = {fn.name for fn in mock_parsed_code.functions}
        print(f"Function names found: {names}")
        print(f"Expected function names: {expected}")
        
        assert names == expected, f"Expected {expected}, got {names}"
        print("test_getAllNodes completed successfully!")
        
    except Exception as e:
        print(f"Error in test_getAllNodes: {e}")
        raise

def test_getConnectedNodes(graph_service, mock_parsed_code, db_manager):
    print("Starting test_getConnectedNodes...")
    
    try:
        graph_service.ingestParsedCode(mock_parsed_code)
        file_id = mock_parsed_code.file.id
        print(f"Looking for nodes connected to file: {file_id}")
        
        connected = graph_service.getConnectedNodes(nodeId=file_id, edgeType='CONTAINS')
        print(f"Found {len(connected)} connected nodes")
        
        connected_ids = {n.id for n in connected}
        expected_ids = {fn.id for fn in mock_parsed_code.functions} | {cls.id for cls in mock_parsed_code.classes}
        
        print(f"Connected node IDs: {connected_ids}")
        print(f"Expected node IDs: {expected_ids}")
        
        assert connected_ids == expected_ids, f"Expected {expected_ids}, got {connected_ids}"
        print("test_getConnectedNodes completed successfully!")
        
    except Exception as e:
        print(f"Error in test_getConnectedNodes: {e}")
        raise

def test_getCodeGraphSnapshot(graph_service, mock_parsed_code, db_manager):
    print("Starting test_getCodeGraphSnapshot...")
    
    try:
        graph_service.ingestParsedCode(mock_parsed_code)
        snapshot = graph_service.getCodeGraphSnapshot(filePath=mock_parsed_code.file.filePath)
        print(f"Snapshot contains {len(snapshot['nodes'])} nodes and {len(snapshot['edges'])} edges")
        
        # Expect nodes list contains the file and its children
        ids = {n.id for n in snapshot['nodes']}
        print(f"Node IDs in snapshot: {ids}")
        
        assert mock_parsed_code.file.id in ids, f"File ID {mock_parsed_code.file.id} not in snapshot"
        for fn in mock_parsed_code.functions:
            assert fn.id in ids, f"Function ID {fn.id} not in snapshot"
        for cls in mock_parsed_code.classes:
            assert cls.id in ids, f"Class ID {cls.id} not in snapshot"
            
        # Expect edges list includes CONTAINS edges
        edge_tuples = {(e.sourceId, e.targetId) for e in snapshot['edges']}
        print(f"Edge tuples in snapshot: {edge_tuples}")
        
        for fn in mock_parsed_code.functions:
            expected_edge = (mock_parsed_code.file.id, fn.id)
            assert expected_edge in edge_tuples, f"Expected edge {expected_edge} not in snapshot"
        for cls in mock_parsed_code.classes:
            expected_edge = (mock_parsed_code.file.id, cls.id)
            assert expected_edge in edge_tuples, f"Expected edge {expected_edge} not in snapshot"
            
        print("test_getCodeGraphSnapshot completed successfully!")
        
    except Exception as e:
        print(f"Error in test_getCodeGraphSnapshot: {e}")
        raise