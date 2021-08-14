import logging

from core import utils
from dsl import arithmatic

_logger = logging.getLogger().getChild(__name__)


class Stencil():

    def __init__(self, **kwargs):
        self.iterate = kwargs.pop('iterate')
        self.app_name = kwargs.pop('app_name')
        self.size = kwargs.pop('size')
        self.input_stmts = kwargs.pop('input_stmts')
        self.output_stmt = kwargs.pop('output_stmt')

        self.input_vars = []
        for stmt in self.input_stmts:
            self.input_vars.append(stmt.name)

        _logger.debug("Get all input vars: [%s]",
                      ', '.join(self.input_vars))

        self.output_var = self.output_stmt.ref.name

        _logger.debug("Get output var: [%s]", self.output_var)

        self.output_idx = self.output_stmt.ref.idx

        self.output_stmt.expr = arithmatic.simplify(self.output_stmt.expr)
        self.output_stmt.let = arithmatic.simplify(self.output_stmt.let)

        self.all_refs = utils.find_relative_ref_position(self.output_stmt, self.output_idx)

        _logger.debug("Get references: \n\t%s",
                      '\n\t'.join("%s:\t%s" % (name, ", ".join("(%d, %d)" % (i[0], i[1]) for i in pos)) for name, pos in self.all_refs.items()))

        pass