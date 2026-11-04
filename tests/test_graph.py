import unittest

from app.agent_graph import create_agent_graph


class GraphTests(unittest.TestCase):
    def test_langgraph_workflow_compiles(self):
        graph = create_agent_graph()
        self.assertTrue(callable(getattr(graph, "invoke", None)))


if __name__ == "__main__":
    unittest.main()
