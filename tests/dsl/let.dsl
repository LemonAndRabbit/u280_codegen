KERNEL: BLUR
COUNT: 6
ITERATE: 1
BOARDER: overlap
input x(3072, 1024)
local k=x(-1,-1)
output y(0, 0) = (3 + x(2,2))/k
