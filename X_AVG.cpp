#include <hls_stream.h>
#include X_AVG.h

template<class T>
T HLS_REG(T in){
#pragma HLS pipeline
#pragma HLS inline off
#pragma HLS interface port=return register
    return in;
}

float X_AVG_stencile_kernel(float x_0_1, float x_m1_0, float x_0_m1, 
    float x_0_0)
{
    /*
        (x(0, -1) * (x(0, 1) + x(0, 0))) + x(-1, 0)
    */
    return ((x_0_m1 * (x_0_1 + x_0_0)) + x_m1_0);
} // stencil kernel definition
static void X_AVG(INTERFACE_WIDTH *x, INTERFACE_WIDTH *y)
{
    INTERFACE_WIDTH x_linem1_block0;
    hls::stream<INTERFACE_WIDTH, GRIS_COLS/WIDTH_FACTOR - 0> x_linem1
    INTERFACE_WIDTH x_line0_block0;
    INTERFACE_WIDTH x_line0_block1;

    INTERFACE_WIDTH x_poped_line0_blockm0;

    x_linem1_block0 = x[0];
    for (int i = 1; i < 1 + GRIS_COLS/WIDTH_FACTOR - 1; i++) {
        x_linem1 << x[i];
    }
    x_linem1 = x[100];
    x_line0_block0 = x[101];

    MAJOR_LOOP:
    for (int i = 0; i < GRID_COLS/WIDTH_FACTOR*PART_ROWS; i++) {
        #pragma HLS pipeline II=1

        COMPUTE_LOOP:
        for (int k = 0; k < PARA_FACTOR; k++) {
            float x_0_1[PARA_FACTOR], x_m1_0[PARA_FACTOR], x_0_m1[PARA_FACTOR], x_0_0[PARA_FACTOR];
            #pragma HLS array_partition variable=x_0_1 complete dim=0
            #pragma HLS array_partition variable=x_m1_0 complete dim=0
            #pragma HLS array_partition variable=x_0_m1 complete dim=0
            #pragma HLS array_partition variable=x_0_0 complete dim=0

            unsigned int idx_k = k << 5;

            uint32_t temp_x_line0_1 = (k>14)?x_line0_block1.range(idx_k + -449, idx_k + -480) : x_line0_block0.range(idx_k + 63, idx_k + 32);
            x_0_0 = *((float*)(&temp_x_line0_1));
            uint32_t temp_x_linem1_0 = x_linem1_block0.range(idx_k+31, idx_k);
            uint32_t temp_x_line0_m1 = (k<1)?x_line0_blockm1.range(idx_k + 511, idx_k + 480) : x_line0_block0.range(idx_k + -1, idx_k + -32);
            x_0_0 = *((float*)(&temp_x_line0_m1));
            uint32_t temp_x_line0_0 = x_line0_block0.range(idx_k+31, idx_k);

            float res = X_AVG_stencile_kernel(x_0_1, x_m1_0, x_0_m1, x_0_0);
            y[i].range(idx_k+31, idx_k) = result;
        }
        x_line0_blockm1 = HLS_REG(x_line0_block0);
        x_linem1_block0 = x_linem1.read();
        x_linem1 << HLS_REG(x_line0_block0);
        x_line0_block0 = HLS_REG(x_line0_block1);

        unsigned int idx_x = GRID_COLS/WIDTH_FACTOR + (i + 2);
        x_line0_block1 = HLS_REG(x[idx_x]);
    }

    INTERFACE_WIDTH popout_x_m1;
    for (int i=1; i < GRID_COLS/WIDTH_FACTOR; i++) {
        #pragma HLS pipeline II=1
        x_linem1 >> popout_x_m1;
    }
    return;
} // stencil kernel definition
