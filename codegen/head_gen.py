import logging

from codegen import codegen_utils
import core
from dsl import ir

_logger = logging.getLogger().getChild(__name__)

def head_gen(stencil, output_file):
    _logger.info('generate kernel code as %s', output_file.name)
    printer = codegen_utils.Printer(output_file)

    printer.println('#ifndef %s_H' % (str.upper(stencil.app_name)))
    printer.println('#define %s_H' % (str.upper(stencil.app_name)))
    printer.println()

    printer.println('#define GRID_ROWS %d' % stencil.size[0])
    printer.println('#define GRID_COLS %d' % stencil.size[1])
    printer.println()

    printer.println('#define KERNEL_COUNT %d' % stencil.kernel_count)
    printer.println('#define PART_ROWS GRID_ROWS / KERNEL_COUNT')
    printer.println()

    printer.println('#define ITERATION %d' % stencil.iterate)
    printer.println()

    printer.println('#include "ap_int.h"')
    printer.println('#define DWIDTH 512')
    printer.println('#define INTERFACE_WIDTH ap_uint<DWIDTH>')
    printer.println('\tconst int WIDTH_FACTOR = DWIDTH/32;')
    printer.println()

    printer.println('#endif')
