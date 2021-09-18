import logging
from itertools import chain

from codegen import codegen_utils
from codegen import hls_kernel_codes
import core
from dsl import ir

_logger = logging.getLogger().getChild(__name__)


def kernel_gen(stencil, output_file, input_buffer_configs, output_buffer_config, position='uni'):
    _logger.info('generate kernel code as %s', output_file.name)
    printer = codegen_utils.Printer(output_file)

    if stencil.iterate > 1 and stencil.boarder_type == 'overlap':
        append = stencil.iterate - 1
    else:
        append = 0

    includes = ['<hls_stream.h>', '"%s.h"' % stencil.app_name]
    for include in includes:
        printer.println('#include %s' % include)

    printer.println()
    _print_force_movement(printer)

    printer.println()
    _print_stencil_kernel(stencil, printer)

    printer.println()
    _print_backbone(stencil, printer, input_buffer_configs, append)

    _print_stream_function(printer, output_buffer_config, position)

    printer.println()
    printer.println('extern "C"{')

    if position == 'uni':
        _print_interface(stencil, printer)
    else:
        _print_stream_interface(stencil, printer, position)
    printer.println('}')


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


def _print_stencil_kernel(stencil: core.Stencil, printer: codegen_utils.Printer):
    all_refs = stencil.all_refs
    ports = []
    for name, positions in all_refs.items():
        for position in positions:
            ports.append("float %s_%s" % (name, '_'.join(codegen_utils.idx2str(idx) for idx in position)))

    printer.print_func('float %s_stencil_kernel' % stencil.app_name, ports)
    printer.do_scope('stencil kernel definition')

    def mutate_name(node: ir.Node, relative_idx: (int,)):
        if isinstance(node, ir.Ref):
            real_idx = codegen_utils.cal_relative(node.idx, relative_idx)
            node.name = node.name + '_' + '_'.join(codegen_utils.idx2str(x) for x in real_idx)
        return node

    output_stmt = stencil.output_stmt.visit(mutate_name, stencil.output_idx)

    printer.println('/*')
    printer.do_indent()
    printer.println(stencil.output_stmt.expr)
    printer.un_indent()
    printer.println('*/')

    printer.println('return ' + output_stmt.expr.c_expr + ';')

    printer.un_scope()


def _print_backbone(stencil: core.Stencil, printer: codegen_utils.Printer, input_buffer_configs, append):
    input_names = stencil.input_vars
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('INTERFACE_WIDTH *%s' % input_var)

    input_def.append('INTERFACE_WIDTH *%s' % stencil.output_var)

    printer.print_func('static void %s' % stencil.app_name, input_def)
    printer.do_scope('stencil kernel definition')
    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_define_buffer(printer)
        printer.println()
        buffer_instance.print_poped_object_def(printer)
        printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_init_buffer(printer)
        printer.println()

    printer.println('MAJOR_LOOP:')
    with printer.for_('int i = 0',
                      'i < GRID_COLS/WIDTH_FACTOR*PART_ROWS + 2*%d*GRID_COLS/WIDTH_FACTOR' % append,
                      'i++'):
        printer.println('#pragma HLS pipeline II=1')
        printer.println()
        printer.println('COMPUTE_LOOP:')
        with printer.for_('int k = 0', 'k < PARA_FACTOR', 'k++'):
            all_refs = stencil.all_refs
            all_ports = []
            for name, positions in all_refs.items():
                ports = []
                for position in positions:
                    ports.append("%s_%s" % (name, '_'.join(codegen_utils.idx2str(idx) for idx in position)))
                    all_ports.append("%s_%s" % (name, '_'.join(codegen_utils.idx2str(idx) for idx in position)))
                printer.println('float ' + ', '.join(map(lambda x: x + '[PARA_FACTOR]', ports)) + ';')
                for port in ports:
                    printer.println('#pragma HLS array_partition variable=%s complete dim=0'
                                    % port)
                printer.println()

            printer.println()
            printer.println('unsigned int idx_k = k << 5;')
            printer.println()

            for name, positions in all_refs.items():
                buffer_instance = input_buffer_configs[name]
                for position in positions:
                    buffer_instance.print_data_retrieve_with_unroll(printer, position,
                                                                    "%s_%s" % (name, '_'.join(
                                                                        codegen_utils.idx2str(idx) for idx in
                                                                        position)))

            printer.println()
            printer.println('float result = %s_stencil_kernel(%s);'
                            % (stencil.app_name, ', '.join(map(lambda x: x + '[k]', all_ports))))
            printer.println('%s[i + %d*GRID_COLS/WIDTH_FACTOR].range(idx_k+31, idx_k) = *((uint32_t *)(&result));'
                            % (stencil.output_var, abs(min(input_buffer_configs[stencil.input_vars[-1]].refs_by_row.keys()))))

        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_data_movement(printer)
    printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_pop_out(printer)

    printer.println('return;')

    printer.un_scope()


def _print_interface(stencil: core.Stencil, printer: codegen_utils.Printer):
    interfaces = []
    for var in stencil.input_vars:
        interfaces.append(var)
    interfaces.append(stencil.output_var)
    printer.print_func('void unikernel', map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces))
    printer.do_scope()
    for interface in interfaces:
        printer.println('#pragma HLS INTERFACE m_axi port=%s offset=slave bundle=%s1'
                        % (interface, interface))

    printer.println()

    for interface in interfaces:
        printer.println('#pragma HLS INTERFACE s_axilite port=%s'
                        % (interface))
    printer.println('#pragma HLS INTERFACE s_axilite port=return')

    printer.println()
    printer.println()

    if stencil.iterate > 1:
        printer.println("int i;")
        with printer.for_('i=0', 'i<ITERATION/2', 'i++'):
            printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))
            printer.println('%s(%s, %s);' % (stencil.app_name, ', '.join(interfaces[1:]), interfaces[0]))
        if stencil.iterate % 2 != 0:
            printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))
    else:
        printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))

    printer.println('return;')
    printer.un_scope()


def _print_stream_interface(stencil: core.Stencil, printer: codegen_utils.Printer, position):
    interfaces = []
    for var in stencil.input_vars:
        interfaces.append(var)
    interfaces.append(stencil.output_var)

    if position == 'up' or position == 'down':
        printer.print_func('void %skernel' % position, chain(map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces)
                           , ['hls::stream<pkt> &stream_to', 'hls::stream<pkt> &stream_from']))
    else:
        printer.print_func('void %skernel' % position, chain(map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces)
                           , ['hls::stream<pkt> &stream_to_up', 'hls::stream<pkt> &stream_from_up',
                              'hls::stream<pkt> &stream_to_down', 'hls::stream<pkt> &stream_from_down']))

    printer.do_scope()
    for interface in interfaces:
        printer.println('#pragma HLS INTERFACE m_axi port=%s offset=slave bundle=%s1'
                        % (interface, interface))

    printer.println()

    for interface in interfaces:
        printer.println('#pragma HLS INTERFACE s_axilite port=%s'
                        % interface)
    printer.println('#pragma HLS INTERFACE s_axilite port=return')

    printer.println()
    printer.println()

    if stencil.iterate > 1:
        printer.println("int i;")
        with printer.for_('i=0', 'i<ITERATION/2', 'i++'):
            printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))

            if position == 'up' or position == 'down':
                printer.println('exchange_stream(%s, stream_to, stream_from);' % interfaces[-1])
            else:
                printer.println('exchange_stream(%s, stream_to_up, stream_from_up, stream_to_down, stream_from_down);'
                                % interfaces[-1])

            printer.println('%s(%s, %s);' % (stencil.app_name, ', '.join(interfaces[1:]), interfaces[0]))

            if position == 'up' or position == 'down':
                printer.println('exchange_stream(%s, stream_to, stream_from);' % interfaces[-2])
            else:
                printer.println('exchange_stream(%s, stream_to_up, stream_from_up, stream_to_down, stream_from_down);'
                                % interfaces[-2])

        if stencil.iterate % 2 != 0:
            printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))
    else:
        printer.println('%s(%s);' % (stencil.app_name, ', '.join(interfaces)))

    printer.println('return;')
    printer.un_scope()


def _print_stream_function(printer: codegen_utils.Printer, output_buffer_config, position):
    top_rows = abs(min(output_buffer_config.refs_by_row.keys()))
    bottom_rows = max(output_buffer_config.refs_by_row.keys())
    if position == 'up':
        printer.println(hls_kernel_codes.up_exchange
                        % (top_rows, top_rows-top_rows, bottom_rows, top_rows))
    elif position == 'mid':
        printer.println(hls_kernel_codes.mid_exchange
                        % (top_rows, bottom_rows, top_rows,
                           top_rows, top_rows-top_rows, bottom_rows, top_rows))
    elif position == 'down':
        printer.println(hls_kernel_codes.down_exchange
                        % (top_rows, bottom_rows, top_rows))
