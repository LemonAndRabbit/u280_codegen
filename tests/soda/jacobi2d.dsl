KERNEL: JACOBI2D
COUNT: 12
ITERATE: 2
BOARDER: overlap
input t1(7680, 1024)
output t0(0,0)= (t1(0,1)+t1(1,0)+t1(0,0)+t1(0,-1)+t1(-1,0))/5
