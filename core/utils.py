import collections

from dsl import ir

import logging

_logger = logging.getLogger().getChild(__name__)

def cal_relative(idx, relative):
    if len(idx) != len(relative):
        raise Exception("Should always have same index length")
    result = []
    for i, j in zip(idx, relative):
        result.append(i-j)
    return tuple(result)

def find_relative_ref_position(stmt, relative_position):
    """Find references in all positions of the stmt

    :param stmt: the input stmt
    :param relative_position: relative position
    :return: all references in the stmt
    """

    if stmt is None:
        _logger.debug('No stmt input')
        return {}

    def find_in_a_place(node: ir.Node) -> dict:
        def visitor(node, args=None):
            ref_positions = {}

            if isinstance(node, ir.Ref):
                if node.name not in ref_positions.keys():
                    ref_positions[node.name] = set()
                ref_positions[node.name].add(cal_relative(node.idx, relative_position))
            elif node.operand:
                for operand in node.operand:
                    temp_positions = find_in_a_place(operand)
                    for name, positions in temp_positions.items():
                        if name not in ref_positions.keys():
                            ref_positions[name] = set()
                        for position in positions:
                            ref_positions[name].add(position)
            return ref_positions

        return node.visit(visitor)

    return find_in_a_place(stmt.expr)