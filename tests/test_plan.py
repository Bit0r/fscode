import pytest
import networkx as nx

from src.fscode.plan import GraphOperationGenerator


# 1. Core Fixture: Using the comprehensive example from __name__ == '__main__'
@pytest.fixture
def main_generator():
    """
    Provides a GraphOperationGenerator instance,
    based on the example in plan.py's if __name__ == '__main__' block.
    This example includes all cases:
    - Cycle: a-b-c-a
    - Cycle: f-g-f
    - Branch (cp): c-d, f-h, d-d1
    - Path (mv): d-e
    - Self-loop: i-i
    - Isolated: j
    - Create (with args): ''-x
    - Create (no args): ''-y
    """
    all_nodes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'x', 'y']
    edge_list = [
        ('a', 'b'),
        ('b', 'c'),
        ('c', 'a'),  # Cycle: a -> b -> c -> a
        ('c', 'd'),  # Branch
        ('d', 'd1'),  # Branch
        ('d', 'e'),  # Path
        ('f', 'g'),
        ('g', 'f'),  # Cycle: f -> g -> f
        ('f', 'h'),  # Branch
        ('i', 'i'),  # Self-loop
        ('', 'x', {'args': ['xxx']}),  # Create (with args)
        ('', 'y'),  # Create (no args)
        # 'j' is an isolated node
    ]
    return GraphOperationGenerator(all_nodes, edge_list)


# 2. Test graph validation logic
def test_init_validation_fails_in_degree_gt_one():
    """Test if a node with in-degree > 1 raises ValueError"""
    nodes = ['a', 'b', 'c']
    edges = [('a', 'c'), ('b', 'c')]  # Node 'c' has in-degree 2

    with pytest.raises(ValueError, match="Node 'c' has an in-degree of 2"):
        GraphOperationGenerator(nodes, edges)


def test_init_validation_fails_empty_node_has_in_degree():
    """Test if the '' node with in-degree > 0 raises ValueError"""
    nodes = ['a']
    edges = [('a', '')]  # Node '' has in-degree 1

    with pytest.raises(ValueError, match="Node '' has an in-degree of 1"):
        GraphOperationGenerator(nodes, edges)


def test_init_validation_success(main_generator):
    """Test if a valid graph can be instantiated successfully (main_generator runs init)"""
    assert main_generator is not None
    assert isinstance(main_generator.DG, nx.DiGraph)


# 3. Test node classification logic
def test_classify_nodes_creates(main_generator):
    """Test classification of "create" nodes"""
    # Check nodes
    assert set(main_generator.creates_nodes_subgraph.nodes) == {'', 'x', 'y'}
    # Check edges
    assert set(main_generator.creates_nodes_subgraph.successors('')) == {'x', 'y'}
    # Check 'args' for node 'x'
    assert main_generator.creates_nodes_subgraph['']['x'].get('args') == ['xxx']
    # Check that node 'y' has no 'args'
    assert not main_generator.creates_nodes_subgraph['']['y'].get('args')
    # Ensure these nodes are removed from the main graph
    assert '' not in main_generator.DG
    assert 'x' not in main_generator.DG
    assert 'y' not in main_generator.DG


def test_classify_nodes_isolated(main_generator):
    """Test classification of "isolated" nodes"""
    assert main_generator.isolated_nodes == {'j'}


def test_classify_nodes_self_loop(main_generator):
    """Test classification of "self-loop" nodes"""
    # Note: 'i' will also be in the main node list, but self-loop ops don't have a corresponding generator
    assert main_generator.self_loop_nodes == {'i'}


# May not pass CI, as topological sort is a partial order
def test_classify_nodes_cycles(main_generator):
    """Test classification of "cycle" nodes (based on sorted results)"""
    # The output order of networkx.simple_cycles can be non-deterministic, but sorted() in the code guarantees order
    assert main_generator.cycles == [['a', 'b', 'c'], ['f', 'g']]


def test_classify_nodes_normal_paths(main_generator):
    """Test classification of "normal path" nodes"""
    assert main_generator.normal_nodes_set == {'d', 'd1', 'e', 'h'}


# 4. Test operation generation (integration tests)
# May not pass CI, as topological sort is a partial order
def test_generate_operations_main_example_temp_var(main_generator):
    """
    Test the __main__ example (is_exchange=False, using a temp variable)
    """
    ops = main_generator.generate_operations(is_exchange=False, tmp_name='__mv_tmp')

    # The order of 'create' operations might be non-deterministic due to dict iteration, test them separately
    create_ops = [op for op in ops if op[0] in ('ln', 'touch')]
    other_ops = [op for op in ops if op[0] not in ('ln', 'touch')]

    expected_other_ops = [
        ['rm', 'j'],  # 1. Remove
        ['cp', 'd', 'e'],  # 2. Path (e <- d)
        ['cp', 'f', 'h'],  # 2. Path (h <- f, f has multiple out-edges -> cp)
        ['mv', 'd', 'd1'],
        ['cp', 'c', 'd'],  # 2. Path (d <- c, c has multiple out-edges -> cp)
        ['#', 'Start processing cycles'],  # 3. Cycles
        ['#', 'Processing cycle 1:', 'a', 'b', 'c'],
        ['mv', 'c', '__mv_tmp'],
        ['mv', 'b', 'c'],
        ['mv', 'a', 'b'],
        ['mv', '__mv_tmp', 'a'],
        ['#', 'Processing cycle 2:', 'f', 'g'],
        ['mv', 'g', '__mv_tmp'],
        ['mv', 'f', 'g'],
        ['mv', '__mv_tmp', 'f'],
        ['#', 'Total of 2 cycles'],
    ]

    assert other_ops == expected_other_ops

    expected_create_ops_set = {('ln', '-snT', 'xxx', 'x'), ('touch', 'y')}
    assert set(tuple(op) for op in create_ops) == expected_create_ops_set


# May not pass CI, as topological sort is a partial order
def test_generate_operations_main_example_exchange(main_generator):
    """
    Test the __main__ example (is_exchange=True, using exchange)
    """
    ops = main_generator.generate_operations(is_exchange=True)

    create_ops = [op for op in ops if op[0] in ('ln', 'touch')]
    other_ops = [op for op in ops if op[0] not in ('ln', 'touch')]

    expected_other_ops = [
        ['rm', 'j'],  # 1. Remove
        ['cp', 'd', 'e'],  # 2. Path
        ['mv', 'd', 'd1'],
        ['cp', 'f', 'h'],  # 2. Path (cp)
        ['cp', 'c', 'd'],  # 2. Path (cp)
        ['#', 'Start processing cycles'],  # 3. Cycles
        ['#', 'Processing cycle 1:', 'a', 'b', 'c'],
        ['mv', '--exchange', 'b', 'c'],  # Exchange (i=1)
        ['mv', '--exchange', 'a', 'b'],  # Exchange (i=0)
        ['#', 'Processing cycle 2:', 'f', 'g'],
        ['mv', '--exchange', 'f', 'g'],  # Exchange (i=0)
        ['#', 'Total of 2 cycles'],
    ]

    assert other_ops == expected_other_ops

    expected_create_ops_set = {('ln', '-snT', 'xxx', 'x'), ('touch', 'y')}
    assert set(tuple(op) for op in create_ops) == expected_create_ops_set


# 5. Test edge cases and specific logic
def test_generate_ops_empty_graph():
    """Test an empty graph"""
    gen = GraphOperationGenerator(nodes=[], edges=[])
    assert gen.generate_operations() == []


def test_generate_ops_only_removes():
    """Test with only isolated nodes"""
    gen = GraphOperationGenerator(nodes=['a', 'b', 'c'], edges=[])
    # Result should be sorted alphabetically
    assert gen.generate_operations() == [['rm', 'a'], ['rm', 'b'], ['rm', 'c']]


def test_generate_ops_only_creates():
    """Test with only create nodes"""
    nodes = ['z', 'a']
    edges = [('', 'a'), ('', 'z', {'args': ['-T']})]
    gen = GraphOperationGenerator(nodes, edges)
    ops = gen.generate_operations()

    # Order is non-deterministic, check using a set
    expected_ops_set = {('touch', 'a'), ('ln', '-snT', '-T', 'z')}
    assert set(tuple(op) for op in ops) == expected_ops_set


def test_generate_ops_only_simple_path():
    """Test a single simple path (a -> b -> c), should generate mv operations"""
    nodes = ['a', 'b', 'c']
    edges = [('a', 'b'), ('b', 'c')]
    gen = GraphOperationGenerator(nodes, edges)
    ops = gen.generate_operations()

    # Path operations are generated in reverse topological order
    # Topological sort: 'c', 'b', 'a'
    # 1. dest='c', src='b' -> ['mv', 'b', 'c']
    # 2. dest='b', src='a' -> ['mv', 'a', 'b']
    assert ops == [['mv', 'b', 'c'], ['mv', 'a', 'b']]


def test_generate_ops_path_with_copy():
    """Test a branching path (a -> b, a -> c), should generate one cp and one mv"""
    nodes = ['a', 'b', 'c']
    edges = [('a', 'b'), ('a', 'c')]
    gen = GraphOperationGenerator(nodes, edges)
    ops = gen.generate_operations()

    # Reverse topological sort could be ['b', 'c', 'a'] or ['c', 'b', 'a']
    # The result will be:
    # 1. cp ('a' -> 'b' or 'c')
    # 2. mv ('a' -> 'c' or 'b')

    assert len(ops) == 2

    # Check operation types
    op_types = sorted([op[0] for op in ops])
    assert op_types == ['cp', 'mv']

    # Check operation contents
    op_contents = sorted([op[1:] for op in ops])
    assert op_contents == [['a', 'b'], ['a', 'c']]


# May not pass CI, as topological sort is a partial order
def test_generate_ops_custom_commands():
    """Test if custom commands from __init__ are used correctly"""
    custom_cmds = {
        'remove': ('DELETE',),
        'copy': ('CLONE',),
        'move': ('RELOCATE',),
        'exchange': ('SWAP',),
        'create': ('MAKE',),
        'create_args': ('LINK', 'ARGS'),
    }

    nodes = ['a', 'b', 'c', 'd', 'e', 'f']
    edges = [
        ('a', 'b'),
        ('b', 'a'),  # Cycle
        ('', 'c', {'args': ['-f']}),  # Create (args)
        ('', 'd'),  # Create
        ('e', 'e'),  # Self-loop
        # 'f' is isolated
    ]
    gen = GraphOperationGenerator(nodes, edges, **custom_cmds)

    # 1. Test is_exchange=True
    ops_exchange = gen.generate_operations(is_exchange=True)
    ops_exchange_set = {tuple(op) for op in ops_exchange if op[0] != '#'}
    expected_exchange_set = {
        ('DELETE', 'f'),
        ('SWAP', 'a', 'b'),
        ('LINK', 'ARGS', '-f', 'c'),
        ('MAKE', 'd'),
    }
    assert ops_exchange_set == expected_exchange_set

    # 2. Test is_exchange=False
    ops_mv = gen.generate_operations(is_exchange=False, tmp_name='_t')
    ops_mv_set = {tuple(op) for op in ops_mv if op[0] != '#'}
    expected_mv_set = {
        ('DELETE', 'f'),
        ('RELOCATE', 'b', '_t'),
        ('RELOCATE', 'a', 'b'),
        ('RELOCATE', '_t', 'a'),
        ('LINK', 'ARGS', '-f', 'c'),
        ('MAKE', 'd'),
    }
    assert ops_mv_set == expected_mv_set
