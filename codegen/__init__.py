from codegen import hls_kernel_gen
from codegen import head_gen
from codegen import buffer
from codegen import host_gen

from core.utils import find_refs_by_row


def hls_codegen(stencil):
    input_buffer_configs = {}
    for input_var in stencil.input_vars:
        var_references = stencil.all_refs[input_var]
        refs_by_row = find_refs_by_row(var_references)
        input_buffer_configs[input_var] = (buffer.InputBufferConfig(input_var, refs_by_row, 16, stencil.size))

    output_buffer_config = buffer.OutputBufferConfig(stencil.output_var,
                                                     input_buffer_configs[stencil.input_vars[-1]].refs_by_row)

    with open('%s.h' % stencil.app_name, 'w') as file:
        head_gen.head_gen(stencil, file)

    with open('host.cpp', 'w') as file:
        host_gen.host_gen(stencil, file, input_buffer_configs, output_buffer_config)

    if stencil.iterate == 1 or stencil.boarder_type == 'overlap':
        with open('unikernel.cpp', 'w') as file:
            hls_kernel_gen.kernel_gen(stencil, file, input_buffer_configs, output_buffer_config)
    else:
        with open('upkernel.cpp', 'w') as file:
            hls_kernel_gen.kernel_gen(stencil, file, input_buffer_configs, output_buffer_config, 'up')
        with open('midkernel.cpp', 'w') as file:
            hls_kernel_gen.kernel_gen(stencil, file, input_buffer_configs, output_buffer_config, 'mid')
        with open('downkernel.cpp', 'w') as file:
            hls_kernel_gen.kernel_gen(stencil, file, input_buffer_configs, output_buffer_config, 'down')