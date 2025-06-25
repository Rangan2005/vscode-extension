import sys
import os

# Ensure project root is on PYTHONPATH so that `src` can be imported.
# Adjust the relative path if needed.
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.graph.graph_database_manager import GraphDatabaseManager
from src.graph.graph_query_service import GraphQueryService

# Import your real Pydantic models
from src.interfaces import ParsedCodeModel, FileNode, FunctionNode, ClassNode

def main():
    endpoint = os.getenv("GREMLIN_ENDPOINT", "ws://localhost:8182/gremlin")
    print(f"Connecting to Gremlin server at {endpoint} ...")
    try:
        dbManager = GraphDatabaseManager(endpoint=endpoint, use_in_memory=False)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return
    service = GraphQueryService(dbManager)

    # Clear existing data to start fresh
    try:
        print("Clearing existing graph data...")
        dbManager.clear_graph()
    except Exception as e:
        print(f"Warning: clear_graph failed: {e}")

    # Create instances of your Pydantic models with correct fields.
    # Adjust fields if your FileNode/FunctionNode/ClassNode differ.
    file_node = FileNode(
        id="file_real_1",
        filePath="/real/test1.py",
        language="python"
    )
    func_node = FunctionNode(
        id="func_real_1",
        name="real_function",
        fileId="file_real_1",
        startLine=5,
        endLine=15
    )
    class_node = ClassNode(
        id="class_real_1",
        name="RealClass",
        fileId="file_real_1",
        startLine=1,
        endLine=50
    )
    parsedCode = ParsedCodeModel(
        file=file_node,
        functions=[func_node],
        classes=[class_node]
    )

    # Test ingestParsedCode
    print("\n--- Testing ingestParsedCode ---")
    try:
        service.ingestParsedCode(parsedCode)
        print("ingestParsedCode succeeded.")
    except Exception as e:
        print(f"ingestParsedCode failed: {e}")
        dbManager.close()
        return

    # Test getAllNodes without filter
    print("\n--- Testing getAllNodes (no filter) ---")
    try:
        all_nodes = service.getAllNodes()
        for n in all_nodes:
            print(n)
    except Exception as e:
        print(f"getAllNodes failed: {e}")

    # Test getAllNodes with nodeType filter
    print("\n--- Testing getAllNodes(nodeType='Function') ---")
    try:
        funcs = service.getAllNodes(nodeType="Function")
        for n in funcs:
            print(n)
    except Exception as e:
        print(f"getAllNodes(nodeType) failed: {e}")

    # Test getConnectedNodes for the file node
    print(f"\n--- Testing getConnectedNodes(nodeId='{file_node.id}') ---")
    try:
        connected = service.getConnectedNodes(nodeId=file_node.id)
        for n in connected:
            print(n)
    except Exception as e:
        print(f"getConnectedNodes failed: {e}")

    # Test getCodeGraphSnapshot for the filePath
    print(f"\n--- Testing getCodeGraphSnapshot(filePath='{file_node.filePath}') ---")
    try:
        snapshot = service.getCodeGraphSnapshot(file_node.filePath)
        print("Nodes in snapshot:")
        for n in snapshot.get('nodes', []):
            print(n)
        print("Edges in snapshot:")
        for e in snapshot.get('edges', []):
            print(e)
    except Exception as e:
        print(f"getCodeGraphSnapshot failed: {e}")

    # Cleanup
    print("\nClearing graph and closing connection.")
    try:
        dbManager.clear_graph()
    except Exception:
        pass
    dbManager.close()
    print("Done.")

if __name__ == "__main__":
    main()