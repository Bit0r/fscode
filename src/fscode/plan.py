import enum
from pathlib import Path

import networkx as nx
from more_itertools import collapse

# [TODO]: A more efficient method is to swap stages two and three, but writing the code by hand is error-prone,
# so it is not implemented for now.
# The specific method is as follows:
# 1. In stage two, build a reverse graph excluding isolated nodes and self-loop nodes,
#    and perform a topological sort on this graph using Kahn's algorithm.
#    1. If the algorithm completes successfully, a valid topological sort can be obtained directly,
#       indicating no cycles exist.
#    2. If the algorithm finds during execution that there are no longer any nodes with an in-degree of 0
#       in the in-degree list, then all remaining unprocessed nodes are in cycles.
# 2. In stage three, remove the previously processed nodes from the forward graph.
#    Then, traverse the remaining nodes using a DFS algorithm. Each connected component will be a cycle.
#    Because the in-degree of this graph is <= 1, there are no intersecting cycles.


class TokenType(enum.Enum):
    SRC = enum.auto()
    TGT = enum.auto()
    ARGS = enum.auto()


class GraphOperationGenerator:
    """
    Analyzes a special directed graph (all nodes have in-degree <= 1) and directly converts its structure
    into a list of instructions containing abstract 'remove', 'create', 'copy', 'move', and 'exchange' operations.

    Instantiate this class to initialize the graph structure, then call the `generate_operations`
    method to generate the instructions.
    """

    def __init__(
        self,
        nodes: list[str],
        edges: list[tuple[str, str]],
        *,
        remove: tuple[str, ...] = ('rm',),
        copy: tuple[str, ...] = ('cp',),
        move: tuple[str, ...] = ('mv',),
        exchange: tuple[str, ...] = ('mv', '--exchange'),
        create: tuple[str, ...] = ('touch',),
        create_args: tuple[str, ...] = ('ln', '-snT'),
    ):
        """
        Initializes the graph and performs basic validation.

        Args:
            nodes: A list of all nodes in the graph.
            edges: A list of all edges in the graph, as (u, v) tuples
                    representing an edge from u to v.
            remove: The command tuple for the remove operation.
            copy: The command tuple for the copy operation.
            move: The command tuple for the move operation.
            exchange: The command tuple for the exchange operation.
            create: The command tuple for the create operation.
            create_args: The command tuple for create operation with arguments.

        Raises:
            ValueError: If any node in the graph has an in-degree greater than 1,
                    or if the '' node has an in-degree.
        """
        self.remove_cmd = remove
        self.copy_cmd = copy
        self.move_cmd = move
        self.exchange_cmd = exchange
        self.create_cmd = create
        self.create_args_cmd = create_args

        self.DG = nx.DiGraph()
        self.DG.add_nodes_from(nodes)
        self.DG.add_node('')
        self.DG.add_edges_from(edges)

        self._validate_graph()
        self._classify_nodes()

    def _validate_graph(self):
        """Validates if the graph meets the requirement that all nodes have an in-degree <= 1."""
        for node, in_degree in self.DG.in_degree:
            if in_degree > 1:
                msg = f"Input graph does not meet requirements: Node '{node}' has an in-degree of {in_degree}, which exceeds the limit of 1."
                raise ValueError(msg)
        if self.DG.in_degree[''] > 0:
            msg = f"Input graph does not meet requirements: Node '' has an in-degree of {self.DG.in_degree['']}, which exceeds the limit of 0."
            raise ValueError(msg)

    def _classify_nodes(self):
        """Classifies nodes in the graph: created, isolated, self-loop, in-cycle, and normal path."""
        # Process the creation of nodes first,
        # and then delete this part from the graph
        # to prevent interference with subsequent processing.
        created_nodes = set(self.DG.successors('')) | {''}
        self.creates_nodes_subgraph = self.DG.subgraph(created_nodes).copy()
        self.DG.remove_nodes_from(created_nodes)

        self.isolated_nodes = set(nx.isolates(self.DG))
        self.self_loop_nodes = set(nx.nodes_with_selfloops(self.DG))

        classified_nodes = self.isolated_nodes | self.self_loop_nodes

        cycles_search_subgraph = self.DG.subgraph(
            set(self.DG.nodes()) - classified_nodes
        )
        self.cycles = sorted(nx.simple_cycles(cycles_search_subgraph))

        classified_nodes |= set(collapse(self.cycles))

        # After excluding all special nodes, we get the set of normal path nodes
        self.normal_nodes_set = set(self.DG.nodes()) - classified_nodes

    def _generate_remove_operations(self) -> list[list[str]]:
        """Generates operations for isolated nodes -> remove"""
        return [[*self.remove_cmd, node] for node in sorted(self.isolated_nodes)]

    def _generate_create_operations(self) -> list[list[str]]:
        """Generates operations for created nodes -> create"""
        operations = []
        for node in self.creates_nodes_subgraph['']:
            edge_data = self.creates_nodes_subgraph[''][node]
            if edge_data.get('args'):
                operation = [*self.create_args_cmd, *edge_data['args'], node]
            else:
                operation = [*self.create_cmd, node]
            operations.append(operation)
        return operations

    def _generate_path_operations(self) -> list[list[str]]:
        """Generates operations for normal path nodes -> move or copy"""
        operations = []
        normal_nodes_subgraph = self.DG.subgraph(self.normal_nodes_set)
        reversed_subgraph = normal_nodes_subgraph.reverse(copy=True)
        reverse_topological_sort = list(nx.topological_sort(reversed_subgraph))

        out_degrees = dict(self.DG.out_degree)

        for dest_node in reverse_topological_sort:
            predecessors = list(self.DG.predecessors(dest_node))
            if not predecessors:
                continue

            src_node = predecessors[0]

            if out_degrees.get(src_node, 0) > 1:
                operations.append([*self.copy_cmd, src_node, dest_node])
                out_degrees[src_node] -= 1
            else:
                operations.append([*self.move_cmd, src_node, dest_node])

        return operations

    def _generate_cycle_operations(
        self, is_exchange: bool, tmp_name: str
    ) -> list[list[str]]:
        """Generates operations for nodes in cycles -> move (using a temporary variable) or exchange"""
        if not self.cycles:
            return []

        operations = [['#', 'Start processing cycles']]
        for idx, cycle in enumerate(self.cycles, 1):
            operations.append(['#', f'Processing cycle {idx}:', *cycle])

            if is_exchange:
                # Use exchange operation, essentially a single-pass bubble sort
                for i in range(len(cycle) - 2, -1, -1):
                    operations.append([*self.exchange_cmd, cycle[i], cycle[i + 1]])
            else:
                # Use temporary node
                temp_node = str(Path(tmp_name).expanduser())
                operations.append([*self.move_cmd, cycle[-1], temp_node])
                for i in range(len(cycle) - 2, -1, -1):
                    operations.append([*self.move_cmd, cycle[i], cycle[i + 1]])
                operations.append([*self.move_cmd, temp_node, cycle[0]])

        operations.append(['#', f'Total of {len(self.cycles)} cycles'])
        return operations

    def generate_operations(
        self, *, is_exchange: bool = False, tmp_name: str = '__mv_tmp'
    ) -> list[list[str]]:
        """
        Generates the final list of all operation instructions.

        Args:
            is_exchange: Whether to use the exchange operation to handle cycles.
                    Defaults to False.
            tmp_name: The temporary name to use when not using the exchange
                    operation for cycles.

        Returns:
            A list containing all operation instructions.
        """
        return [
            *self._generate_remove_operations(),
            *self._generate_path_operations(),
            *self._generate_cycle_operations(is_exchange, tmp_name),
            *self._generate_create_operations(),
        ]


if __name__ == '__main__':
    all_nodes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'a1', 'b1', 'c1']
    edge_list = [
        ('a', 'b'),
        ('b', 'c'),
        ('c1', 'b1'),  # Cycle: c1 -> b1-> a1 -> c1
        ('b1', 'a1'),
        ('a1', 'c1'),
        ('c', 'a'),  # Cycle: a -> b -> c -> a
        ('c', 'd'),  # Branch
        ('d', 'd1'),  # Branch
        ('d', 'e'),  # Path
        ('f', 'g'),
        ('g', 'f'),  # Cycle: f -> g -> f
        ('f', 'h'),  # Branch
        ('i', 'i'),  # Self-loop (will be classified, but no operation generated)
        ('', 'x', {'args': ['xxx']}),  # Create
        ('', 'y'),  # Create
        # 'j' is an isolated node
    ]

    # --- Instantiate and generate operations ---
    op_generator = GraphOperationGenerator(all_nodes, edge_list)

    # 1. Process cycles using a temporary variable (is_exchange=False)
    print('=' * 40)
    print('Generated operations (using temporary variable):')
    print('=' * 40)
    final_ops_mv = op_generator.generate_operations(is_exchange=False)
    for op in final_ops_mv:
        print(op)

    # 2. Process cycles using exchange operation (is_exchange=True)
    print('\n' + '=' * 40)
    print('Generated operations (using exchange operation):')
    print('=' * 40)
    final_ops_exchange = op_generator.generate_operations(is_exchange=True)
    for op in final_ops_exchange:
        print(op)
