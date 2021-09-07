#ifndef X_AVG2_H
#define X_AVG2_H

#define GRID_ROWS 100
#define GRID_COLS 100

#define KERNEL_COUNT 6
#define PART_ROWS GRID_ROWS / KERNEL_COUNT

#define ITERATION 3

#include "ap_int.h"
#define DWIDTH 512
#define INTERFACE_WIDTH ap_uint<DWIDTH>
	const int WIDTH_FACTOR = DWIDTH/32;

#endif
