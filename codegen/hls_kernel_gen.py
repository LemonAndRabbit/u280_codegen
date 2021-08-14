import logging

from codegen import utils
import core
from dsl import ir

_logger = logging.getLogger().getChild(__name__)

def kernel_gen(stencil, output_file):
    _logger.info('generate kernel code as %s', output_file.name)
    printer = utils.Printer(output_file)

    includes = ['<hls_stream.h>', '%s.h' % stencil.app_name]
    for include in includes:
        printer.println('#include %s' % include)

    printer.println()
    _print_force_movement(printer)
    printer.println()
    _print_stencil_kernel(stencil, printer)


def _print_force_movement(printer):
    println = printer.println
    println('template<class T>')
    println('T HLS_REG(T in){')
    println('#pragma HLS pipeline')
    println('#pragma HLS inline off')
    println('#pragma HLS interface port=return register')
    printer.do_indent()
    println('return in;')
    printer.un_indent()
    println('}')

def _print_stencil_kernel(stencil: core.Stencil, printer):
    all_refs = stencil.all_refs
    ports = []
    for name, postions in all_refs.items():
        for postion in postions:
            ports.append("float %s_%s" % (name, '_'.join(utils.idx2str(idx) for idx in postion)))

    printer.print_func('float %s' % stencil.app_name, ports)
    printer.do_scope('stencil kernel definition')

    def mutate_name(node: ir.Node, relative_idx: (int, )):
        if isinstance(node, ir.Ref):
            real_idx = utils.cal_relative(node.idx, relative_idx)
            node.name = node.name + '_'.join(utils.idx2str(x) for x in real_idx)
        return node

    output_stmt = stencil.output_stmt.visit(mutate_name, stencil.output_idx)

    printer.println('/*')
    printer.do_indent()
    printer.println(stencil.output_stmt.expr)
    printer.un_indent()
    printer.println('*/')

    printer.println('return')

    printer.do_indent()
    printer.println(output_stmt.expr.c_expr)
    printer.un_indent()

    printer.un_scope()








