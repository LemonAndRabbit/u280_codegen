import copy
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

    includes = ['<hls_stream.h>', '"math.h"', '"%s.h"' % stencil.app_name]
    for include in includes:
        printer.println('#include %s' % include)

    printer.println()
    _print_force_movement(printer)

    printer.println()
    _print_stencil_kernel(stencil, printer)

    printer.println()
    if stencil.repeat_count == 1:
        _print_backbone(stencil, printer, input_buffer_configs)
    elif stencil.repeat_count == 2:
        _print_stage_in(stencil, printer, input_buffer_configs)
        _print_stage_out(stencil, printer, input_buffer_configs, 1)
        _print_multistage_backbone(stencil, printer)
    else:
        _print_stage_in(stencil, printer, input_buffer_configs)
        for i in range(1, stencil.repeat_count-1):
            _print_stage_mid(stencil, printer, input_buffer_configs, i)
        _print_stage_out(stencil, printer, input_buffer_configs, stencil.repeat_count-1)
        _print_multistage_backbone(stencil, printer)


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
    for scalar in stencil.scalar_vars:
        ports.append('float %s' % scalar)

    printer.print_func('static float %s_stencil_kernel' % stencil.app_name, ports)
    printer.do_scope('stencil kernel definition')

    def mutate_name(node: ir.Node, relative_idx: (int,)):
        if isinstance(node, ir.Ref):
            real_idx = codegen_utils.cal_relative(node.idx, relative_idx)
            node.name = node.name + '_' + '_'.join(codegen_utils.idx2str(x) for x in real_idx)
        return node

    output_stmt = stencil.output_stmt.visit(mutate_name, stencil.output_idx)

    local_stmts = []
    for i in range(0, len(stencil.local_stmts)):
        local_stmts.append(stencil.local_stmts[i].visit(mutate_name, (0,)*len(stencil.output_idx)))

    printer.println('/*')
    printer.do_indent()
    printer.println(stencil.output_stmt.expr)
    printer.un_indent()
    printer.println('*/')

    for local_stmt in local_stmts:
        printer.println(local_stmt.let.c_expr)
    printer.println('return ' + output_stmt.expr.c_expr + ';')

    printer.un_scope()

# TODO: add skip parameter to 1-stage backbone
def _print_backbone(stencil: core.Stencil, printer: codegen_utils.Printer, input_buffer_configs):
    input_names = stencil.input_vars
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('INTERFACE_WIDTH *%s' % input_var)

    input_def.append('INTERFACE_WIDTH *%s' % stencil.output_var)
    for scalar in stencil.scalar_vars:
        input_def.append('float %s' % scalar)

    printer.print_func('static void %s' % stencil.app_name, input_def)
    printer.do_scope('stencil kernel definition')
    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_define_buffer(printer)
        printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_init_buffer(printer)
        printer.println()

    printer.println('MAJOR_LOOP:')
    with printer.for_('int i = 0',
                      'i < GRID_COLS/WIDTH_FACTOR*PART_ROWS + (OVERLAP_TOP_OVERHEAD+OVERLAP_BOTTOM_OVERHEAD)',
                      'i++'):
        printer.println('#pragma HLS pipeline II=1')
        printer.println()
        printer.println('COMPUTE_LOOP:')
        with printer.for_('int k = 0', 'k < PARA_FACTOR', 'k++'):
            printer.println('#pragma HLS unroll')

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
            input_for_kernel = []
            for port in ports:
                input_for_kernel.append(port + '[k]')
            for scalar in stencil.scalar_vars:
                input_for_kernel.append(scalar)
            printer.println('float result = %s_stencil_kernel(%s);'
                            % (stencil.app_name, ', '.join(input_for_kernel)))
            printer.println('%s[i + TOP_APPEND + OVERLAP_TOP_OVERHEAD].range(idx_k+31, idx_k) = *((uint32_t *)(&result));'
                            % stencil.output_var)

        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_data_movement(printer)
    printer.println()


    if stencil.iterate > 1:
        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_pop_out(printer)


    printer.println('return;')

    printer.un_scope()

def _print_multistage_backbone(stencil: core.Stencil, printer: codegen_utils.Printer):
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('INTERFACE_WIDTH *%s' % input_var)

    input_def.append('INTERFACE_WIDTH *%s' % stencil.output_var)
    for scalar in stencil.scalar_vars:
        input_def.append('float %s' % scalar)

    input_def.append('int finished')

    printer.print_func('static void %s' % stencil.app_name, input_def)
    printer.do_scope('multi-stage backbone definition')
    printer.println('#pragma HLS dataflow')

    mid_instance_count = stencil.repeat_count - 1
    printer.println('static hls::stream<INTERFACE_WIDTH> '
                    + ', '.join('temp_out_%d' % i for i in range(mid_instance_count))
                    + ';')


    parameter = codegen_utils.get_parameter_printed(stencil.input_vars, 'temp_out_0', stencil.scalar_vars)
    printer.println('stage_in(%s, finished>=ITERATION);' % parameter)
    for i in range(1, stencil.repeat_count - 1):
        parameter = codegen_utils.get_parameter_printed(['temp_out_%d' % (i-1),], 'temp_out_%d' % i, stencil.scalar_vars)
        printer.println('stage_mid_%d(%s, finished+%s>=ITERATION);' % (i, parameter, i))
    parameter = codegen_utils.get_parameter_printed(['temp_out_%d' % (stencil.repeat_count-2),], stencil.output_var, stencil.scalar_vars)
    printer.println('stage_out(%s, finished+STAGE_COUNT>ITERATION);' % parameter)

    printer.println('return;')

    printer.un_scope()

def _print_stage_in(stencil: core.Stencil, printer: codegen_utils.Printer, input_buffer_configs):
    input_names = stencil.input_vars
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('INTERFACE_WIDTH *%s' % input_var)

    input_def.append('hls::stream<INTERFACE_WIDTH> &%s' % stencil.output_var)
    for scalar in stencil.scalar_vars:
        input_def.append('float %s' % scalar)

    input_def.append('bool skip')

    printer.print_func('static void stage_in', input_def)
    printer.do_scope('stencil kernel definition')
    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_define_buffer(printer)
        printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_init_buffer(printer)
        printer.println()

    printer.println('INTERFACE_WIDTH temp_out;')

    printer.println('MAJOR_LOOP:')
    with printer.for_('int i = 0',
                      'i < GRID_COLS/WIDTH_FACTOR*PART_ROWS + (OVERLAP_TOP_OVERHEAD+OVERLAP_BOTTOM_OVERHEAD) '
                        '+ (TOP_APPEND+BOTTOM_APPEND)*(STAGE_COUNT-1)',
                      'i++'):
        printer.println('#pragma HLS pipeline II=1')
        printer.println()
        printer.println('COMPUTE_LOOP:')
        with printer.for_('int k = 0', 'k < PARA_FACTOR', 'k++'):
            printer.println('#pragma HLS unroll')

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
            input_for_kernel = []
            for port in ports:
                input_for_kernel.append(port + '[k]')
            for scalar in stencil.scalar_vars:
                input_for_kernel.append(scalar)

            # TODO: no guarantee that %s_0_0[k] is retrieved
            printer.println('float result = skip?%s_0_0[k]:%s_stencil_kernel(%s);'
                            % (stencil.output_var, stencil.app_name, ', '.join(input_for_kernel)))
            printer.println('temp_out.range(idx_k+31, idx_k) = *((uint32_t *)(&result));')

        printer.println('%s << temp_out;' % stencil.output_var)

        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_data_movement(printer)
    printer.println()


    if stencil.iterate > 1:
        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_pop_out(printer)


    printer.println('return;')

    printer.un_scope()

def _print_stage_mid(stencil: core.Stencil, printer: codegen_utils.Printer, input_buffer_configs, decrement: int):
    input_names = stencil.input_vars
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('hls::stream<INTERFACE_WIDTH> &%s' % input_var)

    input_def.append('hls::stream<INTERFACE_WIDTH> &%s' % stencil.output_var)
    for scalar in stencil.scalar_vars:
        input_def.append('float %s' % scalar)

    input_def.append('bool skip')

    printer.print_func('static void stage_mid_%d' % decrement, input_def)
    printer.do_scope('stencil kernel definition')
    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_define_buffer(printer)
        printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_init_buffer_from_stream(printer)
        printer.println()

    printer.println('INTERFACE_WIDTH temp_out;')

    printer.println('MAJOR_LOOP:')
    with printer.for_('int i = 0',
                      'i < GRID_COLS/WIDTH_FACTOR*PART_ROWS + (OVERLAP_TOP_OVERHEAD+OVERLAP_BOTTOM_OVERHEAD) '
                        '+ (TOP_APPEND+BOTTOM_APPEND)*(STAGE_COUNT-1) '
                        '- (DECRE_TOP_APPEND+DECRE_BOTTOM_APPEND)*%d' % decrement,
                      'i++'):
        printer.println('#pragma HLS pipeline II=1')
        printer.println()
        printer.println('COMPUTE_LOOP:')
        with printer.for_('int k = 0', 'k < PARA_FACTOR', 'k++'):
            printer.println('#pragma HLS unroll')

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
            input_for_kernel = []
            for port in ports:
                input_for_kernel.append(port + '[k]')
            for scalar in stencil.scalar_vars:
                input_for_kernel.append(scalar)
            printer.println('float result = skip?%s_0_0[k]:%s_stencil_kernel(%s);'
                            % (stencil.output_var, stencil.app_name, ', '.join(input_for_kernel)))
            printer.println('temp_out.range(idx_k+31, idx_k) = *((uint32_t *)(&result));')

        printer.println('%s << temp_out;' % stencil.output_var)

        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_data_movement_from_stream(printer)
    printer.println()


    if stencil.iterate > 1:
        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_pop_out(printer)


    printer.println('return;')

    printer.un_scope()


def _print_stage_out(stencil: core.Stencil, printer: codegen_utils.Printer, input_buffer_configs, decrement: int):
    input_names = stencil.input_vars
    input_def = []
    for input_var in stencil.input_vars:
        input_def.append('hls::stream<INTERFACE_WIDTH> &%s' % input_var)

    input_def.append('INTERFACE_WIDTH* %s' % stencil.output_var)
    for scalar in stencil.scalar_vars:
        input_def.append('float %s' % scalar)

    input_def.append('bool skip')

    printer.print_func('static void stage_out', input_def)
    printer.do_scope('stencil kernel definition')
    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_define_buffer(printer)
        printer.println()

    for buffer_instance in input_buffer_configs.values():
        buffer_instance.print_init_buffer_from_stream(printer)
        printer.println()

    printer.println('MAJOR_LOOP:')
    with printer.for_('int i = 0',
                      'i < GRID_COLS/WIDTH_FACTOR*PART_ROWS + (OVERLAP_TOP_OVERHEAD+OVERLAP_BOTTOM_OVERHEAD) '
                        '+ (TOP_APPEND+BOTTOM_APPEND)*(STAGE_COUNT-1) '
                        '- (DECRE_TOP_APPEND+DECRE_BOTTOM_APPEND)*%d' % decrement,
                      'i++'):
        printer.println('#pragma HLS pipeline II=1')
        printer.println()
        printer.println('COMPUTE_LOOP:')
        with printer.for_('int k = 0', 'k < PARA_FACTOR', 'k++'):
            printer.println('#pragma HLS unroll')

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
            input_for_kernel = []
            for port in ports:
                input_for_kernel.append(port + '[k]')
            for scalar in stencil.scalar_vars:
                input_for_kernel.append(scalar)
            printer.println('float result = skip?%s_0_0[k]:%s_stencil_kernel(%s);'
                            % (stencil.output_var, stencil.app_name, ', '.join(input_for_kernel)))
            printer.println('%s[i + TOP_APPEND*STAGE_COUNT + OVERLAP_TOP_OVERHEAD].range(idx_k+31, idx_k) = *((uint32_t *)(&result));'
                            % stencil.output_var)

        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_data_movement_from_stream(printer)
    printer.println()


    if stencil.iterate > 1:
        for buffer_instance in input_buffer_configs.values():
            buffer_instance.print_pop_out(printer)


    printer.println('return;')

    printer.un_scope()


def _print_interface(stencil: core.Stencil, printer: codegen_utils.Printer):
    interfaces = []
    for var in stencil.input_vars:
        interfaces.append(var)
    interfaces.append(stencil.output_var)
    printer.print_func('void unikernel', chain(map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces)
                                               , map(lambda x: 'float %s' % x, stencil.scalar_vars)
                                               ))
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

    printer.println('#pragma HLS allocation function instances=%s limit=1' % stencil.app_name)

    printer.println()

    parameters = copy.copy(interfaces)
    parameters.extend(stencil.scalar_vars)
    parameters2 = copy.copy(interfaces)

    temp = parameters2[-2]
    parameters2[-2] = parameters2[-1]
    parameters2[-1] = temp
    parameters2.extend(stencil.scalar_vars)

    if stencil.iterate/stencil.repeat_count > 1:
        printer.println("int i;")
        with printer.for_('i=0', 'i<ITERATION', 'i+=STAGE_COUNT'):
            printer.println('if(i%(2*STAGE_COUNT)==0)')
            printer.println('   %s(%s, i);' % (stencil.app_name, ', '.join(parameters)))
            printer.println('else')
            printer.println('   %s(%s, i);' % (stencil.app_name, ', '.join(parameters2)))
    else:
        printer.println('%s(%s, 0);' % (stencil.app_name, ', '.join(parameters)))

    printer.println('return;')
    printer.un_scope()


def _print_stream_interface(stencil: core.Stencil, printer: codegen_utils.Printer, position):
    interfaces = []
    for var in stencil.input_vars:
        interfaces.append(var)
    interfaces.append(stencil.output_var)

    if position == 'up' or position == 'down':
        printer.print_func('void %skernel' % position, chain(map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces)
                            , map(lambda x: 'float %s' % x, stencil.scalar_vars)
                            , ['hls::stream<pkt> &stream_to', 'hls::stream<pkt> &stream_from']))
    else:
        printer.print_func('void %skernel' % position, chain(map(lambda x: 'INTERFACE_WIDTH *%s' % x, interfaces)
                            , map(lambda x: 'float %s' % x, stencil.scalar_vars)
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

    printer.println('#pragma HLS allocation function instances=%s limit=1' % stencil.app_name)

    printer.println()

    parameters = copy.copy(interfaces)
    parameters.extend(stencil.scalar_vars)

    parameters2 = copy.copy(interfaces)
    temp = parameters2[-2]
    parameters2[-2] = parameters2[-1]
    parameters2[-1] = temp
    parameters2.extend(stencil.scalar_vars)

    if stencil.iterate/stencil.repeat_count > 1:
        printer.println("int i;")
        with printer.for_('i=0', 'i<ITERATION', 'i+=STAGE_COUNT*2'):
            printer.println('if(i%(2*STAGE_COUNT)==0)')
            printer.println('\t%s(%s, i);' % (stencil.app_name, ', '.join(parameters)))

            if position == 'up' or position == 'down':
                printer.println('\texchange_stream(%s, stream_to, stream_from);' % interfaces[-1])
            else:
                printer.println('\texchange_stream(%s, stream_to_up, stream_from_up, stream_to_down, stream_from_down);'
                                % interfaces[-1])
            printer.println('else')
            printer.println('\t%s(%s, i);' % (stencil.app_name, ', '.join(parameters2)))

            if position == 'up' or position == 'down':
                printer.println('\texchange_stream(%s, stream_to, stream_from);' % interfaces[-2])
            else:
                printer.println('\texchange_stream(%s, stream_to_up, stream_from_up, stream_to_down, stream_from_down);'
                                % interfaces[-2])

    else:
        printer.println('%s(%s, 0);' % (stencil.app_name, ', '.join(parameters)))

    printer.println('return;')
    printer.un_scope()


def _print_stream_function(printer: codegen_utils.Printer, output_buffer_config, position):
    min_block_offset = output_buffer_config.min_block_offset
    max_block_offset = output_buffer_config.max_block_offset
    if position == 'up':
        printer.println(hls_kernel_codes.up_exchange)
    elif position == 'mid':
        printer.println(hls_kernel_codes.mid_exchange)
    elif position == 'down':
        printer.println(hls_kernel_codes.down_exchange)
