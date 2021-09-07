#include "<hls_stream.h>"
#include "X_AVG2.h"

template<class T>
T HLS_REG(T in){
#pragma HLS pipeline
#pragma HLS inline off
#pragma HLS interface port=return register
    return in;
}

float X_AVG2_stencil_kernel(float x_0_1, float x_0_0, float x_0_m2, 
    float x_m1_0, float x_0_m1, float z_1_0, float z_m1_0)
{
    /*
        (x(0, -1) * (x(0, 1) + x(0, 0))) + x(0, -2) + x(-1, 0) + z(1, 0) + z(-1, 0)
    */
    return ((x_0_m1 * (x_0_1 + x_0_0)) + x_0_m2 + x_m1_0 + z_1_0 + z_m1_0);
} // stencil kernel definition

static void X_AVG2(INTERFACE_WIDTH *x, INTERFACE_WIDTH *z, INTERFACE_WIDTH *y)
{
    INTERFACE_WIDTH x_line_m1_block_0;
    hls::stream<INTERFACE_WIDTH, GRID_COLS/WIDTH_FACTOR - 0> x_line_m1;
    INTERFACE_WIDTH x_line_0_block_0;
    INTERFACE_WIDTH x_line_0_block_1;

    INTERFACE_WIDTH x_poped_line_0_block_m0;

    INTERFACE_WIDTH z_line_m1_block_0;
    hls::stream<INTERFACE_WIDTH, GRID_COLS/WIDTH_FACTOR - 0> z_line_m1;
    hls::stream<INTERFACE_WIDTH, GRID_COLS/WIDTH_FACTOR - -1> z_line_0;
    INTERFACE_WIDTH z_line_1_block_0;


    x_line_m1_block_0 = x[-1*GRID_COLS/WIDTH_FACTOR + 0];
    for (int i = -1*GRID_COLS/WIDTH_FACTOR + 1; i < 0*GRID_COLS/WIDTH_FACTOR; i++) {
        x_line_m1 << x[i];
    }
    x_line_0_block_0 = x[0*GRID_COLS/WIDTH_FACTOR + 0];
    x_line_0_block_1 = x[0*GRID_COLS/WIDTH_FACTOR + 1];

    z_line_m1_block_0 = z[-1*GRID_COLS/WIDTH_FACTOR + 0];
    for (int i = -1*GRID_COLS/WIDTH_FACTOR + 1; i < 0*GRID_COLS/WIDTH_FACTOR; i++) {
        z_line_m1 << z[i];
    }
    for (int i = 0*GRID_COLS/WIDTH_FACTOR + 0; i < 1*GRID_COLS/WIDTH_FACTOR; i++) {
        z_line_0 << z[i];
    }
    z_line_1_block_0 = z[1*GRID_COLS/WIDTH_FACTOR + 0];

    MAJOR_LOOP:
    for (int i = 0; i < GRID_COLS/WIDTH_FACTOR*PART_ROWS; i++) {
        #pragma HLS pipeline II=1

        COMPUTE_LOOP:
        for (int k = 0; k < PARA_FACTOR; k++) {
            float x_0_1[PARA_FACTOR], x_0_0[PARA_FACTOR], x_0_m2[PARA_FACTOR], x_m1_0[PARA_FACTOR], x_0_m1[PARA_FACTOR];
            #pragma HLS array_partition variable=x_0_1 complete dim=0
            #pragma HLS array_partition variable=x_0_0 complete dim=0
            #pragma HLS array_partition variable=x_0_m2 complete dim=0
            #pragma HLS array_partition variable=x_m1_0 complete dim=0
            #pragma HLS array_partition variable=x_0_m1 complete dim=0

            float z_1_0[PARA_FACTOR], z_m1_0[PARA_FACTOR];
            #pragma HLS array_partition variable=z_1_0 complete dim=0
            #pragma HLS array_partition variable=z_m1_0 complete dim=0


            unsigned int idx_k = k << 5;

            uint32_t temp_x_line_0_1 = (k>14)?x_line_0_block_1.range(idx_k + -449, idx_k + -480) : x_line_0_block_0.range(idx_k + 63, idx_k + 32);
            x_0_1 = *((float*)(&temp_x_line_0_1));
            uint32_t temp_x_line_0_0 = x_line_0_block_0.range(idx_k+31, idx_k);
            x_0_0 = *((float*)(&temp_x_line_0_0));
            uint32_t temp_x_line_0_m2 = (k<2)?x_line_0_block_m1.range(idx_k + 479, idx_k + 448) : x_line_0_block_0.range(idx_k + -33, idx_k + -64);
            x_0_m2 = *((float*)(&temp_x_line_0_m2));
            uint32_t temp_x_line_m1_0 = x_line_m1_block_0.range(idx_k+31, idx_k);
            x_m1_0 = *((float*)(&temp_x_line_m1_0));
            uint32_t temp_x_line_0_m1 = (k<1)?x_line_0_block_m1.range(idx_k + 511, idx_k + 480) : x_line_0_block_0.range(idx_k + -1, idx_k + -32);
            x_0_m1 = *((float*)(&temp_x_line_0_m1));
            uint32_t temp_z_line_1_0 = z_line_1_block_0.range(idx_k+31, idx_k);
            z_1_0 = *((float*)(&temp_z_line_1_0));
            uint32_t temp_z_line_m1_0 = z_line_m1_block_0.range(idx_k+31, idx_k);
            z_m1_0 = *((float*)(&temp_z_line_m1_0));

            float res = X_AVG2_stencil_kernel(x_0_1, x_0_0, x_0_m2, x_m1_0, x_0_m1, z_1_0, z_m1_0);
            y[i].range(idx_k+31, idx_k) = result;
        }
        x_line_0_block_m1 = HLS_REG(x_line_0_block_0);
        x_line_m1_block_0 = x_line_m1.read();
        x_line_m1 << HLS_REG(x_line_0_block_0);
        x_line_0_block_0 = HLS_REG(x_line_0_block_1);

        unsigned int idx_x = GRID_COLS/WIDTH_FACTOR + (i + 2);
        x_line_0_block_1 = HLS_REG(x[idx_x]);
        z_line_m1_block_0 = z_line_m1.read();
        z_line_m1 << z_line_0.read();
        z_line_0 << HLS_REG(z_line_1_block_0);

        unsigned int idx_z = GRID_COLS/WIDTH_FACTOR + (i + 1);
        z_line_1_block_0 = HLS_REG(z[idx_z]);
    }

    INTERFACE_WIDTH popout_x_m1;
    for (int i=1; i < GRID_COLS/WIDTH_FACTOR; i++) {
        #pragma HLS pipeline II=1
        x_linem1 >> popout_x_m1;
    }
    INTERFACE_WIDTH popout_z_m1;
    for (int i=1; i < GRID_COLS/WIDTH_FACTOR; i++) {
        #pragma HLS pipeline II=1
        z_linem1 >> popout_z_m1;
    }
    INTERFACE_WIDTH popout_z_0;
    for (int i=0; i < GRID_COLS/WIDTH_FACTOR; i++) {
        #pragma HLS pipeline II=1
        z_line0 >> popout_z_0;
    }
    return;
} // stencil kernel definition

extern "C"{
void kernel(INTERFACE_WIDTH *x, INTERFACE_WIDTH *z, INTERFACE_WIDTH *y)
{
    #pragma HLS INTERFACE m_axi port=x offset=slave bundle=x1
    #pragma HLS INTERFACE m_axi port=z offset=slave bundle=z1
    #pragma HLS INTERFACE m_axi port=y offset=slave bundle=y1

    #pragma HLS INTERFACE s_axilite port=x
    #pragma HLS INTERFACE s_axilite port=z
    #pragma HLS INTERFACE s_axilite port=y
    #pragma HLS INTERFACE s_axilite port=return
    int i;
    for (i=0; i<ITERATION/2; i++) {
        X_AVG2(x, z, y);
        X_AVG2(z, y, x);
    }
    X_AVG2(x, z, y);
    return;
}
}
