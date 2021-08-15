import math
import collections

from codegen.codegen_utils import Printer
from codegen import codegen_utils

class BufferConfig:
    def __init__(self, var_name, refs_by_row, unroll_factor, size):
        self.var_name = var_name
        self.refs_by_row = refs_by_row
        self.unroll_factor = unroll_factor
        self.flow = []
        self.block_num = collections.OrderedDict()
        self.poped_num = collections.OrderedDict()
        self.size = size

    def print_define_buffer(self, printer: Printer):
        topmost = min(self.refs_by_row.keys())
        downmost = max(self.refs_by_row.keys())

        for line_num in range(topmost, downmost):
            if line_num not in self.refs_by_row.keys():
                self.block_num[line_num] = 0
            else:
                rightmost = max(self.refs_by_row[line_num])
                self.block_num[line_num] = math.ceil(rightmost/self.unroll_factor) + 1
                for i in range(self.block_num[line_num]):
                    printer.println('INTERFACE_WIDTH %s_line%s_block%s;' % (self.var_name, codegen_utils.idx2str(line_num), i))
                    self.flow.append('%s_line%s_block%s'  % (self.var_name, codegen_utils.idx2str(line_num), i))
                printer.println('hls::stream<INTERFACE_WIDTH, GRIS_COLS/WIDTH_FACTOR - %s> %s_line%s' %
                                (self.block_num[line_num] - 1, self.var_name, codegen_utils.idx2str(line_num)))
                self.flow.append('%s_line%s' % (self.var_name, codegen_utils.idx2str(line_num)))
        rightmost = max(self.refs_by_row[downmost])
        self.block_num[downmost] = math.ceil(float(rightmost) / self.unroll_factor) + 1
        for i in range(self.block_num[downmost]):
            printer.println('INTERFACE_WIDTH %s_line%s_block%s;' % (self.var_name, codegen_utils.idx2str(downmost), i))
            self.flow.append('%s_line%s_block%s' % (self.var_name, codegen_utils.idx2str(downmost), i))

    def print_poped_object_def(self, printer: Printer):
        topmost = min(self.refs_by_row.keys())
        downmost = max(self.refs_by_row.keys())
        for line_num in range(topmost, downmost+1):
            if line_num not in self.refs_by_row.keys():
                continue
            else:
                leftmost = min(position for position in self.refs_by_row[line_num])
                if leftmost < 0:
                    self.poped_num[line_num] = math.ceil(abs(leftmost)/self.unroll_factor)
                    for position in range(self.poped_num[line_num]):
                        printer.println('INTERFACE_WIDTH %s_poped_line%s_blockm%s;'
                                    % (self.var_name, codegen_utils.idx2str(line_num), position))

    def print_init_buffer(self, printer: Printer):
        flow_scan = 0
        read_index = 0
        for line_num in self.block_num.keys():
            for i in range(self.block_num[line_num]):
                printer.println('%s = %s[%s];' %(self.flow[flow_scan], self.var_name, read_index))
                read_index += 1
                flow_scan += 1
            if line_num != list(self.block_num.keys())[-1]:
                with printer.for_('int i = %s' % read_index,
                              'i < %s + GRIS_COLS/WIDTH_FACTOR - %s' % (read_index, self.block_num[line_num]), 'i++'):
                    printer.println('%s << %s[i];' % (self.flow[flow_scan], self.var_name))
                read_index += self.size[1] - self.block_num[line_num]

    def print_data_retrieve_with_unroll(self, printer: Printer, src_idx, dst='', default_stmt='', default_value=0):
        if src_idx[1] == 0:
            printer.println('uint32_t temp_%s_line%s_%s = %s_line%s_block0.range(idx_k+31, idx_k);'
                            % (self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1]),
                               self.var_name, codegen_utils.idx2str(src_idx[0])))
        elif src_idx[1] > 0:
            #TODO: deal with reference more right blocks
            idx_left_offset = src_idx[1]*32 + 31
            idx_right_offset = src_idx[1]*32
            switch_k = self.unroll_factor - src_idx[1] - 1
            switched_idx_left_offset = idx_left_offset - self.unroll_factor*32
            switched_idx_right_offset= idx_right_offset - self.unroll_factor*32
            printer.println('uint32_t temp_%s_line%s_%s = (k>%s)?%s_line%s_block1.range(idx_k + %s, idx_k + %s)'
                            ' : %s_line%s_block0.range(idx_k + %s, idx_k + %s);'
                            % (self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1]),
                               str(switch_k),
                               self.var_name, codegen_utils.idx2str(src_idx[0]), switched_idx_left_offset, switched_idx_right_offset,
                               self.var_name, codegen_utils.idx2str(src_idx[0]), idx_left_offset, idx_right_offset))
            if default_stmt is not '':
                printer.println('%s = (%s)? %s: *((float*)(&temp_%s_line%s_%s));'
                            % (dst, default_stmt, str(default_value),
                               self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1])))
            else:
                printer.println('%s = *((float*)(&temp_%s_line%s_%s));'
                                % (dst,
                                   self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1])))
        elif src_idx[1] < 0:
            #TODO: deal with reference more right blocks
            idx_left_offset = src_idx[1] * 32 + 31
            idx_right_offset = src_idx[1] * 32
            switch_k = abs(src_idx[1])
            switched_idx_left_offset = idx_left_offset + self.unroll_factor * 32
            switched_idx_right_offset = idx_right_offset + self.unroll_factor * 32
            printer.println('uint32_t temp_%s_line%s_%s = (k<%s)?%s_line%s_blockm1.range(idx_k + %s, idx_k + %s)'
                            ' : %s_line%s_block0.range(idx_k + %s, idx_k + %s);'
                            % (self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1]),
                               str(switch_k),
                               self.var_name, codegen_utils.idx2str(src_idx[0]), switched_idx_left_offset, switched_idx_right_offset,
                               self.var_name, codegen_utils.idx2str(src_idx[0]), idx_left_offset, idx_right_offset))
            if default_stmt is not '':
                printer.println('%s = (%s)? %s: *((float*)(&temp_%s_line%s_%s));'
                            % (dst, default_stmt, str(default_value),
                               self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1])))
            else:
                printer.println('%s = *((float*)(&temp_%s_line%s_%s));'
                                % (dst,
                                   self.var_name, codegen_utils.idx2str(src_idx[0]), codegen_utils.idx2str(src_idx[1])))

    def print_data_movement(self, printer: Printer):
        topmost = min(self.refs_by_row.keys())
        downmost = max(self.refs_by_row.keys())
        for line_num in range(topmost, downmost + 1): #fill in poped buffers
            if line_num in self.poped_num.keys():
                printer.println('%s_line%s_blockm1 = HLS_REG(%s_line%s_block0);'
                                % (self.var_name, codegen_utils.idx2str(line_num), self.var_name, codegen_utils.idx2str(line_num)))

        for x, y in zip(self.flow, self.flow[1:]):
            temp = ''
            if 'block' not in x:
                temp += x + ' << '
            else:
                temp += x + ' = '

            if 'block' not in y:
                temp += y + '.read()'
            else:
                temp += 'HLS_REG(%s)' % y
            temp += ';'
            printer.println(temp)

        printer.println()
        printer.println('unsigned int idx_%s = GRID_COLS/WIDTH_FACTOR + (i + %s);'
                        % (self.var_name, str(self.block_num[downmost])))
        printer.println('%s = HLS_REG(%s[idx_%s]);'
                        % (self.flow[-1], self.var_name, self.var_name))

    def print_pop_out(self, printer:Printer):
        topmost = min(self.refs_by_row.keys())
        downmost = max(self.refs_by_row.keys())
        for line_num in range(topmost, downmost):
            printer.println('INTERFACE_WIDTH popout_%s_%s;'
                            % (self.var_name, codegen_utils.idx2str(line_num)))
            if line_num not in self.block_num:
                start_pop_idx = 0
            else:
                start_pop_idx = self.block_num[line_num]
            with printer.for_('int i=%s' % start_pop_idx, 'i < GRID_COLS/WIDTH_FACTOR', 'i++'):
                printer.println('#pragma HLS pipeline II=1')
                printer.println('%s_line%s >> popout_%s_%s;'
                                % (self.var_name, codegen_utils.idx2str(line_num),
                                   self.var_name, codegen_utils.idx2str(line_num)))