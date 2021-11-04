import logging
import copy

from codegen import codegen_utils
from codegen import host_codes

import core
from dsl import ir

_logger = logging.getLogger().getChild(__name__)

def host_gen(stencil, output_file, input_buffer_configs, output_buffer_config):
    _logger.info('generate host code as %s', output_file.name)
    printer = codegen_utils.Printer(output_file)

    include_files = ['<iostream>', '<string>', '<unistd.h>', '<vector>', '<fstream>', '<sys/time.h>',
                     '"math.h"', '"%s.h"' % stencil.app_name, '"hbm_config.h"']
    for file_name in include_files:
        printer.println('#include %s' %file_name)

    printer.println(host_codes.includes)

    printer.println(host_codes.HBM_def)

    printer.println(host_codes.reset_function)

    for buffer in input_buffer_configs.values():
        buffer.print_c_load_func(printer)

    printer.println(host_codes.verify_function)

    _print_main(stencil, printer, input_buffer_configs, output_buffer_config)


def _print_main(stencil, printer, input_buffer_configs, output_buffer_config):
    printer.println('////////MAIN FUNCTION//////////')
    printer.println('int main(int argc, char** argv) {')
    printer.do_indent()

    if stencil.boarder_type != 'streaming':
        printer.println(host_codes.unikernel_init_opencl)
    else:
        printer.println(host_codes.streaming_kernel_init_opencl)
    printer.println('std::cout << "%s kernel loaded." << std::endl;' % stencil.app_name)

    printer.println()

    printer.println('// Init buffers')
    for buffer in input_buffer_configs.values():
        buffer.print_c_buffer_def(printer)
        buffer.print_c_buffer_init(printer)
        printer.println()

    output_buffer_config.print_c_buffer_def(printer)

    printer.println('std::cout << "%s buffers inited." << std::endl;' % stencil.app_name)

    printer.println()

    printer.println('// Allocate buffers in global memory')
    for buffer in input_buffer_configs.values():
        buffer.print_c_buffer_allocate(printer)
        printer.println()
    output_buffer_config.print_c_buffer_allocate(printer)
    printer.println('std::cout << "%s buffers allocated." << std::endl;' % stencil.app_name)

    printer.println()

    printer.println('// Set kernel arguments')

    scalar_list = copy.copy(stencil.scalar_vars)
    var_list = copy.copy(stencil.input_vars)
    var_list.append(stencil.output_var)
    with printer.for_('int i = 0', 'i < KERNEL_COUNT', 'i++'):
        count = 0
        for var in var_list:
            printer.println('OCL_CHECK(err, err = kernels[i].setArg(%d, device_%ss[i]));' % (count, var))
            count += 1
        for scalar in scalar_list:
            printer.println('OCL_CHECK(err, err = kernels[i].setArg(%d, 1.5));' % count)
            count += 1

        printer.println()

        for var in stencil.input_vars:
            printer.println('OCL_CHECK(err, err = q.enqueueMigrateMemObjects({device_%ss[i]}, 0/*means from host*/));'
                            % var)

    printer.println('q.finish();')

    printer.println('std::cout << "Write device buffer finished" << std::endl;')

    printer.println()

    printer.println('struct timeval tv1, tv2;')
    printer.println('gettimeofday(&tv1, NULL);')

    printer.println('// Launch kernels')
    with printer.for_('int i = 0', 'i < KERNEL_COUNT', 'i++'):
        printer.println('OCL_CHECK(err, err = q.enqueueTask(kernels[i]));')

    printer.println('q.finish();')
    printer.println('std::cout << "Execution finished" << std::endl;')

    printer.println()

    printer.println('gettimeofday(&tv2, NULL);')

    printer.println('std::cout << "Execution finished, kernel execution time cost:" <<')
    printer.println('\t(tv2.tv_sec-tv1.tv_sec)*1000000 + (tv2.tv_usec - tv1.tv_usec) << "us" << std::endl;')

    printer.println()

    printer.println('// Check results')

    if stencil.iterate%2 == 0:
        final_result_buffer = stencil.input_vars[-1]
    else:
        final_result_buffer = stencil.output_var

    with printer.for_('int i = 0', 'i < KERNEL_COUNT', 'i++'):
        printer.println('OCL_CHECK(err, err = q.enqueueMigrateMemObjects({device_%ss[i]}, CL_MIGRATE_MEM_OBJECT_HOST));'
                        % final_result_buffer)

    printer.println('q.finish();')
    printer.println('std::cout << "Read results finished." << std::endl;')

    printer.println()

    printer.println('bool match = verify(%ss);' % final_result_buffer)

    printer.println('return (match ? EXIT_SUCCESS : EXIT_FAILURE);')

    printer.un_indent()
    printer.println('}')