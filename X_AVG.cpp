#include <hls_stream.h>
#include X_AVG.h

template<class T>
T HLS_REG(T in){
#pragma HLS pipeline
#pragma HLS inline off
#pragma HLS interface port=return register
    return in;
}

float X_AVG(float x_0_1, float x_0_m1, float x_0_0, float x1_m1_0)
{
    /*
        x(0, -1) + x(0, 1) + x(0, 0) + x1(-1, 0)
    */
    return
        x0_m1 + x0_1 + x0_0 + x1m1_0
} // stencil kernel definition
