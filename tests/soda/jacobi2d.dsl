KERNEL: JACOBI2D
COUNT: 6
REPEAT: 3
ITERATE: 12
BOARDER: overlap
input t1(9720, 1024)
output t0(0,0)= (t1(0,1)+t1(1,0)+t1(0,0)+t1(0,-1)+t1(-1,0))/5
