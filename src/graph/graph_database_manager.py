from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.structure.graph import Graph
import time


class GraphDatabaseManager:
    def __init__(self, endpoint: str = 'ws://localhost:8182/gremlin', use_in_memory: bool = False):
        """
        Connect to Gremlin Server at the given WebSocket endpoint or use in-memory graph.
        """
        self.use_in_memory = use_in_memory
        
        if use_in_memory:
            # Use TinkerGraph for testing
            self.graph = Graph()
            self.g = traversal().withGraph(self.graph)
            self.connection = None
        else:
            try:
                print(f"Attempting to connect to Gremlin server at {endpoint}")
                # 'g' is the traversal source configured in the server
                self.connection = DriverRemoteConnection(endpoint, 'g')
                # Use the recommended way to create a remote traversal source
                self.g = traversal().with_remote(self.connection)
                self.graph = None
                
                # Test the connection with a simple query
                print("Testing connection...")
                test_result = self.g.V().limit(1).count().next()
                print(f"Connection successful! Test query returned: {test_result}")
                
            except Exception as e:
                print(f"Failed to connect to Gremlin server at {endpoint}: {e}")
                print(f"Error type: {type(e).__name__}")
                raise

    def getClient(self):
        """
        Returns the Gremlin traversal source for queries and mutations.
        """
        return self.g

    def close(self):
        """
        Close the connection to Gremlin Server.
        """
        if self.connection:
            self.connection.close()
    
    def clear_graph(self):
        """
        Clear all vertices and edges from the graph (useful for testing).
        """
        try:
            print("Clearing graph...")
            result = self.g.V().drop().iterate()
            print("Graph cleared successfully")
            return result
        except Exception as e:
            print(f"Error clearing graph: {e}")
            raise
            
    def test_connection(self):
        """
        Test the connection by running a simple query
        """
        try:
            count = self.g.V().count().next()
            print(f"Connection test successful. Current vertex count: {count}")
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False